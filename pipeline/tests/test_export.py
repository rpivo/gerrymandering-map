import json
import math

import pandas as pd
import pytest

from gerry.export import district_records, write_districts_json

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
