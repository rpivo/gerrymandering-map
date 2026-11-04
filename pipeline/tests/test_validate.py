import geopandas as gpd
import pandas as pd
from shapely.geometry import Polygon, box
from shapely.geometry.base import BaseGeometry

from gerry.validate import validate_districts


def replace_geometry(gdf: gpd.GeoDataFrame, district: str, geometry: BaseGeometry | None):
    gdf.loc[gdf["district_id"] == district, "geometry"] = geometry


def test_valid_set_has_no_problems(valid_districts):
    assert validate_districts(valid_districts) == []


def test_missing_district_is_reported_for_total_and_state(valid_districts):
    problems = validate_districts(valid_districts[valid_districts["district_id"] != "TX-35"])
    assert any("434 districts" in p and "435" in p for p in problems)
    assert any(p.startswith("TX:") and "37" in p and "38" in p for p in problems)


def test_missing_state_is_reported(valid_districts):
    problems = validate_districts(valid_districts[valid_districts["state"] != "WY"])
    assert any(p.startswith("WY:") and "0 districts" in p for p in problems)


def test_unknown_state_is_reported(valid_districts):
    extra = valid_districts[valid_districts["district_id"] == "WY-AL"].copy()
    extra["district_id"], extra["state"] = "DC-AL", "DC"
    problems = validate_districts(pd.concat([valid_districts, extra], ignore_index=True))
    assert any("DC" in p and "not a state" in p for p in problems)


def test_duplicate_id_is_reported(valid_districts):
    dup = valid_districts.copy()
    dup.loc[dup["district_id"] == "TX-35", ["district_id", "number"]] = ["TX-34", 34]
    problems = validate_districts(dup)
    assert any("duplicate" in p.lower() and "TX-34" in p for p in problems)
    assert any(p.startswith("TX:") and "35" in p and "missing" in p for p in problems)


def test_at_large_state_must_not_be_numbered(valid_districts):
    bad = valid_districts.copy()
    bad.loc[bad["district_id"] == "WY-AL", ["district_id", "number"]] = ["WY-01", 1]
    assert any(p.startswith("WY:") and "at-large" in p for p in validate_districts(bad))


def test_multi_seat_state_must_be_numbered(valid_districts):
    bad = valid_districts.copy()
    bad.loc[bad["district_id"] == "ME-02", ["district_id", "number"]] = ["ME-AL", pd.NA]
    problems = validate_districts(bad)
    assert any(p.startswith("ME:") and "2" in p and "missing" in p for p in problems)


def test_invalid_geometry_is_reported_with_the_reason(valid_districts):
    bowtie = Polygon([(-120, 30), (-119.9, 30.1), (-119.9, 30), (-120, 30.1)])
    replace_geometry(valid_districts, "TX-35", bowtie)
    problems = validate_districts(valid_districts)
    assert any(
        "TX-35" in p and "invalid geometry" in p and "Self-intersection" in p for p in problems
    )


def test_empty_and_missing_geometry_are_reported(valid_districts):
    replace_geometry(valid_districts, "TX-35", Polygon())
    replace_geometry(valid_districts, "TX-34", None)
    problems = validate_districts(valid_districts)
    assert any("TX-35" in p and "empty geometry" in p for p in problems)
    assert any("TX-34" in p and "empty geometry" in p for p in problems)


def test_overlapping_districts_in_a_state_are_reported(valid_districts):
    tx1 = valid_districts.loc[valid_districts["district_id"] == "TX-01", "geometry"].iloc[0]
    minx, miny, maxx, maxy = tx1.bounds
    replace_geometry(valid_districts, "TX-02", box(minx + 0.025, miny, maxx + 0.025, maxy))
    problems = validate_districts(valid_districts)
    assert any("TX-01" in p and "TX-02" in p and "overlap" in p for p in problems)


def test_districts_sharing_a_border_do_not_overlap(valid_districts):
    tx1 = valid_districts.loc[valid_districts["district_id"] == "TX-01", "geometry"].iloc[0]
    minx, miny, maxx, maxy = tx1.bounds
    replace_geometry(valid_districts, "TX-02", box(maxx, miny, maxx + 0.05, maxy))
    assert validate_districts(valid_districts) == []


def test_tiny_slivers_below_tolerance_are_allowed(valid_districts):
    tx1 = valid_districts.loc[valid_districts["district_id"] == "TX-01", "geometry"].iloc[0]
    minx, miny, maxx, maxy = tx1.bounds
    # About 0.005 km2 of overlap, below the 0.01 km2 tolerance.
    replace_geometry(valid_districts, "TX-02", box(maxx - 0.00001, miny, maxx + 0.05, maxy))
    assert validate_districts(valid_districts) == []
