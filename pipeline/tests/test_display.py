import re

import geopandas as gpd
import pytest
import shapely
from shapely.geometry import MultiPolygon, Polygon, box
from test_metrics import square_in_lonlat

from gerry.display import (
    VIEW_SIZE,
    display_crop,
    district_outline,
    district_points,
    fit_to_view,
    state_map,
    state_points,
    svg_path,
    us_map,
)


def points(path: str) -> list[tuple[int, int]]:
    return [(int(x), int(y)) for x, y in re.findall(r"(-?\d+) (-?\d+)", path)]


class TestSvgPath:
    def test_polygon_becomes_one_closed_subpath(self):
        square = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)])
        assert svg_path(square) == "M0 0L10 0L10 10L0 10Z"

    def test_holes_are_extra_subpaths(self):
        donut = Polygon([(0, 0), (10, 0), (10, 10), (0, 10)], [[(4, 4), (6, 4), (6, 6), (4, 6)]])
        assert svg_path(donut).count("M") == 2
        assert svg_path(donut).count("Z") == 2

    def test_each_piece_of_a_multipolygon_is_a_subpath(self):
        pieces = MultiPolygon([box(0, 0, 1, 1), box(5, 5, 6, 6)])
        assert svg_path(pieces).count("M") == 2

    def test_rounds_and_drops_points_that_round_to_the_same_spot(self):
        shape = Polygon([(0, 0), (10.2, 0), (10.4, 0.1), (10, 10), (0, 10)])
        assert svg_path(shape) == "M0 0L10 0L10 10L0 10Z"


