import pandas as pd
import pytest

from gerry.votes import (
    BIG_ROW_VOTES,
    assign_to_districts,
    district_weights,
    one_count_per_precinct,
    read_precinct_returns,
    state_quality,
    two_party_by_precinct,
    unopposed_districts,
)

HEADER = (
    "precinct,office,party_simplified,mode,votes,county_fips,jurisdiction_fips,district,state_po\n"
)


def returns(rows: list[tuple]) -> pd.DataFrame:
    """Rows of (state, county, precinct, mode, party, votes, district) as a returns table."""
    df = pd.DataFrame(
        rows,
        columns=[
            "state_po",
            "county_fips",
            "precinct",
            "mode",
            "party_simplified",
            "votes",
            "district",
        ],
    )
    df["jurisdiction_fips"] = df["county_fips"]
    df["votes"] = df["votes"].astype(float)
    return df


def test_read_precinct_returns_treats_redacted_votes_as_zero(tmp_path):
    path = tmp_path / "pres.csv"
    path.write_text(
        HEADER
        + "P1,US PRESIDENT,DEMOCRAT,TOTAL,*,06001,06001,STATEWIDE,CA\n"
        + "P1,US PRESIDENT,REPUBLICAN,TOTAL,12,06001,06001,STATEWIDE,CA\n"
    )
    df = read_precinct_returns(path)
    assert df["votes"].tolist() == [0.0, 12.0]
    # Codes stay strings: leading zeros in FIPS codes matter for the join.
    assert df["county_fips"].tolist() == ["06001", "06001"]


def test_one_count_per_precinct_prefers_total_rows():
    df = returns(
        [
            ("XX", "1", "A", "TOTAL", "DEMOCRAT", 10, ""),
            ("XX", "1", "A", "EARLY", "DEMOCRAT", 4, ""),
            ("XX", "1", "A", "ELECTION DAY", "DEMOCRAT", 6, ""),
        ]
    )
    assert one_count_per_precinct(df)["votes"].sum() == 10


def test_one_count_per_precinct_sums_modes_without_a_total():
    df = returns(
        [
            ("XX", "1", "B", "EARLY", "DEMOCRAT", 4, ""),
            ("XX", "1", "B", "ELECTION DAY", "DEMOCRAT", 6, ""),
        ]
    )
    assert one_count_per_precinct(df)["votes"].sum() == 10


def test_two_party_by_precinct_keeps_only_democrat_and_republican():
    df = returns(
        [
            ("XX", "1", "A", "TOTAL", "DEMOCRAT", 60, ""),
            ("XX", "1", "A", "TOTAL", "REPUBLICAN", 40, ""),
            ("XX", "1", "A", "TOTAL", "LIBERTARIAN", 9, ""),
        ]
    )
    row = two_party_by_precinct(df).iloc[0]
    assert (row["dem"], row["rep"]) == (60, 40)


def test_district_weights_split_a_precinct_by_its_house_votes():
    house = returns(
        [
            ("XX", "1", "A", "TOTAL", "DEMOCRAT", 30, "001"),
            ("XX", "1", "A", "TOTAL", "REPUBLICAN", 10, "002"),
        ]
    )
    w = district_weights(house).set_index("district")["weight"]
    assert w.to_dict() == {1: 0.75, 2: 0.25}


def test_district_weights_ignore_zero_vote_and_statewide_rows():
    # Ohio lists every precinct under every district with zero votes off-ballot;
    # Rhode Island adds STATEWIDE rows. Neither says where a precinct is.
    house = returns(
        [
            ("XX", "1", "A", "TOTAL", "DEMOCRAT", 50, "003"),
            ("XX", "1", "A", "TOTAL", "DEMOCRAT", 0, "004"),
            ("XX", "1", "A", "TOTAL", "DEMOCRAT", 50, "STATEWIDE"),
        ]
    )
    assert district_weights(house)["district"].tolist() == [3]


def test_unopposed_districts_are_the_seats_with_no_house_votes():
    house = returns([("OK", "1", "A", "TOTAL", "DEMOCRAT", 5, f"{d:03d}") for d in (1, 2, 4, 5)])
    assert unopposed_districts(district_weights(house)) == {"OK": [3]}


def _assign(pres_rows, house_rows):
    two = two_party_by_precinct(returns(pres_rows))
    weights = district_weights(returns(house_rows))
    return assign_to_districts(two, weights, unopposed_districts(weights))


