"""Checks on data files committed to the repo, so CI catches a bad edit."""

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
