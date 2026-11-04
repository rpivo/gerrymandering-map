import math

import pytest
import shapely
from pyproj import Transformer
from shapely.geometry import MultiPolygon, Point, Polygon, box

from gerry.generalize import local_crs
from gerry.metrics import (
    compactness,
    convex_hull_ratio,
    polsby_popper,
    reock,
    schwartzberg,
)

CIRCLE = Point(0, 0).buffer(1, quad_segs=512)
SQUARE = box(0, 0, 1, 1)
L_SHAPE = Polygon([(0, 0), (2, 0), (2, 1), (1, 1), (1, 2), (0, 2)])  # three unit squares
TWO_SQUARES = MultiPolygon([box(0, 0, 1, 1), box(3, 0, 4, 1)])


class TestKnownAnswers:
    def test_circle_is_perfectly_compact(self):
        assert polsby_popper(CIRCLE) == pytest.approx(1, abs=1e-4)
        assert reock(CIRCLE) == pytest.approx(1, abs=1e-4)
        assert convex_hull_ratio(CIRCLE) == pytest.approx(1)
        assert schwartzberg(CIRCLE) == pytest.approx(1, abs=1e-4)

    def test_square(self):
        assert polsby_popper(SQUARE) == pytest.approx(math.pi / 4)
        assert reock(SQUARE) == pytest.approx(2 / math.pi)  # circumcircle area is pi/2
        assert convex_hull_ratio(SQUARE) == pytest.approx(1)
        assert schwartzberg(SQUARE) == pytest.approx(1 / math.sqrt(math.pi / 4))

    def test_l_shape_has_a_bite_out_of_its_hull(self):
        assert convex_hull_ratio(L_SHAPE) == pytest.approx(3 / 3.5)
        assert polsby_popper(L_SHAPE) == pytest.approx(4 * math.pi * 3 / 8**2)

    def test_multi_part_district_uses_totals_and_one_hull_and_circle(self):
        # Area 2, perimeter 8, hull 4 x 1, enclosing circle radius sqrt(2^2 + 0.5^2).
        assert polsby_popper(TWO_SQUARES) == pytest.approx(math.pi / 8)
        assert convex_hull_ratio(TWO_SQUARES) == pytest.approx(0.5)
        assert reock(TWO_SQUARES) == pytest.approx(2 / (math.pi * 4.25))

    def test_less_compact_shapes_score_lower(self):
        assert polsby_popper(CIRCLE) > polsby_popper(SQUARE) > polsby_popper(L_SHAPE)


def square_in_lonlat(lon: float, lat: float, side_m: float = 50_000) -> Polygon:
    """A square of side_m meters centered on (lon, lat), expressed in lon/lat."""
    crs = local_crs(Point(lon, lat))
    to_lonlat = Transformer.from_crs(crs, "EPSG:4269", always_xy=True)
    h = side_m / 2
    corners = [(-h, -h), (h, -h), (h, h), (-h, h)]
    # Densify so the edges stay straight lines on the ground, not in lon/lat.
    edge = shapely.segmentize(Polygon(corners), side_m / 100)
    return shapely.transform(edge, lambda xy: list(zip(*to_lonlat.transform(*xy.T), strict=True)))


class TestCompactness:
    def test_returns_all_four_scores_for_a_lonlat_district(self):
        scores = compactness(square_in_lonlat(-69.5, 45.0), "EPSG:4269")
        assert set(scores) == {"polsby_popper", "reock", "convex_hull", "schwartzberg"}
        assert scores["polsby_popper"] == pytest.approx(math.pi / 4, rel=1e-3)
        assert scores["reock"] == pytest.approx(2 / math.pi, rel=1e-3)

    def test_same_shape_scores_the_same_in_maine_and_alaska(self):
        maine = compactness(square_in_lonlat(-69.5, 45.0), "EPSG:4269")
        alaska = compactness(square_in_lonlat(-150.0, 64.0), "EPSG:4269")
        for name in maine:
            assert alaska[name] == pytest.approx(maine[name], rel=1e-3)

    def test_raw_lonlat_would_have_been_wrong(self):
        # Guard for the projection step: in raw degrees an Alaska square looks stretched.
        assert polsby_popper(square_in_lonlat(-150.0, 64.0)) < 0.7


class TestMeasuredAgainstLand:
    """Reock and convex hull count only the part of the circle or hull that is on land."""

    COAST = box(-10, -10, 10, 0)  # land is everything south of y = 0

    def test_inland_district_is_unchanged(self):
        land = box(-10, -10, 10, 10)
        assert reock(SQUARE, land) == pytest.approx(reock(SQUARE), rel=1e-3)
        assert convex_hull_ratio(L_SHAPE, land) == pytest.approx(convex_hull_ratio(L_SHAPE))

    def test_half_disk_on_a_straight_coast_is_perfectly_round_on_land(self):
        half_disk = CIRCLE.intersection(self.COAST)
        assert reock(half_disk) == pytest.approx(0.5, abs=1e-3)
        assert reock(half_disk, self.COAST) == pytest.approx(1, abs=1e-3)

    def test_water_between_islands_does_not_count(self):
        assert convex_hull_ratio(TWO_SQUARES) == pytest.approx(0.5)
        assert convex_hull_ratio(TWO_SQUARES, TWO_SQUARES) == pytest.approx(1)
        assert reock(TWO_SQUARES, TWO_SQUARES) == pytest.approx(1)

    def test_wasting_usable_land_still_counts(self):
        everywhere = box(-10, -10, 10, 10)
        assert convex_hull_ratio(L_SHAPE, everywhere) == pytest.approx(3 / 3.5)

    def test_compactness_projects_the_land_with_the_district(self):
        district = square_in_lonlat(-69.5, 45.0)
        coast = shapely.box(-69.5, 40, -60, 50)  # land only east of the square's center
        half = district.intersection(coast)
        scores = compactness(half, "EPSG:4269", coast)
        assert scores["convex_hull"] == pytest.approx(1, abs=1e-3)
        assert scores["polsby_popper"] == pytest.approx(
            compactness(half, "EPSG:4269")["polsby_popper"]
        )

    def test_district_poking_past_the_land_still_scores_at_most_one(self):
        land = box(0, 0, 1, 1)
        district = box(0, 0, 1.001, 1)  # a hair over the edge, as rounding can leave it
        assert convex_hull_ratio(district, land) <= 1
        assert reock(district, land) <= 1

    def test_compactness_counts_projected_land_a_district_leaves_out(self):
        # The L's bite is land, so the hull ratio stays below 1. If the land weren't
        # projected with the district, only the district would count and give 1.
        lon, lat, s = -69.5, 45.0, 0.2
        el = Polygon([(lon, lat), (lon + 2 * s, lat), (lon + 2 * s, lat + s), (lon + s, lat + s),
                      (lon + s, lat + 2 * s), (lon, lat + 2 * s)])  # fmt: skip
        land = shapely.box(lon - 1, lat - 1, lon + 1, lat + 1)
        assert compactness(el, "EPSG:4269", land)["convex_hull"] == pytest.approx(3 / 3.5, rel=0.01)
