import geopandas as gpd
import pytest
from shapely.geometry import MultiPolygon, box

from gerry.replacement import (
    check_audit_match,
    clip_to_land,
    coverage_gap,
    normalize_state_map,
    replace_states,
)

# Maine has two seats, which keeps the fixtures small.
LAND = box(0, 0, 2, 1)  # the state's shoreline-clipped outline


def raw_map(values, geometries, field="DISTRICT", crs="EPSG:4269") -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame({field: values, "geometry": geometries}, crs=crs)


def halves(extend_into_water: float = 0.0):
    """Two districts splitting LAND down the middle, optionally extending past it."""
    e = extend_into_water
    return [box(0 - e, 0 - e, 1, 1 + e), box(1, 0 - e, 2 + e, 1 + e)]


class TestNormalizeStateMap:
    @pytest.mark.parametrize("values", [[1, 2], ["1", "2"], ["01", "02"], [1.0, 2.0]])
    def test_reads_district_numbers_in_common_formats(self, values):
        gdf = normalize_state_map(raw_map(values, halves()), "ME", "DISTRICT")
        assert list(gdf["district_id"]) == ["ME-01", "ME-02"]
        assert list(gdf["number"]) == [1, 2]
        assert list(gdf["state"]) == ["ME", "ME"]
        assert list(gdf.columns) == ["district_id", "state", "number", "geometry"]

    def test_merges_districts_split_across_rows(self):
        left, right = halves()
        pieces = [box(0, 0, 1, 0.5), box(0, 0.5, 1, 1), right]
        gdf = normalize_state_map(raw_map([1, 1, 2], pieces), "ME", "DISTRICT")
        assert list(gdf["district_id"]) == ["ME-01", "ME-02"]
        assert gdf.geometry.iloc[0].area == pytest.approx(left.area)

    def test_reprojects_to_the_census_crs(self):
        projected = raw_map([1, 2], halves()).set_crs("EPSG:4269").to_crs("EPSG:3857")
        gdf = normalize_state_map(projected, "ME", "DISTRICT")
        assert gdf.crs == "EPSG:4269"
        assert gdf.geometry.iloc[0].bounds == pytest.approx((0, 0, 1, 1), abs=1e-6)

    def test_uses_the_named_field(self):
        gdf = normalize_state_map(raw_map([2, 1], halves(), field="District_N"), "ME", "District_N")
        assert list(gdf["number"]) == [1, 2]

    @pytest.mark.parametrize("values", [[1, 3], [0, 1], [1, "AL"], [1, None]])
    def test_rejects_numbers_outside_the_states_seats(self, values):
        with pytest.raises(ValueError, match="ME"):
            normalize_state_map(raw_map(values, halves()), "ME", "DISTRICT")

    def test_rejects_a_missing_district(self):
        with pytest.raises(ValueError, match=r"ME: missing districts \[2\]"):
            normalize_state_map(raw_map([1, 1], halves()), "ME", "DISTRICT")

    def test_rejects_a_missing_field(self):
        with pytest.raises(ValueError, match="DISTRICT"):
            normalize_state_map(raw_map([1, 2], halves(), field="CD"), "ME", "DISTRICT")


def test_clip_to_land_trims_water_and_keeps_polygons_only():
    gdf = normalize_state_map(raw_map([1, 2], halves(extend_into_water=0.5)), "ME", "DISTRICT")
    clipped = clip_to_land(gdf, LAND)
    assert clipped.geometry.iloc[0].equals(box(0, 0, 1, 1))
    assert clipped.geometry.iloc[1].equals(box(1, 0, 2, 1))
    assert set(clipped.geom_type) <= {"Polygon", "MultiPolygon"}
    assert gdf.geometry.iloc[0].area > 1  # the input is not modified


def test_clip_to_land_drops_points_and_lines_where_shapes_only_touch():
    # District 2 overlaps the land's right half and also touches its top-left corner,
    # so the raw intersection is a GeometryCollection of a polygon and a point.
    corner_touch = MultiPolygon([box(1, 0, 3, 1), box(-1, 1, 0, 2)])
    assert LAND.intersection(corner_touch).geom_type == "GeometryCollection"
    gdf = normalize_state_map(raw_map([1, 2], [box(0, 0, 1, 1), corner_touch]), "ME", "DISTRICT")
    clipped = clip_to_land(gdf, LAND)
    assert list(clipped.geom_type) == ["Polygon", "Polygon"]
    assert clipped.geometry.iloc[1].equals(box(1, 0, 2, 1))


class TestCoverageGap:
    def test_full_coverage_has_no_gap(self):
        gdf = normalize_state_map(raw_map([1, 2], halves()), "ME", "DISTRICT")
        assert coverage_gap(gdf, LAND) == pytest.approx(0, abs=1e-9)

    def test_missing_land_is_measured_as_a_share_of_the_state(self):
        gdf = normalize_state_map(
            raw_map([1, 2], [box(0, 0, 1, 1), box(1, 0, 1.5, 1)]), "ME", "DISTRICT"
        )
        assert coverage_gap(gdf, LAND) == pytest.approx(0.25, rel=0.01)


def test_replace_states_swaps_only_the_named_states(valid_districts):
    me = normalize_state_map(raw_map([1, 2], halves()), "ME", "DISTRICT")
    me["map_source"] = "maine-2026"
    result = replace_states(valid_districts.assign(map_source="census"), {"ME": me})
    assert len(result) == len(valid_districts)
    assert list(result.loc[result["state"] == "ME", "map_source"]) == ["maine-2026"] * 2
    assert set(result.loc[result["state"] != "ME", "map_source"]) == {"census"}
    assert list(result["district_id"]) == sorted(result["district_id"])
    assert list(result.index) == list(range(len(result)))


def test_replace_states_rejects_a_replacement_for_the_wrong_state(valid_districts):
    me = normalize_state_map(raw_map([1, 2], halves()), "ME", "DISTRICT")
    with pytest.raises(ValueError, match="NH"):
        replace_states(valid_districts, {"NH": me})


class TestCheckAuditMatch:
    def test_matching_sets_have_no_problems(self):
        assert check_audit_match({"yes": ["TX", "UT"], "unclear": []}, {"TX", "UT"}) == []

    def test_changed_state_without_a_replacement(self):
        problems = check_audit_match({"yes": ["TX", "UT"], "unclear": []}, {"TX"})
        assert any("UT" in p and "no replacement" in p for p in problems)

    def test_replacement_for_an_unchanged_state(self):
        problems = check_audit_match({"yes": ["TX"], "unclear": []}, {"TX", "OK"})
        assert any("OK" in p and "unchanged" in p for p in problems)

    def test_pending_changed_state_is_allowed_without_a_replacement(self):
        assert check_audit_match({"yes": ["OH", "TX"], "unclear": []}, {"TX"}, {"OH"}) == []

    def test_pending_state_must_be_one_the_audit_marks_changed(self):
        problems = check_audit_match({"yes": ["TX"], "unclear": []}, {"TX"}, {"OK"})
        assert any("OK" in p and "pending" in p for p in problems)

    def test_state_cannot_be_both_pending_and_registered(self):
        problems = check_audit_match({"yes": ["OH"], "unclear": []}, {"OH"}, {"OH"})
        assert any("OH" in p and "pending" in p for p in problems)

    def test_unclear_states_must_be_resolved_first(self):
        problems = check_audit_match({"yes": [], "unclear": ["AL"]}, set())
        assert any("AL" in p and "unclear" in p for p in problems)