def test_assign_puts_a_matched_precinct_in_its_district():
    out = _assign(
        [
            ("XX", "1", "A", "TOTAL", "DEMOCRAT", 60, ""),
            ("XX", "1", "A", "TOTAL", "REPUBLICAN", 40, ""),
        ],
        [
            ("XX", "1", "A", "TOTAL", "DEMOCRAT", 1, "002"),
            ("XX", "1", "Z", "TOTAL", "DEMOCRAT", 1, "001"),
        ],
    )
    row = out[out["district"] == 2].iloc[0]
    assert (row["dem"], row["rep"], row["kind"]) == (60, 40, "exact")


def test_assign_sends_unmatched_precincts_to_the_states_unopposed_district():
    out = _assign(
        [
            ("OK", "9", "Q", "TOTAL", "DEMOCRAT", 10, ""),
            ("OK", "9", "Q", "TOTAL", "REPUBLICAN", 30, ""),
        ],
        [("OK", "1", "A", "TOTAL", "DEMOCRAT", 5, f"{d:03d}") for d in (1, 2, 4, 5)],
    )
    row = out[out["kind"] == "unopposed"].iloc[0]
    assert (row["district"], row["dem"], row["rep"]) == (3, 10, 30)


def test_assign_spreads_other_unmatched_precincts_by_the_countys_matched_votes():
    out = _assign(
        [
            ("XX", "1", "A", "TOTAL", "DEMOCRAT", 30, ""),
            ("XX", "1", "B", "TOTAL", "DEMOCRAT", 10, ""),
            ("XX", "1", "C", "TOTAL", "DEMOCRAT", 8, ""),  # unmatched
        ],
        [
            ("XX", "1", "A", "TOTAL", "DEMOCRAT", 1, "001"),
            ("XX", "1", "B", "TOTAL", "DEMOCRAT", 1, "002"),
        ],
    )
    county = out[out["kind"] == "county"].set_index("district")["dem"]
    assert county.to_dict() == {1: 6.0, 2: 2.0}


def test_assign_reports_votes_it_cannot_place_as_lost():
    out = _assign(
        [("XX", "7", "Q", "TOTAL", "DEMOCRAT", 5, "")],
        [
            ("XX", "1", "A", "TOTAL", "DEMOCRAT", 1, "001"),
            ("XX", "1", "B", "TOTAL", "DEMOCRAT", 1, "002"),
        ],
    )
    lost = out[out["kind"] == "lost"]
    assert lost["dem"].sum() == 5
    assert lost["district"].isna().all()


def test_assign_conserves_votes():
    pres = [
        ("XX", "1", p, "TOTAL", party, v, "")
        for p, party, v in [
            ("A", "DEMOCRAT", 30),
            ("A", "REPUBLICAN", 20),
            ("B", "DEMOCRAT", 7),
            ("C", "REPUBLICAN", 11),
        ]
    ]
    house = [
        ("XX", "1", "A", "TOTAL", "DEMOCRAT", 3, "001"),
        ("XX", "1", "A", "TOTAL", "DEMOCRAT", 1, "002"),
        ("XX", "1", "B", "TOTAL", "DEMOCRAT", 1, "002"),
    ]
    out = _assign(pres, house)
    assert out["dem"].sum() + out["rep"].sum() == pytest.approx(68)


def test_state_quality_measures_votes_in_big_unassignable_rows():
    big = BIG_ROW_VOTES + 1
    out = _assign(
        [
            ("XX", "1", "A", "TOTAL", "DEMOCRAT", 3 * big, ""),
            ("XX", "1", "CATCHALL", "TOTAL", "DEMOCRAT", big, ""),
        ],
        [
            ("XX", "1", "A", "TOTAL", "DEMOCRAT", 1, "001"),
            ("XX", "1", "CATCHALL", "TOTAL", "DEMOCRAT", 1, "001"),
            ("XX", "1", "CATCHALL", "TOTAL", "DEMOCRAT", 1, "002"),
        ],
    )
    q = state_quality(out).set_index("state").loc["XX"]
    assert q["exact_pct"] == pytest.approx(75)
    assert q["big_row_pct"] == pytest.approx(25)
    assert q["lost_pct"] == 0


