import json
import math

import pandas as pd
import pytest

from gerry.export import district_records, state_records, write_districts_json, write_shapes_json

CENSUS = "census-cd119-cb-2025-500k"


def scores_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "district_id": ["TX-35", "WY-AL"],
            "state": ["TX", "WY"],
            "number": pd.array([35, None], dtype="Int64"),
            "map_source": ["tx-2025-planc2333-congress", CENSUS],
            "at_large": [False, True],
            "polsby_popper": [0.123456789, 0.6],
            "reock": [0.25, 0.5],
            "convex_hull": [0.5, 0.9],
            "schwartzberg": [1 / math.sqrt(0.123456789), 1 / math.sqrt(0.6)],
            "polsby_popper_pct": [3.4567, float("nan")],
            "reock_pct": [10.0, float("nan")],
            "convex_hull_pct": [5.0, float("nan")],
            "compactness_pct": [6.15, float("nan")],
            "irregularity": pd.array([94, None], dtype="Int64"),
            "rank_national": pd.array([12, None], dtype="Int64"),
            "rank_state": pd.array([2, None], dtype="Int64"),
        }
    )


def test_records_round_numbers_and_use_null_for_missing_values():
    tx, wy = district_records(scores_frame())
    assert tx["id"] == "TX-35"
    assert tx["number"] == 35
    assert tx["polsby_popper"] == 0.1235
    assert tx["polsby_popper_pct"] == 3.5
    assert tx["irregularity"] == 94
    assert tx["rank_national"] == 12
    assert wy["number"] is None
    assert wy["irregularity"] is None
    assert wy["polsby_popper_pct"] is None
    assert wy["polsby_popper"] == 0.6


def test_records_flag_districts_redrawn_for_2026():
    tx, wy = district_records(scores_frame())
    assert tx["redrawn_2026"] is True
    assert wy["redrawn_2026"] is False
    assert wy["at_large"] is True


def test_records_have_plain_json_types():
    for record in district_records(scores_frame()):
        for value in record.values():
            assert value is None or type(value) in (str, int, float, bool)


def test_written_json_is_stable_and_complete(tmp_path):
    path = tmp_path / "site" / "src" / "data" / "districts.json"
    write_districts_json(scores_frame(), path)
    first = path.read_text()
    write_districts_json(scores_frame(), path)
    assert path.read_text() == first
    data = json.loads(first)
    assert data["count"] == 2
    assert [d["id"] for d in data["districts"]] == ["TX-35", "WY-AL"]
    assert "irregularity" in data["fields"]


def test_records_reject_an_unexpected_nan_in_a_scored_district():
    frame = scores_frame()
    frame.loc[0, "reock"] = float("nan")
    with pytest.raises(ValueError, match="TX-35"):
        district_records(frame)


def test_records_reject_a_missing_score_for_a_district_with_lines():
    frame = scores_frame()
    frame["irregularity"] = pd.array([None, None], dtype="Int64")
    with pytest.raises(ValueError, match="TX-35.*irregularity"):
        district_records(frame)


def test_shapes_json_has_card_and_page_outlines_and_state_maps(tmp_path):
    import geopandas as gpd
    from shapely.geometry import box

    districts = gpd.GeoDataFrame(
        {"district_id": ["ME-01", "ME-02", "WY-AL"], "state": ["ME", "ME", "WY"]},
        geometry=[box(-70, 44, -69, 45), box(-69, 44, -68, 45), box(-110, 41, -104, 45)],
        crs="EPSG:4269",
    )
    path = tmp_path / "shapes.json"
    write_shapes_json(districts, path)
    data = json.loads(path.read_text())
    assert set(data["districts"]) == {"ME-01", "ME-02", "WY-AL"}
    for outline in data["districts"]["ME-01"].values():
        assert outline["viewBox"].startswith("0 0 ") and outline["d"].startswith("M")
    assert set(data["districts"]["ME-01"]) == {"card", "page"}
    assert set(data["states"]) == {"ME", "WY"}
    assert set(data["states"]["ME"]["paths"]) == {"ME-01", "ME-02"}


def test_state_records_join_names_seats_and_the_audit():
    from test_state_audit import row

    audit = [
        row("TX", changed_since_2024="yes", first_used="2026", enacted="2025-08-29"),
        row("WY"),
    ]
    tx, wy = state_records(audit)
    assert tx["state"] == "TX" and tx["name"] == "Texas" and tx["seats"] == 38
    assert tx["changed_since_2024"] is True
    assert tx["map_in_effect_2026"] == "2021 enacted plan"
    assert tx["source_url"] == "https://example.gov/maps"
    assert wy["at_large"] is True and wy["changed_since_2024"] is False
    assert wy["enacted"] is None


def test_sources_json_lists_every_source_with_its_role(tmp_path):
    from gerry.export import write_sources_json

    entries = {
        "census-tiger-cd119-2025-04": {"id": "census-tiger-cd119-2025-04", "url": "https://c/t",
            "publisher": "U.S. Census Bureau", "license": "PD", "description": "TIGER AZ",
            "downloaded": "2026-11-04", "sha256": "a" * 64},
        "census-cd119-cb-2025-500k": {"id": "census-cd119-cb-2025-500k", "url": "https://c/cb",
            "publisher": "U.S. Census Bureau", "license": "PD", "description": "CD119",
            "downloaded": "2026-11-04", "sha256": "b" * 64},
    }  # fmt: skip
    path = tmp_path / "sources.json"
    write_sources_json(entries, path)
    data = json.loads(path.read_text())
    assert [s["id"] for s in data["sources"]] == [
        "census-cd119-cb-2025-500k",
        "census-tiger-cd119-2025-04",
    ]
    roles = {s["id"]: s["role"] for s in data["sources"]}
    assert roles == {
        "census-cd119-cb-2025-500k": "boundaries",
        "census-tiger-cd119-2025-04": "calibration",
    }
    assert "sha256" not in data["sources"][0]
    assert data["sources"][0]["downloaded"] == "2026-11-04"


def test_sources_json_marks_election_results_as_votes(tmp_path):
    from gerry.export import write_sources_json

    entry = {"id": "medsl-president-precinct-2024", "url": "https://d/v", "publisher": "MIT",
        "license": "CC0", "description": "President 2024", "downloaded": "2026-11-05",
        "sha256": "c" * 64}  # fmt: skip
    path = tmp_path / "sources.json"
    write_sources_json({entry["id"]: entry}, path)
    assert json.loads(path.read_text())["sources"][0]["role"] == "votes"


def test_sources_json_marks_other_results_ending_in_votes_as_votes(tmp_path):
    from gerry.export import write_sources_json

    entry = {"id": "wa-king-county-precincts-2024-votes", "url": "https://k/c", "publisher": "KC",
        "license": "PD", "description": "Precincts", "downloaded": "2026-11-05",
        "sha256": "d" * 64}  # fmt: skip
    path = tmp_path / "sources.json"
    write_sources_json({entry["id"]: entry}, path)
    assert json.loads(path.read_text())["sources"][0]["role"] == "votes"
