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
            "state_edge_share": [0.41766, 1.0],
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


def test_records_carry_the_share_of_the_border_on_the_state_edge():
    tx, wy = district_records(scores_frame())
    assert tx["state_edge_share"] == 0.418
    assert wy["state_edge_share"] == 1.0


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


def fairness_table(*rows: tuple) -> pd.DataFrame:
    columns = ["state", "districts", "dem_vote_share", "dem_seats", "efficiency_gap",
               "mean_median", "declination", "method"]  # fmt: skip
    return pd.DataFrame(list(rows), columns=columns)


AZ = ("AZ", 9, 0.472148992, 3, 0.196312038, 0.005990420, 0.250274538, "precinct join")
CT = ("CT", 5, 0.573782324, 5, -0.352435350, 0.003201440, math.nan, "precinct join")


def fairness_by_state(table, audit) -> dict[str, dict]:
    from gerry.export import fairness_records

    return {r["state"]: r for r in fairness_records(table, audit)}


def test_fairness_records_carry_rounded_scores_and_the_seat_count():
    from test_state_audit import row

    az = fairness_by_state(fairness_table(AZ), [row("AZ")])["AZ"]
    assert az == {
        "state": "AZ",
        "status": "scored",
        "districts": 9,
        "dem_vote_share": 0.4721,
        "dem_seats": 3,
        "one_party_won_every_district": False,
        "efficiency_gap": 0.1963,
        "mean_median": 0.006,
        "declination": 0.2503,
        "method": "precinct join",
    }


def test_a_state_one_party_swept_has_no_declination_and_says_so():
    from test_state_audit import row

    ct = fairness_by_state(fairness_table(CT), [row("CT")])["CT"]
    assert ct["one_party_won_every_district"] is True
    assert ct["declination"] is None
    assert ct["efficiency_gap"] == -0.3524


def test_a_republican_sweep_is_a_sweep_too():
    from test_state_audit import row

    ar = ("AR", 4, 0.343286, 0, 0.186573, 0.005211, math.nan, "precinct join")
    assert fairness_by_state(fairness_table(ar), [row("AR")])["AR"]["one_party_won_every_district"]


def test_unscored_states_get_the_reason_and_no_scores():
    from test_state_audit import row

    audit = [
        row("WY"),
        row("NH"),
        row("UT", changed_since_2024="yes", first_used="2026", enacted="2025-11-10"),
        row("OR"),
    ]
    out = fairness_by_state(fairness_table(), audit)
    assert {s: r["status"] for s, r in out.items()} == {
        "WY": "at_large",
        "NH": "too_few_districts",
        "UT": "awaiting_2026_results",
        "OR": "no_vote_data",
    }
    for record in out.values():
        assert record["efficiency_gap"] is None and record["dem_seats"] is None
        assert record["one_party_won_every_district"] is None
        assert set(record) == set(fairness_by_state(fairness_table(AZ), [row("AZ")])["AZ"])


def test_a_scored_redrawn_state_is_scored():
    from test_state_audit import row

    tx_row = row("TX", changed_since_2024="yes", first_used="2026", enacted="2025-08-29")
    tx = ("TX", 38, 0.43, 13, 0.194, 0.03, 0.3, "official report")
    assert fairness_by_state(fairness_table(tx), [tx_row])["TX"]["status"] == "scored"


def test_fairness_records_follow_the_audit_order():
    from test_state_audit import row

    from gerry.export import fairness_records

    records = fairness_records(fairness_table(CT, AZ), [row("AZ"), row("CT"), row("WY")])
    assert [r["state"] for r in records] == ["AZ", "CT", "WY"]


def test_fairness_json_is_deterministic_and_described(tmp_path):
    from test_state_audit import row

    from gerry.export import write_fairness_json

    path = tmp_path / "fairness.json"
    write_fairness_json(fairness_table(AZ, CT), [row("AZ"), row("CT")], path)
    first = path.read_bytes()
    write_fairness_json(fairness_table(CT, AZ), [row("AZ"), row("CT")], path)
    assert path.read_bytes() == first
    data = json.loads(first)
    assert data["count"] == 2 and len(data["states"]) == 2
    assert "Positive favors Republicans" in data["description"]
    assert "2024 presidential" in data["description"]
    assert "NaN" not in first.decode()


@pytest.mark.parametrize(
    ("source_id", "role"),
    [
        ("census-pl94171-2020-48", "population"),
        ("census-blocks-2020-39", "boundaries"),
        ("medsl-president-precinct-2024", "votes"),
        ("tx-planc2333-president-2024-votes", "votes"),
        ("census-tiger-cd119-2025-04", "calibration"),
    ],
)
def test_source_roles_by_id(source_id, role):
    from gerry.export import _source_role

    assert _source_role(source_id) == role
