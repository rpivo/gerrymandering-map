"""Checks on data files committed to the repo, so CI catches a bad edit."""

import pytest

from gerry.__main__ import REPO_ROOT
from gerry.fetch import read_manifest
from gerry.state_audit import read_state_audit, validate_state_audit

SOURCES = REPO_ROOT / "data" / "sources"


def test_state_audit_is_valid():
    assert validate_state_audit(read_state_audit(SOURCES / "states.csv")) == []


def test_every_manifest_entry_is_complete():
    entries = read_manifest(SOURCES / "sources.csv")
    assert entries, "sources.csv is empty"
    for source_id, entry in entries.items():
        blank = [field for field, value in entry.items() if not value.strip()]
        assert blank == [], f"{source_id} has blank fields: {blank}"
        assert entry["url"].startswith("https://"), source_id
        assert len(entry["sha256"]) == 64, source_id


def test_new_jersey_county_totals_add_up_to_the_official_statewide_totals():
    import csv

    with (SOURCES / "votes" / "nj-2024-president-by-county.csv").open() as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 21
    assert sum(int(r["harris"]) for r in rows) == 2_220_713
    assert sum(int(r["trump"]) for r in rows) == 1_968_215


@pytest.mark.parametrize(
    ("name", "state", "harris", "trump"),
    [
        ("tx-planc2333-president-2024.csv", "TX", 4_835_134, 6_393_403),
        ("nc-s249-president-2024.csv", "NC", 2_713_609, 2_896_941),
    ],
)
def test_official_district_results_add_up_to_their_reports_totals(name, state, harris, trump):
    import csv

    from gerry.states import STATES_BY_USPS

    with (SOURCES / "votes" / name).open() as f:
        rows = list(csv.DictReader(f))
    assert sorted(int(r["district"]) for r in rows) == list(
        range(1, STATES_BY_USPS[state].seats + 1)
    )
    assert {r["state"] for r in rows} == {state}
    assert sum(int(r["harris"]) for r in rows) == harris
    assert sum(int(r["trump"]) for r in rows) == trump
