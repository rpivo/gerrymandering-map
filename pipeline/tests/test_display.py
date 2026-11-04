import re

import geopandas as gpd
import pytest
import shapely
from shapely.geometry import MultiPolygon, Polygon, box
from test_metrics import square_in_lonlat

from gerry.display import VIEW_SIZE, district_outline, fit_to_view, state_map, svg_path


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


def test_pieces_too_small_to_see_are_left_off_coarse_outlines():
    mainland = square_in_lonlat(-100, 40, side_m=50_000)
    speck = square_in_lonlat(-99.5, 40, side_m=300)  # 300 m island, 40 km away
    district = MultiPolygon([mainland, speck])
    coarse = district_outline(district, "EPSG:4269", detail=0.01)  # 500 m tolerance
    fine = district_outline(district, "EPSG:4269", detail=0.001)  # 50 m tolerance
    assert coarse["d"].count("M") == 1
    assert fine["d"].count("M") == 2
