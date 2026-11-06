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


def test_shapes_json_gives_each_state_map_its_closeups(tmp_path):
    import geopandas as gpd
    import shapely
    from shapely.geometry import box

    # Kansas has two 1 km districts in a 200 km state; Wyoming has one big district.
    tiny = [box(-99.01, 40.99, -99.0, 41.0), box(-99.0, 40.99, -98.99, 41.0)]
    rest = box(-100, 40, -98, 42).difference(shapely.union_all(tiny))
    districts = gpd.GeoDataFrame(
        {"district_id": ["KS-01", "KS-02", "KS-03", "WY-AL"], "state": ["KS", "KS", "KS", "WY"]},
        geometry=[rest, *tiny, box(-110, 41, -104, 45)],
        crs="EPSG:4269",
    )
    path = tmp_path / "shapes.json"
    write_shapes_json(districts, path)
    states = json.loads(path.read_text())["states"]
    closeup = states["KS"]["closeups"][0]
    assert set(closeup) == {"box", "viewBox", "paths"}  # the first is never nested
    assert {"KS-02", "KS-03"} <= set(closeup["paths"])
    assert states["WY"]["closeups"] == []


def test_shapes_json_crops_hawaii_and_notes_it(tmp_path):
    import geopandas as gpd
    from shapely.geometry import MultiPolygon, box

    oahu, big_island, kure = (box(-158.3, 21.25, -157.6, 21.7), box(-156.0, 19.0, -155.0, 20.2),
                              box(-178.4, 28.35, -178.3, 28.45))  # fmt: skip
    districts = gpd.GeoDataFrame(
        {"district_id": ["HI-01", "HI-02"], "state": ["HI", "HI"]},
        geometry=[oahu, MultiPolygon([big_island, kure])],
        crs="EPSG:4269",
    )
    path = tmp_path / "shapes.json"
    write_shapes_json(districts, path)
    data = json.loads(path.read_text())
    note = "The Northwestern Hawaiian Islands, part of District 2, are not shown."
    assert data["states"]["HI"]["note"] == note
    assert data["districts"]["HI-02"]["note"] == note
    assert "note" not in data["districts"]["HI-01"]
    # Without Kure the drawing is nearly as tall as wide (874 of 1000), not a wide strip of
    # ocean (527 of 1000 with it).
    width, height = map(int, data["states"]["HI"]["viewBox"].split()[2:])
    assert height > 0.8 * width


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


def population_table(*rows: tuple) -> pd.DataFrame:
    columns = ["district_id", "state", "pop", "vap", "hispanic", "nh_white", "nh_black",
               "nh_aian", "nh_asian", "nh_nhpi", "minority", "nearest_pop"]  # fmt: skip
    return pd.DataFrame(list(rows), columns=columns)


# AL-07: Black majority. TX-35: Hispanic majority. NJ-08: majority-minority only together.
AL_07 = ("AL-07", "AL", 717_000, 550_000, 22_000, 235_000, 277_200, 4_000, 8_000, 500, 315_000, 0)
TX_35 = ("TX-35", "TX", 766_000, 590_000, 316_830, 205_000, 60_000, 6_000, 20_000, 900, 385_000, 0)
NJ_08 = ("NJ-08", "NJ", 775_000, 600_000, 220_000, 250_000, 60_000, 3_000, 75_000, 400, 350_000, 0)
WY_AL = ("WY-AL", "WY", 576_851, 441_337, 38_153, 370_041, 5_000, 9_000, 5_000, 600, 71_296, 0)


def population_by_id(*rows) -> dict[str, dict]:
    from gerry.export import population_records

    return {r["id"]: r for r in population_records(population_table(*rows))}


def test_population_records_give_rounded_voting_age_shares():
    tx = population_by_id(TX_35)["TX-35"]
    assert tx == {
        "id": "TX-35",
        "vap": 590_000,
        "hispanic": 0.537,
        "white": 0.347,
        "black": 0.102,
        "aian": 0.01,
        "asian": 0.034,
        "nhpi": 0.002,
        "minority": 0.653,
        "majority": "hispanic",
    }