def test_reference_check_passes_matching_districts_and_names_differing_ones():
    from gerry.votes import check_reference

    totals = pd.DataFrame(
        {"state": ["TX"] * 2, "district": [1, 2], "dem": [100.0, 50.0], "rep": [100.0, 50.0]}
    )
    totals["dem_share"] = totals["dem"] / (totals["dem"] + totals["rep"])
    same = pd.DataFrame({"district": [1, 2], "harris": [1000, 500], "trump": [1000, 500]})
    assert check_reference(totals, "TX", same, tolerance_pts=0.1) == []
    off = same.assign(harris=[1000, 600])
    problems = check_reference(totals, "TX", off, tolerance_pts=0.1)
    assert len(problems) == 1 and "TX-02" in problems[0]


def test_reference_check_flags_a_district_missing_from_the_results():
    from gerry.votes import check_reference

    totals = pd.DataFrame(
        {"state": ["TX"], "district": [1], "dem": [1.0], "rep": [1.0], "dem_share": [0.5]}
    )
    ref = pd.DataFrame({"district": [1, 2], "harris": [1, 1], "trump": [1, 1]})
    assert any("TX-02" in p for p in check_reference(totals, "TX", ref, tolerance_pts=0.1))


def test_drop_aggregate_rows_removes_town_totals_that_repeat_their_precincts():
    from gerry.votes import drop_aggregate_rows

    df = returns(
        [
            ("NJ", "3", "Allendale 1", "TOTAL", "DEMOCRAT", 10, ""),
            ("NJ", "3", "Allendale 2", "TOTAL", "DEMOCRAT", 5, ""),
            ("NJ", "3", "Allendale", "TOTAL", "DEMOCRAT", 15, ""),  # town total: drop
            ("NJ", "3", "Alpine", "TOTAL", "DEMOCRAT", 7, ""),  # one-precinct town: keep
            ("NJ", "3", "Oradell", "TOTAL", "DEMOCRAT", 99, ""),  # not their sum: keep
            ("NJ", "3", "Oradell 1", "TOTAL", "DEMOCRAT", 4, ""),
        ]
    )
    kept = drop_aggregate_rows(df)
    assert sorted(kept["precinct"]) == [
        "Allendale 1",
        "Allendale 2",
        "Alpine",
        "Oradell",
        "Oradell 1",
    ]


def test_drop_aggregate_rows_removes_a_county_total_row():
    from gerry.votes import drop_aggregate_rows

    df = returns(
        [
            ("NJ", "15", "Clayton 1", "TOTAL", "DEMOCRAT", 10, ""),
            ("NJ", "15", "Glassboro 1", "TOTAL", "REPUBLICAN", 6, ""),
            ("NJ", "15", "COUNTY TOTAL", "TOTAL", "DEMOCRAT", 10, ""),
            ("NJ", "15", "COUNTY TOTAL", "TOTAL", "REPUBLICAN", 6, ""),
        ]
    )
    assert "COUNTY TOTAL" not in drop_aggregate_rows(df)["precinct"].tolist()


def test_a_big_catch_all_row_takes_each_districts_own_partisan_mix():
    # County 1: district 1's precincts vote 80% Democratic, district 2's 20%. A county-wide
    # mail-ballot row split evenly by House votes should follow those mixes, not its own 50%.
    big = BIG_ROW_VOTES
    pres = [
        ("MO", "1", "A", "TOTAL", "DEMOCRAT", 80, ""),
        ("MO", "1", "A", "TOTAL", "REPUBLICAN", 20, ""),
        ("MO", "1", "B", "TOTAL", "DEMOCRAT", 20, ""),
        ("MO", "1", "B", "TOTAL", "REPUBLICAN", 80, ""),
        ("MO", "1", "MAIL", "TOTAL", "DEMOCRAT", big, ""),
        ("MO", "1", "MAIL", "TOTAL", "REPUBLICAN", big, ""),
    ]
    house = [
        ("MO", "1", "A", "TOTAL", "DEMOCRAT", 1, "001"),
        ("MO", "1", "B", "TOTAL", "DEMOCRAT", 1, "002"),
        ("MO", "1", "MAIL", "TOTAL", "DEMOCRAT", 50, "001"),
        ("MO", "1", "MAIL", "TOTAL", "DEMOCRAT", 50, "002"),
    ]
    out = _assign(pres, house)
    mail = out[out["kind"] == "split"].set_index("district")
    assert mail.loc[1, "dem"] == pytest.approx(0.8 * big)
    assert mail.loc[2, "dem"] == pytest.approx(0.2 * big)
    # Each party's votes are still all there.
    assert mail["dem"].sum() == pytest.approx(big)
    assert mail["rep"].sum() == pytest.approx(big)


