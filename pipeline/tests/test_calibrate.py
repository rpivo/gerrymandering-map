import geopandas as gpd
import pytest
from shapely.geometry import MultiPolygon, box
from test_generalize import MAIN_1, MAIN_2, frame, zigzag_pair

from gerry.calibrate import (
    CALIBRATION_STATES,
    clipping_artifacts,
    load_tiger_districts,
    sweep,
    tiger_source,
    touching_piece_sizes,
)
from gerry.states import STATES_BY_USPS


def test_tiger_sources_cover_the_calibration_states():
    assert len(CALIBRATION_STATES) == 12
    for state in CALIBRATION_STATES:
        source = tiger_source(state)
        fips = STATES_BY_USPS[state].fips
        assert source.id == f"census-tiger-cd119-2025-{fips}"
        assert (
            source.url == f"https://www2.census.gov/geo/tiger/TIGER2025/CD/tl_2025_{fips}_cd119.zip"
        )


def test_load_tiger_districts_drops_unassigned_water(tmp_path):
    path = tmp_path / "tiger.gpkg"
    gpd.GeoDataFrame(
        {"STATEFP": ["23", "23", "23"], "CD119FP": ["01", "02", "ZZ"]},
        geometry=[box(0, 0, 1, 1), box(1, 0, 2, 1), box(2, 0, 3, 1)],
        crs="EPSG:4269",
    ).to_file(path)
    assert list(load_tiger_districts(path)["district_id"]) == ["ME-01", "ME-02"]


def test_sweep_of_identical_maps_gives_ratio_one():
    reference = frame("ME", [MAIN_1, MAIN_2])
    rows = sweep(reference, reference, (0, 75))
    assert [r["tolerance_m"] for r in rows] == [0, 75]
    for r in rows:
        assert r["pp_ratio_median"] == pytest.approx(1)
        assert r["points_per_km"] > 0


def test_sweep_shows_simplification_closing_the_gap():
    detailed = zigzag_pair()
    straight = frame("ME", [box(0, 40, 1, 41), box(1, 40, 2, 41)])
    rows = {r["tolerance_m"]: r for r in sweep(detailed, straight, (0, 75))}
    assert rows[0]["pp_ratio_median"] < 0.99
    assert rows[75]["pp_ratio_median"] == pytest.approx(1, abs=0.005)


def test_touching_piece_sizes_counts_slivers_not_islands():
    sliver = box(1.5, 41, 1.502, 41.002)
    island = box(0.5, 41.5, 0.502, 41.502)
    districts = frame("ME", [MultiPolygon([MAIN_1, sliver, island]), MAIN_2])
    sizes = touching_piece_sizes(districts)
    assert len(sizes) == 1
    assert sizes[0] == pytest.approx(0.037, rel=0.1)


def test_clipping_artifacts_are_pieces_with_no_match_in_the_reference():
    real_piece = box(1.5, 41, 1.6, 41.1)  # in both versions, slightly different sizes
    sliver = box(1.2, 41, 1.202, 41.002)  # only in the detailed version
    reference = frame("ME", [MultiPolygon([MAIN_1, real_piece]), MAIN_2])
    detailed = frame("ME", [MultiPolygon([MAIN_1, box(1.5, 41, 1.601, 41.1), sliver]), MAIN_2])
    artifacts = clipping_artifacts(detailed, reference)
    assert len(artifacts) == 1
    assert artifacts[0] == pytest.approx(0.037, rel=0.1)
