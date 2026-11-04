import pytest

from gerry.state_audit import COLUMNS, changed_states, read_state_audit, validate_state_audit
from gerry.states import STATES


def row(usps: str, **overrides: str) -> dict[str, str]:
    """A valid audit row: unchanged 2021 map, or an at-large row for one-seat states."""
    at_large = next(s for s in STATES if s.usps == usps).seats == 1
    base = {
        "state": usps,
        "map_in_effect_2026": "Single statewide district" if at_large else "2021 enacted plan",
        "changed_since_2024": "no",
        "enacted": "" if at_large else "2021-11-04",
        "drawn_by": "at-large" if at_large else "legislature",
        "first_used": "2022",
        "source_url": "https://example.gov/maps",
        "source_publisher": "Example Secretary of State",
        "notes": "",
        "confidence": "high",
        "checked": "2026-11-04",
    }
    return {**base, **overrides}


@pytest.fixture
def rows() -> list[dict[str, str]]:
    return [row(s.usps) for s in sorted(STATES, key=lambda s: s.usps)]


def with_row(rows, usps, **overrides):
    return [row(usps, **overrides) if r["state"] == usps else r for r in rows]


def test_valid_audit_has_no_problems(rows):
    assert validate_state_audit(rows) == []


def test_missing_and_duplicate_states_are_reported(rows):
    rows = [r for r in rows if r["state"] != "TX"] + [row("OH")]
    problems = validate_state_audit(sorted(rows, key=lambda r: r["state"]))
    assert any("TX" in p and "missing" in p for p in problems)
    assert any("OH" in p and "more than once" in p for p in problems)


def test_non_states_are_reported(rows):
    problems = validate_state_audit(rows + [row("WY", state="DC")])
    assert any("DC" in p and "not a state" in p for p in problems)


def test_rows_must_be_sorted_by_state(rows):
    rows[0], rows[1] = rows[1], rows[0]
    assert any("sorted" in p for p in validate_state_audit(rows))


@pytest.mark.parametrize(
    ("column", "value"),
    [
        ("changed_since_2024", "maybe"),
        ("drawn_by", "governor"),
        ("first_used", "2020"),
        ("confidence", "certain"),
    ],
)
def test_values_outside_the_allowed_set_are_reported(rows, column, value):
    problems = validate_state_audit(with_row(rows, "TX", **{column: value}))
    assert any(p.startswith("TX:") and column in p and value in p for p in problems)


@pytest.mark.parametrize("column", ["map_in_effect_2026", "source_publisher"])
def test_required_text_must_not_be_blank(rows, column):
    problems = validate_state_audit(with_row(rows, "TX", **{column: "  "}))
    assert any(p.startswith("TX:") and column in p for p in problems)


@pytest.mark.parametrize("url", ["http://example.gov", "example.gov", ""])
def test_source_url_must_be_https(rows, url):
    problems = validate_state_audit(with_row(rows, "TX", source_url=url))
    assert any(p.startswith("TX:") and "source_url" in p for p in problems)


@pytest.mark.parametrize("enacted", ["2025-08-29", "2025-08"])
def test_enacted_accepts_a_day_or_a_month(rows, enacted):
    assert validate_state_audit(with_row(rows, "TX", enacted=enacted)) == []


@pytest.mark.parametrize("enacted", ["2025-8-29", "08/29/2025", "2025-13", ""])
def test_enacted_must_be_a_date_for_multi_seat_states(rows, enacted):
    problems = validate_state_audit(with_row(rows, "TX", enacted=enacted))
    assert any(p.startswith("TX:") and "enacted" in p for p in problems)


@pytest.mark.parametrize("checked", ["2026-11", "20261104", "2026-W45-3", "2026-02-30"])
def test_checked_must_be_a_full_date(rows, checked):
    problems = validate_state_audit(with_row(rows, "TX", checked=checked))
    assert any(p.startswith("TX:") and "checked" in p for p in problems)


def test_at_large_states_must_say_at_large(rows):
    problems = validate_state_audit(with_row(rows, "WY", drawn_by="legislature"))
    assert any(p.startswith("WY:") and "at-large" in p for p in problems)


def test_multi_seat_states_cannot_be_at_large(rows):
    problems = validate_state_audit(with_row(rows, "TX", drawn_by="at-large"))
    assert any(p.startswith("TX:") and "at-large" in p for p in problems)


def test_changed_map_must_be_first_used_in_2026(rows):
    problems = validate_state_audit(
        with_row(rows, "TX", changed_since_2024="yes", first_used="2022", enacted="2025-08-29")
    )
    assert any(p.startswith("TX:") and "first_used" in p and "2026" in p for p in problems)


def test_map_first_used_in_2026_must_be_marked_changed(rows):
    problems = validate_state_audit(with_row(rows, "TX", first_used="2026"))
    assert any(p.startswith("TX:") and "changed_since_2024" in p for p in problems)


def test_unclear_rows_must_be_low_confidence_with_notes(rows):
    problems = validate_state_audit(with_row(rows, "TX", changed_since_2024="unclear"))
    assert any(p.startswith("TX:") and "unclear" in p for p in problems)
    ok = with_row(
        rows, "TX", changed_since_2024="unclear", confidence="low", notes="Court ruling pending."
    )
    assert validate_state_audit(ok) == []


def test_changed_states_lists_yes_and_unclear(rows):
    rows = with_row(rows, "TX", changed_since_2024="yes", first_used="2026", enacted="2025-08-29")
    rows = with_row(rows, "UT", changed_since_2024="unclear", confidence="low", notes="x")
    assert changed_states(rows) == {"yes": ["TX"], "unclear": ["UT"]}


def test_read_state_audit_checks_the_header(tmp_path):
    path = tmp_path / "states.csv"
    path.write_text("state,notes\nTX,x\n")
    with pytest.raises(ValueError, match="columns"):
        read_state_audit(path)


def test_read_state_audit_round_trip(tmp_path, rows):
    path = tmp_path / "states.csv"
    lines = [",".join(COLUMNS)] + [",".join(r[c] for c in COLUMNS) for r in rows]
    path.write_text("\n".join(lines) + "\n")
    assert read_state_audit(path) == rows