def test_a_small_split_precinct_keeps_one_mix():
    pres = [
        ("XX", "1", "S", "TOTAL", "DEMOCRAT", 30, ""),
        ("XX", "1", "S", "TOTAL", "REPUBLICAN", 10, ""),
    ]
    house = [
        ("XX", "1", "S", "TOTAL", "DEMOCRAT", 3, "001"),
        ("XX", "1", "S", "TOTAL", "DEMOCRAT", 1, "002"),
    ]
    out = _assign(pres, house).set_index("district")
    assert (out.loc[1, "dem"], out.loc[1, "rep"]) == (22.5, 7.5)


def test_unmatched_votes_spread_by_each_partys_county_pattern():
    pres = [
        ("XX", "1", "A", "TOTAL", "DEMOCRAT", 90, ""),
        ("XX", "1", "A", "TOTAL", "REPUBLICAN", 10, ""),
        ("XX", "1", "B", "TOTAL", "DEMOCRAT", 10, ""),
        ("XX", "1", "B", "TOTAL", "REPUBLICAN", 90, ""),
        ("XX", "1", "C", "TOTAL", "DEMOCRAT", 50, ""),  # unmatched
        ("XX", "1", "C", "TOTAL", "REPUBLICAN", 50, ""),
    ]
    house = [
        ("XX", "1", "A", "TOTAL", "DEMOCRAT", 1, "001"),
        ("XX", "1", "B", "TOTAL", "DEMOCRAT", 1, "002"),
    ]
    county = _assign(pres, house).query("kind == 'county'").set_index("district")
    assert county.loc[1, "dem"] == pytest.approx(45)
    assert county.loc[1, "rep"] == pytest.approx(5)


def test_state_quality_doesnt_flag_catch_all_rows_split_by_county_patterns():
    big = BIG_ROW_VOTES + 1
    out = _assign(
        [
            ("XX", "1", "A", "TOTAL", "DEMOCRAT", 10, ""),
            ("XX", "1", "B", "TOTAL", "DEMOCRAT", 10, ""),
            ("XX", "1", "MAIL", "TOTAL", "DEMOCRAT", big, ""),
        ],
        [
            ("XX", "1", "A", "TOTAL", "DEMOCRAT", 1, "001"),
            ("XX", "1", "B", "TOTAL", "DEMOCRAT", 1, "002"),
            ("XX", "1", "MAIL", "TOTAL", "DEMOCRAT", 1, "001"),
            ("XX", "1", "MAIL", "TOTAL", "DEMOCRAT", 1, "002"),
        ],
    )
    assert state_quality(out).set_index("state").loc["XX", "big_row_pct"] == 0


KC_HEADER = (
    "Precinct,Race,LegislativeDistrict,CountyCouncil,CongressionalDistrict,CounterGroup,"
    "CounterType,SumOfCount\n"
)
PRES_RACE = "President and Vice President of the United States" * 2


def test_read_king_county_places_each_precinct_in_its_listed_district(tmp_path):
    from gerry.votes import read_king_county

    path = tmp_path / "kc.csv"
    path.write_text(
        KC_HEADER
        + f"SEA 37-1,{PRES_RACE},37,2,9,Total,Kamala D. Harris / Tim Walz,300\n"
        + f"SEA 37-1,{PRES_RACE},37,2,9,Total,Donald J. Trump / JD Vance,100\n"
        + f"SEA 37-1,{PRES_RACE},37,2,9,Total,Registered Voters,999\n"
        + f"SEA 37-1,{PRES_RACE},37,2,9,Total,Jill Stein / Rudolph Ware,7\n"
        + "SEA 37-1,Congressional District No. 9 United States Representative,37,2,9,Total,"
        + "Adam Smith,250\n"
        + f"KEN 33-2,{PRES_RACE},33,5,8,Total,Kamala D. Harris / Tim Walz,40\n"
        + f"KEN 33-2,{PRES_RACE},33,5,8,Total,Donald J. Trump / JD Vance,60\n"
    )
    two, weights = read_king_county(path)
    rows = two.merge(weights, on=["state_po", "county_fips", "jurisdiction_fips", "precinct"])
    got = {r.precinct: (r.district, r.dem, r.rep, r.weight) for r in rows.itertuples()}
    assert got == {"KC SEA 37-1": (9, 300, 100, 1.0), "KC KEN 33-2": (8, 40, 60, 1.0)}
    assert set(rows["county_fips"]) == {"53033"} and set(rows["state_po"]) == {"WA"}


