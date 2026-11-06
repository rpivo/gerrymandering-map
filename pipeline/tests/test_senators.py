import json

import pytest

from gerry.states import STATES


def member(last: str, first: str, party: str, state: str) -> str:
    return (
        f"<member><member_full>{last} ({party}-{state})</member_full>"
        f"<last_name>{last}</last_name> <first_name>{first}</first_name>"
        f"<party>{party}</party><state>{state}</state><class>Class I</class></member>"
    )


def senate_xml(*members: str) -> str:
    return (
        '<?xml version="1.0" encoding="UTF-8"?><contact_information>'
        + "".join(members)
        + ("</contact_information>")
    )


def full_senate() -> list[str]:
    """Two made-up senators for every state."""
    return [
        member(f"{s.usps}{n}", "Pat", "D" if n == 1 else "R", s.usps)
        for s in STATES
        for n in (1, 2)
    ]


def test_reads_each_senator_with_a_readable_name_and_party(tmp_path):
    from gerry.senators import read_senators

    path = tmp_path / "senators.xml"
    path.write_text(
        senate_xml(
            member("King", "Angus S., Jr.", "I", "ME"),
            member("Collins", "Susan M.", "R", "ME"),
            member("Alsobrooks", "Angela D.", "D", "MD"),
        )
    )
    table = read_senators(path)
    assert table.to_dict("records") == [
        {
            "state": "ME",
            "last": "King",
            "name": "Angus S. King Jr.",
            "party": "Independent",
            "class": 1,
        },
        {
            "state": "ME",
            "last": "Collins",
            "name": "Susan M. Collins",
            "party": "Republican",
            "class": 1,
        },
        {
            "state": "MD",
            "last": "Alsobrooks",
            "name": "Angela D. Alsobrooks",
            "party": "Democrat",
            "class": 1,
        },
    ]


def test_reads_the_senate_class_as_a_number(tmp_path):
    from gerry.senators import read_senators

    path = tmp_path / "senators.xml"
    path.write_text(senate_xml(member("Doe", "Jo", "D", "WY").replace("Class I<", "Class III<")))
    assert read_senators(path)["class"].tolist() == [3]


def test_an_unknown_party_letter_fails_rather_than_guessing(tmp_path):
    from gerry.senators import read_senators

    path = tmp_path / "senators.xml"
    path.write_text(senate_xml(member("Doe", "Jo", "L", "WY")))
    with pytest.raises(ValueError, match="party"):
        read_senators(path)


def test_a_full_senate_has_no_problems(tmp_path):
    from gerry.senators import read_senators, senator_problems

    path = tmp_path / "senators.xml"
    path.write_text(senate_xml(*full_senate()))
    table = read_senators(path)
    assert len(table) == 100  # anchor: the check below runs on a real table
    assert senator_problems(table) == []


def test_a_state_without_two_senators_is_a_problem(tmp_path):
    from gerry.senators import read_senators, senator_problems

    members = [m for m in full_senate() if "<last_name>OH2<" not in m]
    members.append(member("Extra", "Lee", "R", "TX"))
    members.append(member("Delegate", "Sam", "D", "DC"))
    path = tmp_path / "senators.xml"
    path.write_text(senate_xml(*members))
    problems = senator_problems(read_senators(path))
    assert problems == [
        "DC: 1 senators, expected 0",
        "OH: 1 senators, expected 2",
        "TX: 3 senators, expected 2",
    ]


def test_senators_json_lists_each_state_alphabetically_by_last_name(tmp_path):
    from gerry.export import write_senators_json
    from gerry.senators import read_senators

    xml = tmp_path / "senators.xml"
    xml.write_text(
        senate_xml(
            member("King", "Angus S., Jr.", "I", "ME"),
            member("Collins", "Susan M.", "R", "ME"),
        )
    )
    path = tmp_path / "senators.json"
    write_senators_json(read_senators(xml), "2026-11-06", path)
    data = json.loads(path.read_text())
    assert data["as_of"] == "2026-11-06"
    assert data["states"] == {
        "ME": [
            {"name": "Susan M. Collins", "last": "Collins", "party": "Republican", "class": 1},
            {"name": "Angus S. King Jr.", "last": "King", "party": "Independent", "class": 1},
        ]
    }


def test_sources_json_marks_the_senate_list_as_members(tmp_path):
    from gerry.export import write_sources_json

    entry = {"id": "senate-senators", "url": "https://s/x", "publisher": "U.S. Senate",
        "license": "PD", "description": "Senators", "downloaded": "2026-11-06",
        "sha256": "e" * 64}  # fmt: skip
    path = tmp_path / "sources.json"
    write_sources_json({entry["id"]: entry}, path)
    assert json.loads(path.read_text())["sources"][0]["role"] == "members"


def place_cached_list(repo_root, members: list[str]) -> None:
    """Put a Senate list where the fetch cache looks, recorded in the manifest."""
    from gerry.senators import SENATORS

    raw = repo_root / "data" / "raw" / SENATORS.id
    raw.mkdir(parents=True)
    (raw / "senators_cfm.xml").write_text(senate_xml(*members))
    manifest = repo_root / "data" / "sources" / "sources.csv"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(
        "id,url,publisher,license,description,downloaded,sha256\n"
        f"{SENATORS.id},{SENATORS.url},U.S. Senate,PD,Senators,2026-11-06,\n"
    )


def test_the_senators_command_writes_the_site_data(tmp_path):
    from gerry import __main__ as cli

    place_cached_list(tmp_path, full_senate())
    assert cli.main(["senators", "--repo-root", str(tmp_path)]) == 0
    site = tmp_path / "site" / "src" / "data"
    data = json.loads((site / "senators.json").read_text())
    assert data["as_of"] == "2026-11-06"
    assert len(data["states"]) == 50
    assert data["states"]["OH"] == [
        {"name": "Pat OH1", "last": "OH1", "party": "Democrat", "class": 1},
        {"name": "Pat OH2", "last": "OH2", "party": "Republican", "class": 1},
    ]
    roles = [s["role"] for s in json.loads((site / "sources.json").read_text())["sources"]]
    assert roles == ["members"]


def test_the_senators_command_fails_on_an_incomplete_list(tmp_path, capsys):
    from gerry import __main__ as cli

    place_cached_list(tmp_path, full_senate()[1:])
    assert cli.main(["senators", "--repo-root", str(tmp_path)]) == 1
    assert "AL: 1 senators, expected 2" in capsys.readouterr().out
    assert not (tmp_path / "site" / "src" / "data" / "senators.json").exists()
