import pytest

RESULTS_HEADER = (
    "state,office,district,leader,leader_party,leader_votes,second,second_party,second_votes,"
    "counted,source_url,publisher,checked\n"
)
UNCALLED_HEADER = "state,office,district,status,runoff_date,note,source_url,as_of\n"
SRC = "https://sos.example.gov/results,Example Secretary of State,2026-11-06"


def results_csv(tmp_path, *rows: str):
    path = tmp_path / "results.csv"
    path.write_text(RESULTS_HEADER + "".join(f"{r},{SRC}\n" for r in rows))
    return path


def uncalled_csv(tmp_path, *rows: str):
    path = tmp_path / "uncalled.csv"
    path.write_text(
        UNCALLED_HEADER + "".join(f"{r},https://news.example.com,2026-11-06 09:00\n" for r in rows)
    )
    return path


def test_party_labels_become_plain_words():
    from gerry.elected import party_name

    assert party_name("DEM") == "Democrat"
    assert party_name("Democratic") == "Democrat"
    assert party_name("Democratic-Farmer-Labor") == "Democrat"
    assert party_name("REP") == "Republican"
    assert party_name("Republican Party") == "Republican"
    assert party_name("Independent") == "Independent"
    assert party_name("Libertarian") == "Libertarian"
    # Nebraska's label for a candidate on the ballot without a party.
    assert party_name("By Petition") == "Independent"


def test_names_printed_in_capitals_are_written_normally():
    from gerry.elected import display_name

    assert display_name("JARED GOLDEN") == "Jared Golden"
    assert display_name("MARY MCDONALD-SMITH JR.") == "Mary McDonald-Smith Jr."
    assert display_name("Pat O'Neil") == "Pat O'Neil"  # already mixed case: kept
    # Texas marks incumbents with "(I)", which isn't part of the name.
    assert display_name("Greg Casar (I)") == "Greg Casar"
    # Hawaii prints the last name first, in capitals.
    assert display_name("CASE, Ed") == "Ed Case"
    assert display_name("TOKUDA, Jill N.") == "Jill N. Tokuda"
    # Nevada does the same in mixed case.
    assert display_name("Titus, Dina") == "Dina Titus"
    assert display_name("Horsford, Steven A.") == "Steven A. Horsford"
    # A suffix after a comma is not a reversed name; the comma goes.
    assert display_name("Troy A. Carter, Sr.") == "Troy A. Carter Sr."
    assert display_name("Emanuel Cleaver, II") == "Emanuel Cleaver II"
    # Kentucky prints the last name alone in capitals.
    assert display_name("Andy BARR") == "Andy Barr"
    assert display_name("Pat Doe III") == "Pat Doe III"  # a numeral stays in capitals


def test_a_called_race_names_the_leader_and_an_uncalled_one_names_nobody(tmp_path):
    from gerry.elected import house_outcomes, read_results, read_uncalled

    results = read_results(results_csv(
        tmp_path,
        "ME,house,1,Chellie Pingree,Democrat,200,Sam Doe,Republican,100,99%",
        "ME,house,2,A Lead,Republican,150,B Close,Democrat,149,95%",
        "AK,house,AL,C Lead,Republican,90,D Next,Democrat,80,RCV pending",
    ))  # fmt: skip
    uncalled = read_uncalled(uncalled_csv(
        tmp_path, "ME,house,2,uncalled,,NBC and AP", "AK,house,AL,uncalled,,RCV November 18"
    ))  # fmt: skip
    outcomes = house_outcomes(results, uncalled)
    assert outcomes == {
        "ME-01": {"status": "elected", "name": "Chellie Pingree", "party": "Democrat"},
        "ME-02": {"status": "uncalled"},
        "AK-AL": {"status": "uncalled"},
    }