def test_replace_county_swaps_a_countys_rows_for_better_ones():
    from gerry.votes import replace_county

    old_two = two_party_by_precinct(
        returns(
            [
                ("WA", "53033", "9917", "TOTAL", "DEMOCRAT", 50, ""),
                ("WA", "53061", "S1", "TOTAL", "DEMOCRAT", 5, ""),
            ]
        )
    )
    old_w = district_weights(
        returns(
            [
                ("WA", "53033", "9917", "TOTAL", "DEMOCRAT", 1, "007"),
                ("WA", "53061", "S1", "TOTAL", "DEMOCRAT", 1, "002"),
            ]
        )
    )
    new_two = two_party_by_precinct(returns([("WA", "53033", "KC A", "TOTAL", "DEMOCRAT", 50, "")]))
    new_w = district_weights(returns([("WA", "53033", "KC A", "TOTAL", "DEMOCRAT", 1, "009")]))
    two, w = replace_county(old_two, old_w, new_two, new_w)
    assert sorted(two["precinct"]) == ["KC A", "S1"]
    assert sorted(w["precinct"]) == ["KC A", "S1"]


def test_calibrate_to_county_totals_scales_each_party_to_the_official_count():
    from gerry.votes import calibrate_to_county_totals

    two = two_party_by_precinct(
        returns(
            [
                ("NJ", "34021", "A", "TOTAL", "DEMOCRAT", 30, ""),
                ("NJ", "34021", "A", "TOTAL", "REPUBLICAN", 10, ""),
                ("NJ", "34021", "B", "TOTAL", "DEMOCRAT", 10, ""),
                ("NJ", "34021", "B", "TOTAL", "REPUBLICAN", 10, ""),
                ("NJ", "34003", "C", "TOTAL", "DEMOCRAT", 5, ""),
                ("NY", "36001", "D", "TOTAL", "DEMOCRAT", 7, ""),
            ]
        )
    )
    official = pd.DataFrame(
        {
            "state": ["NJ", "NJ"],
            "county_fips": ["34021", "34003"],
            "harris": [80, 5],
            "trump": [30, 0],
        }
    )
    out = calibrate_to_county_totals(two, official).set_index("precinct")
    assert (out.loc["A", "dem"], out.loc["A", "rep"]) == (60, 15)
    assert (out.loc["B", "dem"], out.loc["B", "rep"]) == (20, 15)
    assert out.loc["C", "dem"] == 5
    assert out.loc["D", "dem"] == 7  # other states untouched


def test_calibrate_to_county_totals_fails_for_a_county_with_no_precincts():
    from gerry.votes import calibrate_to_county_totals

    two = two_party_by_precinct(returns([("NJ", "34021", "A", "TOTAL", "DEMOCRAT", 30, "")]))
    official = pd.DataFrame(
        {"state": ["NJ"], "county_fips": ["34999"], "harris": [1], "trump": [1]}
    )
    with pytest.raises(ValueError, match="34999"):
        calibrate_to_county_totals(two, official)


def test_assign_matches_town_names_that_differ_only_by_a_municipal_suffix():
    # Gloucester County, NJ: the President file says "Deptford Twp", the House file "Deptford".
    out = _assign(
        [
            ("NJ", "15", "Deptford Twp", "TOTAL", "DEMOCRAT", 70, ""),
            ("NJ", "15", "Clayton Boro", "TOTAL", "DEMOCRAT", 30, ""),
        ],
        [
            ("NJ", "15", "Deptford", "TOTAL", "DEMOCRAT", 3, "001"),
            ("NJ", "15", "Deptford", "TOTAL", "DEMOCRAT", 1, "002"),
            ("NJ", "15", "Clayton", "TOTAL", "DEMOCRAT", 5, "002"),
        ],
    )
    assert "county" not in set(out["kind"])
    by = out.groupby("district")["dem"].sum()
    assert by.to_dict() == {1: 52.5, 2: 47.5}


def test_assign_doesnt_guess_between_two_towns_with_the_same_short_name():
    out = _assign(
        [("NJ", "15", "Franklin Twp", "TOTAL", "DEMOCRAT", 10, "")],
        [
            ("NJ", "15", "Franklin", "TOTAL", "DEMOCRAT", 1, "001"),
            ("NJ", "15", "Franklin Boro", "TOTAL", "DEMOCRAT", 1, "002"),
        ],
    )
    # Not renamed, so not matched to either district.
    assert not out["kind"].isin(["exact", "split"]).any()