def test_population_records_name_the_majority_group_or_coalition():
    out = population_by_id(AL_07, TX_35, NJ_08, WY_AL)
    assert {i: r["majority"] for i, r in out.items()} == {
        "AL-07": "black",
        "TX-35": "hispanic",
        "NJ-08": "coalition",
        "WY-AL": None,
    }


def test_exactly_half_is_not_a_majority():
    half = ("XX-01", "KS", 2, 1000, 0, 500, 500, 0, 0, 0, 500, 0)
    assert population_by_id(half)["XX-01"]["majority"] is None


def test_population_json_is_sorted_deterministic_and_described(tmp_path):
    from gerry.export import write_population_json

    path = tmp_path / "population.json"
    write_population_json(population_table(WY_AL, AL_07), path)
    first = path.read_bytes()
    write_population_json(population_table(AL_07, WY_AL), path)
    assert path.read_bytes() == first
    data = json.loads(first)
    assert [r["id"] for r in data["districts"]] == ["AL-07", "WY-AL"]
    assert data["count"] == 2
    assert "2020 Census" in data["description"]


def city_rows(*rows: tuple) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["state", "name", "kind", "pop", "lat", "lon"])


def test_cities_json_keeps_each_states_largest_places_in_map_coordinates(tmp_path):
    import geopandas as gpd
    from shapely.geometry import box

    from gerry.export import MAX_CITIES, write_cities_json

    districts = gpd.GeoDataFrame(
        {"district_id": ["ME-01", "ME-02"], "state": ["ME", "ME"]},
        geometry=[box(-70, 44, -69, 45), box(-69, 44, -68, 45)],
        crs="EPSG:4269",
    )
    small = [("ME", f"Town {i}", "town", 100 + i, 44.5, -69.5) for i in range(MAX_CITIES)]
    places = city_rows(*small, ("ME", "Portland", "city", 68408, 44.9, -69.9))
    write_cities_json(districts, places, tmp_path / "cities.json")
    write_shapes_json(districts, tmp_path / "shapes.json")
    data = json.loads((tmp_path / "cities.json").read_text())
    me = data["states"]["ME"]
    assert (
        me["viewBox"]
        == json.loads((tmp_path / "shapes.json").read_text())["states"]["ME"]["viewBox"]
    )
    assert len(me["cities"]) == MAX_CITIES
    # 0.1 degrees in from the northwest corner of a 1-degree-tall map 696 units tall; x is a
    # little more than 50 because meridians lean in toward the north in the projection.
    assert me["cities"][0] == {"name": "Portland", "pop": 68408, "x": 57, "y": 70}
    assert [c["name"] for c in me["cities"][1:3]] == [
        f"Town {MAX_CITIES - 1}",
        f"Town {MAX_CITIES - 2}",
    ]
    assert "Generated by" in data["description"]


def test_cities_json_labels_a_consolidated_city_by_its_short_name(tmp_path):
    import geopandas as gpd
    from shapely.geometry import box

    from gerry.export import write_cities_json

    districts = gpd.GeoDataFrame(
        {"district_id": ["TN-05"], "state": ["TN"]}, geometry=[box(-87, 36, -86, 37)],
        crs="EPSG:4269",
    )  # fmt: skip
    places = city_rows(("TN", "Nashville-Davidson", "metropolitan government", 689447, 36.2, -86.8))
    write_cities_json(districts, places, tmp_path / "cities.json")
    tennessee = json.loads((tmp_path / "cities.json").read_text())["states"]["TN"]
    assert [c["name"] for c in tennessee["cities"]] == ["Nashville"]


