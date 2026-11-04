"""The state map audit: which congressional map each state used in the 2026 election.

`data/sources/states.csv` has one row per state. It records whether the map used on
2026-11-03 differs from the 2024 map in the Census CD119 boundary file, who drew it,
when, and an official source. States marked `yes` or `unclear` need their current
boundaries swapped in (milestone M2).
"""

import csv
import re
from datetime import date
from pathlib import Path

from gerry.states import STATES_BY_USPS

COLUMNS = [
    "state",
    "map_in_effect_2026",
    "changed_since_2024",
    "enacted",
    "drawn_by",
    "first_used",
    "source_url",
    "source_publisher",
    "notes",
    "confidence",
    "checked",
]
ALLOWED = {
    "changed_since_2024": {"yes", "no", "unclear"},
    "drawn_by": {"legislature", "commission", "court", "ballot-measure", "at-large"},
    "first_used": {"2022", "2024", "2026"},
    "confidence": {"high", "medium", "low"},
}
REQUIRED_TEXT = ["map_in_effect_2026", "source_publisher"]
_YEAR_MONTH = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")
# date.fromisoformat also accepts 20261104 and 2026-W45-3, so check the shape first.
_FULL_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def read_state_audit(path: Path) -> list[dict[str, str]]:
    """Read the audit CSV.

    Raises:
        ValueError: if the header doesn't match COLUMNS exactly.
    """
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != COLUMNS:
            raise ValueError(f"Expected columns {COLUMNS}, found {reader.fieldnames}")
        return list(reader)


def _is_date(value: str) -> bool:
    """Return True for a real calendar date written exactly as YYYY-MM-DD."""
    if not _FULL_DATE.match(value):
        return False
    try:
        date.fromisoformat(value)
    except ValueError:
        return False
    return True


def _check_coverage(rows: list[dict[str, str]]) -> list[str]:
    """Check that every state appears exactly once, nothing else appears, in sorted order."""
    seen = [r["state"] for r in rows]
    problems = [f"{s}: not a state." for s in seen if s not in STATES_BY_USPS]
    problems += [f"{s}: missing." for s in sorted(STATES_BY_USPS.keys() - set(seen))]
    problems += [
        f"{s}: appears more than once." for s in sorted({s for s in seen if seen.count(s) > 1})
    ]
    if seen != sorted(seen):
        problems.append("Rows must be sorted by state.")
    return problems


def _check_values(r: dict[str, str]) -> list[str]:
    """Check one row's fields against the allowed values and formats."""
    s = r["state"]
    problems = [
        f"{s}: {column} is {r[column]!r}, expected one of {sorted(allowed)}."
        for column, allowed in ALLOWED.items()
        if r[column] not in allowed
    ]
    problems += [f"{s}: {column} is blank." for column in REQUIRED_TEXT if not r[column].strip()]
    if not r["source_url"].startswith("https://"):
        problems.append(f"{s}: source_url must start with https://.")
    if not _is_date(r["checked"]):
        problems.append(f"{s}: checked must be a date (YYYY-MM-DD).")
    return problems


def _check_consistency(r: dict[str, str]) -> list[str]:
    """Check that one row's fields agree with each other and with the apportionment."""
    s, problems = r["state"], []
    state = STATES_BY_USPS.get(s)
    at_large = state is not None and state.seats == 1
    if at_large != (r["drawn_by"] == "at-large"):
        problems.append(f"{s}: drawn_by must be at-large exactly when the state has one seat.")
    if not at_large and not (_is_date(r["enacted"]) or _YEAR_MONTH.match(r["enacted"])):
        problems.append(f"{s}: enacted must be YYYY-MM-DD or YYYY-MM.")
    changed, first_used = r["changed_since_2024"], r["first_used"]
    if changed == "yes" and first_used != "2026":
        problems.append(f"{s}: a map changed since 2024 must have first_used 2026.")
    if first_used == "2026" and changed != "yes":
        problems.append(f"{s}: first_used 2026 means changed_since_2024 must be yes.")
    if changed == "unclear" and (r["confidence"] != "low" or not r["notes"].strip()):
        problems.append(f"{s}: unclear rows need confidence low and notes explaining why.")
    return problems


def validate_state_audit(rows: list[dict[str, str]]) -> list[str]:
    """Return a list of problems with the audit rows. An empty list means all checks pass."""
    problems = _check_coverage(rows)
    for r in rows:
        problems += _check_values(r) + _check_consistency(r)
    return problems


def changed_states(rows: list[dict[str, str]]) -> dict[str, list[str]]:
    """Return the states whose 2026 map differs from 2024 (`yes`) or might (`unclear`)."""
    return {
        status: sorted(r["state"] for r in rows if r["changed_since_2024"] == status)
        for status in ["yes", "unclear"]
    }
