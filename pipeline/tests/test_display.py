import math
import re

import geopandas as gpd
import pytest
import shapely
from shapely.geometry import MultiPolygon, Polygon, box
from test_metrics import square_in_lonlat

from gerry.display import (
    CLOSEUP_MIN_SIDE,
    CLOSEUP_SMALL_RADIUS,
    VIEW_SIZE,
    closeup_boxes,
    display_crop,
    district_outline,
    district_points,
    fit_to_view,
    state_closeups,
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


def evenodd_shape(path: str):
    """The drawn shape with fill-rule="evenodd", as the site draws it: holes stay empty."""
    shape = Polygon()
    for ring in path.split("M")[1:]:
        shape = shape.symmetric_difference(Polygon(points(f"M{ring}")))
    return shape


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


class TestCloseupBoxes:
    """Squares of a state map (view units, 1000 on the longer side) to show enlarged."""

    SIZE = (1000, 800)

    def test_none_when_every_district_is_big_enough_to_see(self):
        # 100 units across: a tenth of the map, plenty to see, and its square would be small
        # enough to keep, so only the size check leaves it out.
        assert closeup_boxes([box(400, 400, 500, 500)], self.SIZE) == []

    def test_one_square_around_a_cluster_of_tiny_districts(self):
        tiny = [box(400 + 10 * i, 400, 410 + 10 * i, 410) for i in range(3)]
        [(x0, y0, x1, y1)] = closeup_boxes([box(0, 0, 1000, 800), *tiny], self.SIZE)
        assert x1 - x0 == pytest.approx(y1 - y0)
        assert x1 - x0 == pytest.approx(CLOSEUP_MIN_SIDE)  # no closer than the most zoom
        assert shapely.box(x0, y0, x1, y1).contains(shapely.union_all(tiny))

    def test_a_big_cluster_gets_a_square_padded_around_it(self):
        tiny = [
            box(300 + 10 * i, 300 + 10 * j, 310 + 10 * i, 310 + 10 * j)
            for i in range(20)
            for j in range(20)
        ]
        [(x0, y0, x1, y1)] = closeup_boxes(tiny, self.SIZE)
        # The 200-unit cluster, padded on every side, centered.
        assert (
            x1 - x0 > 200
            and (x0 + x1) / 2 == pytest.approx(400)
            and (y0 + y1) / 2 == pytest.approx(400)
        )

    def test_far_apart_clusters_get_their_own_squares(self):
        a, b = box(100, 100, 110, 110), box(800, 600, 810, 610)
        boxes = closeup_boxes([a, b], self.SIZE)
        assert len(boxes) == 2
        assert all(any(shapely.box(*bx).contains(t) for bx in boxes) for t in (a, b))

    def test_squares_that_would_overlap_are_merged(self):
        # 80 apart: separate clusters, but their smallest squares would overlap.
        a, b = box(400, 400, 410, 410), box(490, 400, 500, 410)
        [square] = closeup_boxes([a, b], self.SIZE)
        assert shapely.box(*square).contains(a.union(b))

    def test_a_square_near_the_edge_stays_inside_the_map(self):
        [(x0, y0, x1, y1)] = closeup_boxes([box(990, 790, 1000, 800)], self.SIZE)
        assert (x1, y1) == pytest.approx((1000, 800))
        # Moved in whole, not cut down by the edge.
        assert (x1 - x0, y1 - y0) == pytest.approx((CLOSEUP_MIN_SIDE, CLOSEUP_MIN_SIDE))

    def test_a_long_thin_district_too_big_to_enlarge_much_is_left_alone(self):
        # Narrow enough to count as small, but its square would be most of the map.
        assert closeup_boxes([box(0, 400, 1000, 410)], self.SIZE) == []

    def test_takes_a_bigger_largest_square_when_asked(self):
        [(x0, _, x1, _)] = closeup_boxes([box(300, 400, 700, 410)], self.SIZE, max_side=600)
        assert 500 < x1 - x0 <= 600


def top_level(districts) -> list[dict]:
    """A state's close-ups of the state map itself, leaving out nested ones."""
    return [c for c in state_closeups(districts, 0.002) if "parent" not in c]


class TestStateCloseups:
    @pytest.fixture
    def districts(self):
        # A 2-degree state with two 0.01-degree (about 1 km) districts side by side at its middle.
        tiny = [box(-99.01, 40.99, -99.0, 41.0), box(-99.0, 40.99, -98.99, 41.0)]
        rest = box(-100, 40, -98, 42).difference(shapely.union_all(tiny))
        return gpd.GeoDataFrame(
            {"district_id": ["KS-01", "KS-02", "KS-03"], "state": "KS"},
            geometry=[rest, *tiny],
            crs="EPSG:4269",
        )

    @pytest.fixture
    def coastal(self, districts):
        # A strait just north of the tiny districts, so their square's top part is empty.
        sea = box(-100, 41.0, -98, 41.4)
        districts.loc[0, "geometry"] = districts.geometry[0].difference(sea)
        return districts

    @pytest.mark.parametrize("state", ["districts", "coastal"])
    def test_draws_the_tiny_districts_enlarged_where_the_square_shows_them(self, state, request):
        districts = request.getfixturevalue(state)
        main = state_map(districts, 0.002)
        [closeup] = top_level(districts)
        x0, y0, x1, y1 = closeup["box"]
        width, height = map(int, closeup["viewBox"].split()[2:])
        assert max(width, height) == VIEW_SIZE
        zoom = VIEW_SIZE / max(x1 - x0, y1 - y0)
        assert zoom > 5
        for district in ("KS-02", "KS-03"):
            mx0, my0, mx1, my1 = bounds_of(main["paths"][district])
            cx0, cy0, cx1, cy1 = bounds_of(closeup["paths"][district])
            # The same spot, moved to the square's corner and scaled up (main-map rounding aside).
            assert cx0 == pytest.approx((mx0 - x0) * zoom, abs=zoom)
            assert cy1 == pytest.approx((my1 - y0) * zoom, abs=zoom)
            assert cx1 - cx0 == pytest.approx((mx1 - mx0) * zoom, abs=2 * zoom)

    def test_draws_the_districts_around_them_cut_to_the_square(self, districts):
        [closeup] = top_level(districts)
        assert set(closeup["paths"]) == {"KS-01", "KS-02", "KS-03"}
        width, height = map(int, closeup["viewBox"].split()[2:])
        assert bounds_of(closeup["paths"]["KS-01"]) == (0, 0, width, height)

    def test_keeps_shared_borders_identical(self, districts):
        [closeup] = top_level(districts)
        shared = set(points(closeup["paths"]["KS-02"])) & set(points(closeup["paths"]["KS-03"]))
        assert len(shared) >= 2

    def test_districts_tile_the_square_without_gaps_or_overlaps(self, districts):
        # An irregular shared border wiggling up to 200 m either side: some wiggles are kept at the
        # close-up's detail (about 55 m) and some aren't.
        wiggle = [0.0016 * math.sin(i * 1.7) + 0.0008 * math.sin(i * 0.37) for i in range(51)]
        zigzag = [(-99.0 + dx, 40.99 + i * 0.0002) for i, dx in enumerate(wiggle)]
        west = Polygon([(-99.01, 40.99), *zigzag, (-99.01, 41.0)])
        east = Polygon([*zigzag[::-1][:1], (-98.99, 41.0), (-98.99, 40.99), *zigzag])
        districts.loc[1, "geometry"], districts.loc[2, "geometry"] = west, east.buffer(0)
        [closeup] = top_level(districts)
        shapes = [evenodd_shape(p) for p in closeup["paths"].values()]
        width, height = map(int, closeup["viewBox"].split()[2:])
        # Exact to a square unit: a few dozen square units of gap is what separately simplified
        # borders leave here.
        assert sum(g.area for g in shapes) == pytest.approx(width * height, abs=1)
        assert shapely.union_all(shapes).area == pytest.approx(width * height, abs=1)

    def test_is_drawn_from_full_detail_not_the_simplified_map(self, districts):
        # A 50 m notch in a tiny district: far below the main map's detail, but visible enlarged.
        notch = box(-99.0055, 40.9945, -99.005, 41.0)
        districts.loc[1, "geometry"] = districts.geometry[1].difference(notch)
        districts.loc[0, "geometry"] = districts.geometry[0].union(notch)
        [closeup] = top_level(districts)
        main = state_map(districts, 0.002)
        assert len(points(closeup["paths"]["KS-02"])) > len(points(main["paths"]["KS-02"]))

    def test_none_for_a_state_whose_districts_are_all_big(self):
        halves = gpd.GeoDataFrame(
            {"district_id": ["KS-01", "KS-02"], "state": "KS"},
            geometry=[box(-100, 40, -99, 42), box(-99, 40, -98, 42)],
            crs="EPSG:4269",
        )
        assert top_level(halves) == []


class TestNestedCloseups:
    """A close-up whose districts are still too small to see gets close-ups of its own."""

    @staticmethod
    def state(*extra, dot=None):
        # A 2-degree state with a cluster of 1 km districts at its middle, one of which has a
        # 0.0004-degree district (about 40 m) inside it: too small to see even 8 times larger.
        speck = box(-99.0052, 40.9948, -99.0048, 40.9952)
        tiny = [box(-99.01, 40.99, -99.0, 41.0).difference(speck), box(-99.0, 40.99, -98.99, 41.0)]
        tiny += [speck.difference(dot), dot] if dot else [speck]
        shapes = [*tiny, *extra]
        rest = box(-100, 40, -98, 42).difference(shapely.union_all(shapes))
        ids = [f"KS-{i:02d}" for i in range(1, len(shapes) + 2)]
        return gpd.GeoDataFrame(
            {"district_id": ids, "state": "KS"}, geometry=[rest, *shapes], crs="EPSG:4269"
        )

    def test_a_close_up_with_a_district_still_too_small_gets_its_own(self):
        outer, inner = state_closeups(self.state(), 0.002)
        assert "parent" not in outer
        assert inner["parent"] == 0
        # The inner square is in the outer close-up's units, around where it draws the speck.
        x0, y0, x1, y1 = inner["box"]
        sx0, sy0, sx1, sy1 = bounds_of(outer["paths"]["KS-04"])
        assert x0 <= sx0 and sx1 <= x1 and y0 <= sy0 and sy1 <= y1
        assert x1 - x0 == pytest.approx(CLOSEUP_MIN_SIDE)
        # Drawn 8 times larger again: the speck, 34 m east to west at this latitude, goes from
        # about 1.2 units across to 9.7.
        sx0, _, sx1, _ = bounds_of(inner["paths"]["KS-04"])
        assert sx1 - sx0 == pytest.approx(9.7, abs=1)

    def test_a_big_district_cut_to_a_sliver_by_the_square_gets_none(self):
        # A big district whose west edge pokes about 250 m into the outer square: a sliver as
        # thin as a small district, but only because the square cuts it.
        big = box(-98.84, 40.2, -98.2, 41.8)
        closeups = state_closeups(self.state(big), 0.002)
        x0, _, x1, _ = bounds_of(closeups[0]["paths"]["KS-05"])
        width, _ = map(int, closeups[0]["viewBox"].split()[2:])
        # Anchor: the sliver is drawn, at the edge, and thin enough to count as small.
        assert x1 == width and (x1 - x0) / 2 < CLOSEUP_SMALL_RADIUS
        assert [c.get("parent") for c in closeups] == [None, 0]  # only the speck's

    def test_close_ups_go_two_levels_deep_at_most(self):
        # Ten times smaller again: still too small in the inner close-up, but there it stops.
        dot = box(-99.00502, 40.99498, -99.00498, 40.99502)
        assert [c.get("parent") for c in state_closeups(self.state(dot=dot), 0.002)] == [None, 0]