def test_a_runoff_gives_its_date_and_names_nobody(tmp_path):
    from gerry.elected import house_outcomes, read_results, read_uncalled

    results = read_results(
        results_csv(tmp_path, "LA,house,5,E One,Republican,40,F Two,Democrat,35,runoff")
    )
    uncalled = read_uncalled(uncalled_csv(tmp_path, "LA,house,5,runoff,2026-12-12,No majority"))
    assert house_outcomes(results, uncalled) == {
        "LA-05": {"status": "runoff", "runoff_date": "2026-12-12"}
    }


def test_a_race_without_state_results_is_pending_unless_listed_as_uncalled(tmp_path):
    from gerry.elected import house_outcomes, read_results, read_uncalled

    results = read_results(results_csv(
        tmp_path, "MI,house,1,,,,,,,state site timed out", "MS,house,2,,,,,,,county results only"
    ))  # fmt: skip
    uncalled = read_uncalled(uncalled_csv(tmp_path, "MS,house,2,uncalled,,close"))
    assert house_outcomes(results, uncalled) == {
        "MI-01": {"status": "pending"},
        "MS-02": {"status": "uncalled"},
    }


def test_an_unopposed_candidate_is_elected(tmp_path):
    from gerry.elected import house_outcomes, read_results, read_uncalled

    results = read_results(results_csv(tmp_path, "FL,house,5,G Solo,Republican,,,,,unopposed"))
    assert house_outcomes(results, read_uncalled(uncalled_csv(tmp_path))) == {
        "FL-05": {"status": "elected", "name": "G Solo", "party": "Republican"}
    }


def test_problems_catch_missing_extra_unreadable_and_stray_rows(tmp_path):
    from gerry.elected import read_results, read_uncalled, result_problems

    results = read_results(results_csv(
        tmp_path,
        "ME,house,1,A,Democrat,2,B,Republican,1,",
        "ME,house,1,A,Democrat,2,B,Republican,1,",
        "ME,house,3,C,Democrat,2,D,Republican,1,",
    ))  # fmt: skip
    uncalled = read_uncalled(uncalled_csv(tmp_path, "VT,house,AL,uncalled,,stray"))
    problems = result_problems(results, uncalled, ["ME-01", "ME-02"])
    assert problems == [
        "ME-01: 2 result rows",
        "ME-02: no result row",
        "ME-03: not a 2026 district",
        "VT-AL: listed as uncalled but has no result row",
    ]


def test_a_complete_set_has_no_problems(tmp_path):
    from gerry.elected import read_results, read_uncalled, result_problems

    results = read_results(results_csv(
        tmp_path,
        "ME,house,1,A,Democrat,2,B,Republican,1,",
        "ME,house,2,,,,,,,state site unreadable",
    ))  # fmt: skip
    uncalled = read_uncalled(uncalled_csv(tmp_path, "ME,house,2,uncalled,,count ongoing"))
    assert len(results) == 2  # anchor
    assert result_problems(results, uncalled, ["ME-01", "ME-02"]) == []


def test_senate_outcomes_are_keyed_by_state_and_seat(tmp_path):
    from gerry.elected import read_results, read_uncalled, senate_outcomes

    results = read_results(results_csv(
        tmp_path,
        "ME,senate,regular,Janet Mills,Democrat,300,Susan Collins,Republican,290,",
        "OH,senate,special,H Win,Democrat,10,I Lose,Republican,9,",
        "MS,senate,regular,J Lead,Democrat,10,K Close,Republican,9,",
        "ME,house,1,A,Democrat,2,B,Republican,1,",
    ))  # fmt: skip
    uncalled = read_uncalled(uncalled_csv(tmp_path, "MS,senate,regular,uncalled,,close"))
    assert senate_outcomes(results, uncalled) == {
        ("ME", "regular"): {"status": "elected", "name": "Janet Mills", "party": "Democrat"},
        ("OH", "special"): {"status": "elected", "name": "H Win", "party": "Democrat"},
        ("MS", "regular"): {"status": "uncalled"},
    }


def test_an_unknown_status_in_the_uncalled_list_fails(tmp_path):
    from gerry.elected import read_uncalled

    with pytest.raises(ValueError, match="status"):
        read_uncalled(uncalled_csv(tmp_path, "ME,house,2,maybe,,?"))


