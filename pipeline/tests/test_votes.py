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
