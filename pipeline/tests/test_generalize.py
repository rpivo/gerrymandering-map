import geopandas as gpd
import pytest
import shapely
from shapely.geometry import MultiPolygon, Polygon, box

from gerry.generalize import absorb_fragments, simplify_to_census

# Boxes near 40N: 0.002 degrees is about 0.03 km2 (a sliver), 0.02 is about 3.7 km2.
MAIN_1 = box(0, 40, 1, 41)
MAIN_2 = box(1, 40, 2, 41)


def frame(state, geometries):
    return gpd.GeoDataFrame(
        {
            "district_id": [f"{state}-{n:02d}" for n in range(1, len(geometries) + 1)],
            "state": state,
            "geometry": geometries,
        },
        crs="EPSG:4269",
    )


class TestAbsorbFragments:
    def test_small_piece_touching_a_neighbour_joins_that_neighbour(self):
        sliver = box(1.5, 41, 1.502, 41.002)  # sits on top of district 2
        result = absorb_fragments(frame("ME", [MultiPolygon([MAIN_1, sliver]), MAIN_2]))
        assert result.geometry.iloc[0].equals(MAIN_1)
        assert result.geometry.iloc[1].geom_type == "Polygon"
        assert result.geometry.iloc[1].area == pytest.approx(MAIN_2.area + sliver.area)

    def test_tiny_island_below_census_detail_is_dropped(self):
        # About 0.0009 km2: the Census 1:500,000 file has no piece under 0.01 km2.
        speck = box(0.5, 41.5, 0.5003, 41.5003)
        result = absorb_fragments(frame("ME", [MultiPolygon([MAIN_1, speck]), MAIN_2]))
        assert result.geometry.iloc[0].equals(MAIN_1)
        assert result.geometry.iloc[1].equals(MAIN_2)

    def test_small_island_touching_no_district_stays(self):
        island = box(0.5, 41.5, 0.502, 41.502)
        result = absorb_fragments(frame("ME", [MultiPolygon([MAIN_1, island]), MAIN_2]))
        assert result.geometry.iloc[0].equals(MultiPolygon([MAIN_1, island]))
        assert result.geometry.iloc[1].equals(MAIN_2)

    def test_small_island_of_the_last_district_stays(self):
        # Processed last, so a wrongly moved island has no later pass to move it back.
        island = box(1.5, 41.5, 1.502, 41.502)
        result = absorb_fragments(frame("ME", [MAIN_1, MultiPolygon([MAIN_2, island])]))
        assert result.geometry.iloc[0].equals(MAIN_1)
        assert result.geometry.iloc[1].equals(MultiPolygon([MAIN_2, island]))

    def test_large_piece_touching_a_neighbour_stays(self):
        piece = box(1.5, 41, 1.52, 41.02)
        result = absorb_fragments(frame("ME", [MultiPolygon([MAIN_1, piece]), MAIN_2]))
        assert len(shapely.get_parts(result.geometry.iloc[0])) == 2

    def test_piece_touching_two_districts_joins_the_longer_shared_border(self):
        main_3 = box(2, 40, 3, 41)
        # Straddles the 2|3 border at x=2: 0.0015 degrees over district 2, 0.0005 over 3.
        sliver = box(1.9985, 41, 2.0005, 41.002)
        result = absorb_fragments(frame("NE", [MultiPolygon([MAIN_1, sliver]), MAIN_2, main_3]))
        assert result.geometry.iloc[1].area == pytest.approx(MAIN_2.area + sliver.area)
        assert result.geometry.iloc[2].equals(main_3)

    def test_only_districts_in_the_same_state_count_as_neighbours(self):
        sliver = box(1.5, 41, 1.502, 41.002)
        me = frame("ME", [MultiPolygon([MAIN_1, sliver]), box(5, 40, 6, 41)])
        nh = frame("NH", [MAIN_2, box(7, 40, 8, 41)])
        both = gpd.GeoDataFrame(
            list(me.itertuples(index=False)) + list(nh.itertuples(index=False)),
            columns=me.columns,
            crs=me.crs,
        )
        result = absorb_fragments(both)
        assert result.geometry.iloc[0].equals(MultiPolygon([MAIN_1, sliver]))

    def test_does_not_modify_the_input(self):
        sliver = box(1.5, 41, 1.502, 41.002)
        source = frame("ME", [MultiPolygon([MAIN_1, sliver]), MAIN_2])
        absorb_fragments(source)
        assert source.geometry.iloc[0].geom_type == "MultiPolygon"


def zigzag_pair(teeth=2000):
    """Two districts split by a line zigzagging about 17 m every 55 m (detail a 1:500,000
    map drops), inside the outline box(0,40,2,41)."""
    ys = [40 + i / teeth for i in range(teeth + 1)]
    line = [(1 + (0.0002 if i % 2 else -0.0002), y) for i, y in enumerate(ys)]
    left = Polygon([(0, 40), *line, (0, 41)])
    right = Polygon([(2, 40), (2, 41), *reversed(line)])
    return frame("ME", [left, right])


def wiggly_coast_pair(teeth=2000):
    """Two districts with a straight shared border at x=1 and a finely wiggling outer
    coast along x=0, like a state outline that is already at the Census level."""
    coast = [(0.0002 if i % 2 else 0, 40 + i / teeth) for i in range(teeth + 1)]
    left = Polygon([*coast, (1, 41), (1, 40)])
    return frame("ME", [left, box(1, 40, 2, 41)])


class TestSimplifyToCensus:
    def test_removes_fine_detail_from_internal_borders(self):
        source = zigzag_pair()
        result = simplify_to_census(source, tolerance_m=75)
        before = sum(shapely.get_num_coordinates(g) for g in source.geometry)
        after = sum(shapely.get_num_coordinates(g) for g in result.geometry)
        assert after < before / 10

    def test_keeps_borders_shared_with_no_gaps_or_overlaps(self):
        result = simplify_to_census(zigzag_pair(), tolerance_m=75)
        left, right = result.geometry
        assert left.intersection(right).area == pytest.approx(0, abs=1e-12)
        assert shapely.union(left, right).area == pytest.approx(box(0, 40, 2, 41).area, rel=1e-9)

    @pytest.mark.parametrize("make", [zigzag_pair, wiggly_coast_pair])
    def test_leaves_the_outer_edge_alone(self, make):
        source = make()
        result = simplify_to_census(source, tolerance_m=75)
        before = shapely.union_all(source.geometry.to_numpy())
        after = shapely.union_all(result.geometry.to_numpy())
        # Projecting there and back leaves float noise, so compare by distance.
        assert after.hausdorff_distance(before) < 1e-9
        assert shapely.get_num_coordinates(after) == shapely.get_num_coordinates(before)

    def test_zero_tolerance_changes_nothing(self):
        source = zigzag_pair()
        result = simplify_to_census(source, tolerance_m=0)
        assert all(a.equals(b) for a, b in zip(source.geometry, result.geometry, strict=True))

    def test_keeps_the_crs_and_does_not_modify_the_input(self):
        source = zigzag_pair()
        coordinates = sum(shapely.get_num_coordinates(g) for g in source.geometry)
        result = simplify_to_census(source, tolerance_m=75)
        assert result.crs == source.crs
        assert sum(shapely.get_num_coordinates(g) for g in source.geometry) == coordinates