def test_fit_to_view_scales_keeps_aspect_and_flips_y():
    shapes, (width, height) = fit_to_view([box(100, 50, 300, 150)])
    assert (width, height) == (VIEW_SIZE, VIEW_SIZE // 2)
    minx, miny, maxx, maxy = shapes[0].bounds
    assert (minx, miny, maxx, maxy) == pytest.approx((0, 0, VIEW_SIZE, VIEW_SIZE / 2))
    marker, _ = fit_to_view([box(100, 50, 300, 150), box(100, 140, 110, 150)])
    assert marker[1].bounds[1] == pytest.approx(0)  # the top of the map is y = 0


class TestDistrictOutline:
    def test_returns_a_view_box_and_a_path(self):
        outline = district_outline(square_in_lonlat(-150, 64), "EPSG:4269", detail=0.001)
        width, height = map(int, outline["viewBox"].split()[2:])
        assert max(width, height) == VIEW_SIZE
        assert outline["d"].startswith("M") and outline["d"].endswith("Z")

    def test_a_square_on_the_ground_is_square_on_screen_even_in_alaska(self):
        outline = district_outline(square_in_lonlat(-150, 64), "EPSG:4269", detail=0.001)
        width, height = map(int, outline["viewBox"].split()[2:])
        assert width == pytest.approx(height, rel=0.01)

    def test_coarser_detail_uses_fewer_points(self):
        wiggly = shapely.segmentize(square_in_lonlat(-100, 40), 0.001).buffer(0.002)
        fine = district_outline(wiggly, "EPSG:4269", detail=0.0005)
        coarse = district_outline(wiggly, "EPSG:4269", detail=0.01)
        assert len(points(coarse["d"])) < len(points(fine["d"]))


def test_state_map_keeps_shared_borders_identical():
    left = Polygon([(-100, 40), (-99.5, 40), (-99.51, 40.5), (-99.5, 41), (-100, 41)])
    right = Polygon([(-99.5, 40), (-99, 40), (-99, 41), (-99.5, 41), (-99.51, 40.5)])
    districts = gpd.GeoDataFrame(
        {"district_id": ["ME-01", "ME-02"], "state": "ME"}, geometry=[left, right], crs="EPSG:4269"
    )
    result = state_map(districts, detail=0.001)
    assert set(result["paths"]) == {"ME-01", "ME-02"}
    shared = set(points(result["paths"]["ME-01"])) & set(points(result["paths"]["ME-02"]))
    assert len(shared) >= 3  # the whole bent border, not just its two ends
    width, height = map(int, result["viewBox"].split()[2:])
    assert max(width, height) == VIEW_SIZE


class TestDistrictPoints:
    def test_points_land_on_the_district_outline_drawing(self):
        # A spike 0.006 degrees (about 670 m) tall: kept at this detail, simplified away at a
        # coarser one, so a mismatched detail would move the drawing's bounds.
        spike = Polygon([(-69.5, 45), (-69.4995, 45.006), (-69.499, 45)])
        shape = box(-70, 44, -69, 45).union(spike)
        drawn = district_outline(shape, "EPSG:4269", 0.002)
        placed = district_points(shape, "EPSG:4269", 0.002, [shapely.Point(-70, 45)])
        assert placed["viewBox"] == drawn["viewBox"]
        assert tuple(placed["points"][0]) in points(drawn["d"])


class TestStatePoints:
    @pytest.fixture
    def districts(self):
        return gpd.GeoDataFrame(
            {"district_id": ["ME-01", "ME-02"], "state": "ME"},
            geometry=[box(-70, 44, -69, 45), box(-69, 44, -68, 45)],
            crs="EPSG:4269",
        )

    def test_points_land_where_the_map_draws_the_same_spot(self, districts):
        drawn = state_map(districts, detail=0.001)
        placed = state_points(districts, 0.001, [shapely.Point(-69, 44), shapely.Point(-70, 45)])
        assert placed["viewBox"] == drawn["viewBox"]
        # The shared border's south end, and ME-01's northwest corner, are both path vertices.
        vertices = points(drawn["paths"]["ME-01"])
        assert tuple(placed["points"][0]) in vertices
        assert tuple(placed["points"][1]) in vertices

    def test_a_point_between_two_corners_lands_between_them(self, districts):
        width, height = map(int, state_map(districts, 0.001)["viewBox"].split()[2:])
        ((x, y),) = state_points(districts, 0.001, [shapely.Point(-69, 44.5)])["points"]
        assert x == pytest.approx(width / 2, abs=2) and y == pytest.approx(height / 2, abs=2)


def test_pieces_too_small_to_see_are_left_off_coarse_outlines():
    mainland = square_in_lonlat(-100, 40, side_m=50_000)
    speck = square_in_lonlat(-99.5, 40, side_m=300)  # 300 m island, 40 km away
    district = MultiPolygon([mainland, speck])
    coarse = district_outline(district, "EPSG:4269", detail=0.01)  # 500 m tolerance
    fine = district_outline(district, "EPSG:4269", detail=0.001)  # 50 m tolerance
    assert coarse["d"].count("M") == 1
    assert fine["d"].count("M") == 2


# Hawaii's 2nd district: the Big Island plus the Northwestern Hawaiian Islands out to Kure Atoll.
BIG_ISLAND = box(-156.0, 19.0, -155.0, 20.2)
KURE = box(-178.4, 28.35, -178.3, 28.45)


class TestDisplayCrop:
    def test_hawaii_drawings_leave_out_the_northwestern_islands_and_say_so(self):
        shape, note = display_crop("HI", MultiPolygon([BIG_ISLAND, KURE]))
        assert shape.equals(BIG_ISLAND)
        assert note == "The Northwestern Hawaiian Islands, part of District 2, are not shown."

    def test_a_hawaii_shape_on_the_main_islands_is_untouched(self):
        oahu = box(-158.3, 21.25, -157.6, 21.7)
        assert display_crop("HI", oahu) == (oahu, None)

    def test_a_shape_wholly_outside_the_area_is_never_cut_to_nothing(self):
        assert display_crop("HI", KURE) == (KURE, None)

    def test_other_states_are_untouched(self):
        aleutians = MultiPolygon([box(-179, 51, -178, 52), box(-150, 60, -149, 61)])
        assert display_crop("AK", aleutians) == (aleutians, None)


# A rough US: boxes in NAD83 degrees where the states are.
US_BOXES = {
    "WA": box(-124.7, 45.5, -117.0, 49.0),
    "CA": box(-124.4, 32.5, -114.1, 42.0),
    "AZ": box(-114.8, 31.3, -109.0, 37.0),
    "TX": box(-106.6, 25.8, -93.5, 36.5),
    "FL": box(-87.6, 24.5, -80.0, 31.0),
    "ME": box(-71.1, 43.0, -66.9, 47.5),
    "AK": box(-170.0, 52.0, -141.0, 71.0),
    # The main islands, plus an island far west, big enough to draw, that the crop leaves out.
    "HI": MultiPolygon([box(-160.3, 18.9, -154.8, 22.3), box(-178.6, 28.2, -178.0, 28.6)]),
}


def bounds_of(path: str) -> tuple[int, int, int, int]:
    xs, ys = zip(*points(path), strict=True)
    return min(xs), min(ys), max(xs), max(ys)


def shape_of(path: str):
    """The drawn shape: one polygon per subpath, in view coordinates."""
    rings = [points(f"M{ring}") for ring in path.split("M") if ring]
    return shapely.union_all([Polygon(r) for r in rings])


def covered_by_inset(drawn: dict, inset: str) -> list[str]:
    """The states whose drawn shapes an inset overlaps (sharing an edge isn't overlap)."""
    shapes = {s: shape_of(p) for s, p in drawn["paths"].items()}
    return [s for s, g in shapes.items() if s != inset and g.intersection(shapes[inset]).area > 0]


@pytest.fixture(scope="module")
def us():
    return us_map(US_BOXES, detail=0.002)


class TestUsMap:
    def test_draws_and_labels_every_state_in_one_view(self, us):
        assert set(us["paths"]) == set(US_BOXES) == set(us["labels"])
        width, height = (int(n) for n in us["viewBox"].split()[2:])
        assert width == VIEW_SIZE
        for x, y in us["labels"].values():
            assert 0 <= x <= width and 0 <= y <= height

    def test_keeps_the_lower_48_where_they_are_with_north_up(self, us):
        wa, fl, me, ca = (us["labels"][s] for s in ["WA", "FL", "ME", "CA"])
        assert wa[0] < fl[0] and wa[1] < fl[1]  # Washington is northwest of Florida
        assert me[0] > ca[0]

    def test_puts_alaska_and_hawaii_bottom_left_without_covering_any_state(self, us):
        width, height = (int(n) for n in us["viewBox"].split()[2:])
        for inset in ["AK", "HI"]:
            x, y = us["labels"][inset]
            assert x < width / 2 and y > height / 2
            assert covered_by_inset(us, inset) == []
        assert us["labels"]["AK"][0] < us["labels"]["HI"][0]

    def test_shrinks_alaska_to_an_inset(self, us):
        ak, tx = bounds_of(us["paths"]["AK"]), bounds_of(us["paths"]["TX"])
        # At true scale Alaska is about twice as wide as Texas.
        assert ak[2] - ak[0] < tx[2] - tx[0]

    def test_crops_hawaii_like_its_state_map(self, us):
        hi = bounds_of(us["paths"]["HI"])
        assert len(re.findall("M", us["paths"]["HI"])) == 1  # only the main islands' box
        assert hi[2] - hi[0] < 200

    def test_moves_an_inset_down_until_it_clears_the_mainland(self):
        # A mainland state right where the insets would go, at the bottom left.
        crowded = {**US_BOXES, "XX": box(-125.0, 24.5, -100.0, 30.0)}
        drawn = us_map(crowded, detail=0.002)
        for inset in ["AK", "HI"]:
            assert covered_by_inset(drawn, inset) == []
        # Anchor: the crowding state is drawn, so "covers nothing" isn't vacuous.
        assert shape_of(drawn["paths"]["XX"]).area > 0