def test_cities_json_leaves_out_places_the_map_does_not_draw(tmp_path):
    import geopandas as gpd
    from shapely.geometry import MultiPolygon, box

    from gerry.export import write_cities_json

    districts = gpd.GeoDataFrame(
        {"district_id": ["HI-01", "HI-02"], "state": ["HI", "HI"]},
        geometry=[box(-158.3, 21.25, -157.6, 21.7),
                  MultiPolygon([box(-156.0, 19.0, -155.0, 20.2),
                                box(-178.4, 28.35, -178.3, 28.45)])],
        crs="EPSG:4269",
    )  # fmt: skip
    places = city_rows(("HI", "Hilo", "community", 44186, 19.7, -155.1),
                       ("HI", "Kure", "community", 50000, 28.4, -178.35))  # fmt: skip
    write_cities_json(districts, places, tmp_path / "cities.json")
    hawaii = json.loads((tmp_path / "cities.json").read_text())["states"]["HI"]
    assert [c["name"] for c in hawaii["cities"]] == ["Hilo"]


def test_district_cities_json_places_each_districts_largest_pieces_on_its_page_outline(tmp_path):
    import geopandas as gpd
    from shapely.geometry import Polygon, box

    from gerry.export import MAX_DISTRICT_CITIES, write_district_cities_json

    # The spike (about 670 m tall) survives page detail but not card detail, so the page and
    # card view boxes differ and the test can tell which one the points were placed on.
    spike = Polygon([(-86.5, 37), (-86.4995, 37.006), (-86.499, 37)])
    districts = gpd.GeoDataFrame(
        {"district_id": ["TN-05", "TN-06"], "state": ["TN", "TN"]},
        geometry=[box(-87, 36, -86, 37).union(spike), box(-86, 36, -85, 37)],
        crs="EPSG:4269",
    )
    places = pd.DataFrame({
        "state": "TN", "place": ["52006", "00001"], "name": ["Nashville-Davidson", "Smallville"],
        "kind": ["metropolitan government", "town"], "pop": [689447, 100],
    })  # fmt: skip
    small = [("TN-05", "TN", "00001", 50 + i, -86.5, 36.5) for i in range(MAX_DISTRICT_CITIES)]
    pieces = pd.DataFrame(
        [("TN-05", "TN", "52006", 400000, -86.9, 36.9), *small,
         ("TN-06", "TN", "52006", 289447, -85.5, 36.5)],
        columns=["district_id", "state", "place", "pop", "lon", "lat"],
    )  # fmt: skip
    write_district_cities_json(districts, pieces, places, tmp_path / "district-cities.json")
    write_shapes_json(districts, tmp_path / "shapes.json")
    data = json.loads((tmp_path / "district-cities.json").read_text())
    shapes = json.loads((tmp_path / "shapes.json").read_text())
    tn5 = data["districts"]["TN-05"]
    page, card = (shapes["districts"]["TN-05"][k]["viewBox"] for k in ("page", "card"))
    assert page != card  # anchor: the spike makes the two details distinguishable
    assert tn5["viewBox"] == page
    assert len(tn5["cities"]) == MAX_DISTRICT_CITIES
    first = tn5["cities"][0]
    assert (first["name"], first["pop"]) == ("Nashville", 400000)
    assert first["x"] < 150 and first["y"] < 150  # near the northwest corner
    assert [c["name"] for c in data["districts"]["TN-06"]["cities"]] == ["Nashville"]
    assert "Generated by" in data["description"]


def test_president_records_key_each_districts_two_party_shares_by_its_id():
    from gerry.export import president_records

    table = pd.DataFrame({
        "state": ["NE", "NE", "WY"], "district": [2, 10, 0], "dem": [163541.3, 1.0, 69527.0],
        "rep": [148905.6, 3.0, 192633.0], "dem_share": [0.52342, 0.25, 0.26521],
        "method": ["precinct join", "official report", "statewide"],
    })  # fmt: skip
    assert president_records(table) == {
        "NE-02": {"harris": 0.523, "trump": 0.477, "method": "precinct join"},
        "NE-10": {"harris": 0.25, "trump": 0.75, "method": "official report"},
        "WY-AL": {"harris": 0.265, "trump": 0.735, "method": "statewide"},
    }