def test_state_sources_list_each_state_once(tmp_path):
    from gerry.elected import read_results, state_sources

    results = read_results(results_csv(
        tmp_path,
        "ME,house,1,A,Democrat,2,B,Republican,1,",
        "ME,house,2,C,Democrat,2,D,Republican,1,",
    ))  # fmt: skip
    assert state_sources(results) == {
        "ME": {
            "publisher": "Example Secretary of State",
            "url": "https://sos.example.gov/results",
            "checked": "2026-11-06",
        }
    }


def test_senate_problems_need_a_race_for_every_seat_up_and_no_other(tmp_path):
    from gerry.elected import read_results, senate_problems

    results = read_results(results_csv(
        tmp_path,
        "ME,senate,regular,A,Democrat,2,B,Republican,1,",
        "VT,senate,regular,C,Democrat,2,D,Republican,1,",
    ))  # fmt: skip
    up = {("ME", "regular"), ("OH", "special")}
    assert senate_problems(results, up) == [
        "OH Senate special: no result row",
        "VT Senate regular: no seat was up",
    ]
    assert senate_problems(results[results["state"] == "ME"], {("ME", "regular")}) == []


def write_members(repo_root, results: list[str], uncalled: list[str]) -> None:
    members = repo_root / "data" / "sources" / "members"
    members.mkdir(parents=True)
    (members / "results-2026.csv").write_text(
        RESULTS_HEADER + "".join(f"{r},{SRC}\n" for r in results)
    )
    (members / "uncalled-2026.csv").write_text(
        UNCALLED_HEADER
        + "".join(f"{r},https://news.example.com,2026-11-06 09:00\n" for r in uncalled)
    )


def every_district_row(skip: str = "") -> list[str]:
    from gerry.states import STATES

    rows = []
    for s in STATES:
        for d in ["AL"] if s.seats == 1 else [str(n) for n in range(1, s.seats + 1)]:
            if f"{s.usps}-{d}" != skip:
                rows.append(f"{s.usps},house,{d},Pat Doe{d},DEM,2,Lee,REP,1,")
    return rows


def senators_json(repo_root, seats: list[tuple[str, int]]) -> None:
    import json

    site = repo_root / "site" / "src" / "data"
    site.mkdir(parents=True)
    states = {
        s: [{"name": f"X {s}", "last": "X", "party": "Democrat", "class": c}] for s, c in seats
    }
    (site / "senators.json").write_text(json.dumps({"as_of": "2026-11-06", "states": states}))


def test_the_elected_command_writes_house_and_senate_outcomes(tmp_path):
    import json

    from gerry import __main__ as cli

    write_members(
        tmp_path,
        every_district_row() + ["ME,senate,regular,JANET MILLS,DEM,3,Sue,REP,2,"],
        ["NE,house,2,uncalled,,close"],
    )
    senators_json(tmp_path, [("ME", 2)])
    assert cli.main(["elected", "--repo-root", str(tmp_path)]) == 0
    data = json.loads((tmp_path / "site/src/data/elected-2026.json").read_text())
    assert data["called_as_of"] == "2026-11-06 09:00"
    assert len(data["house"]) == 435
    assert data["house"]["ME-01"] == {"status": "elected", "name": "Pat Doe1", "party": "Democrat"}
    assert data["house"]["NE-02"] == {"status": "uncalled"}
    assert data["senate"] == {
        "ME": {"regular": {"status": "elected", "name": "Janet Mills", "party": "Democrat"}}
    }
    assert data["sources"]["ME"]["publisher"] == "Example Secretary of State"


def test_the_elected_command_writes_nothing_with_a_district_missing(tmp_path, capsys):
    from gerry import __main__ as cli

    write_members(tmp_path, every_district_row(skip="TX-35"), [])
    senators_json(tmp_path, [])
    assert cli.main(["elected", "--repo-root", str(tmp_path)]) == 1
    assert "TX-35: no result row" in capsys.readouterr().out
    assert not (tmp_path / "site/src/data/elected-2026.json").exists()
