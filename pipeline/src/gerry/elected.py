"""Who won each November 2026 U.S. House and Senate race, from the states' own results.

Two files in data/sources/members/, both transcribed by hand:

- results-2026.csv: for every House district on the 2026 ballot and every Senate seat that
  was up, the two leading candidates and their votes, from the state election office's
  unofficial results (public record), with the page each came from.
- uncalled-2026.csv: races that news organizations' decision desks hadn't called yet, or
  that go to a runoff, with when that list was checked.

A race counts as decided only when its leader leads the state's count AND the race isn't on
the uncalled list. The site never calls a race itself, and names nobody in an uncalled race.
A race whose state hasn't published statewide results yet has no leader and shows as pending.
Results stay unofficial until each state certifies them.
"""

import re
from pathlib import Path

import pandas as pd

_STATUSES = {"uncalled", "runoff"}
_PARTY_WORDS = [
    (re.compile(r"^(dem|democrat|democratic|democratic-farmer-labor|dfl)\b", re.I), "Democrat"),
    (re.compile(r"^(rep|republican|gop)\b", re.I), "Republican"),
    # Nebraska prints "By Petition" for a candidate on the ballot without a party.
    (re.compile(r"^by petition$", re.I), "Independent"),
]
# Suffixes that can follow a comma without the name being written last-name-first.
_SUFFIXES = {"Jr", "Sr", "II", "III", "IV"}
# Texas marks incumbents with "(I)" after the name.
_INCUMBENT_MARK = re.compile(r"\s*\(I\)\s*$")
# Lowercase prefixes that keep a capital after them: McDonald, MacArthur, O'Neil.
_INNER_CAPITAL = re.compile(r"\b(Mc|Mac|O')([a-z])")


def party_name(label: str) -> str:
    """Return a party in plain words: "Democrat", "Republican", or the state's own label.

    States print parties as "DEM", "Democratic", "Democratic-Farmer-Labor" (Minnesota's
    Democrats) and so on; these become one word so pages read the same everywhere.
    """
    text = label.strip()
    for pattern, word in _PARTY_WORDS:
        if pattern.match(text):
            return word
    return text


def display_name(name: str) -> str:
    """Return a candidate's name as it reads in a sentence.

    States print names in several styles, all put into one: "JARED GOLDEN" and "Andy BARR"
    (words in capitals), "CASE, Ed" and "Titus, Dina" (last name first, from Hawaii and
    Nevada), "Troy A. Carter, Sr." (a comma before a suffix) and "Greg Casar (I)" (Texas's
    mark for incumbents). Words already in mixed case are kept as the state printed them.
    """
    text = _INCUMBENT_MARK.sub("", " ".join(name.split()))
    before, comma, after = text.rpartition(", ")
    if comma:
        is_suffix = after.rstrip(".").title() in _SUFFIXES or after.rstrip(".") in _SUFFIXES
        text = f"{before} {after}" if is_suffix else f"{after} {before}"
    return " ".join(_word(w) for w in text.split())


def _word(word: str) -> str:
    """Write one word of a name normally if it's in capitals ("BARR" becomes "Barr").

    Initials ("J.") and Roman numerals ("III") stay as they are.
    """
    letters = [c for c in word if c.isalpha()]
    if len(letters) < 2 or word != word.upper() or word.rstrip(".") in _SUFFIXES:
        return word
    titled = word.title().replace("'S", "'s")
    return _INNER_CAPITAL.sub(lambda m: m.group(1) + m.group(2).upper(), titled)


def read_results(path: Path) -> pd.DataFrame:
    """Read results-2026.csv: one row per race, every column as text ("" when blank)."""
    return pd.read_csv(path, dtype=str, keep_default_na=False)


def read_uncalled(path: Path) -> pd.DataFrame:
    """Read uncalled-2026.csv, every column as text.

    Raises:
        ValueError: on a status other than "uncalled" or "runoff".
    """
    table = pd.read_csv(path, dtype=str, keep_default_na=False)
    bad = sorted(set(table["status"]) - _STATUSES)
    if bad:
        raise ValueError(f"Unknown status in the uncalled list: {', '.join(bad)}")
    return table


def _house_id(state: str, district: str) -> str:
    """Return a district ID, such as "ME-02" or "AK-AL", from a results row."""
    return f"{state}-{'AL' if district.upper() == 'AL' else f'{int(district):02d}'}"


def _outcome(row, open_races: dict) -> dict:
    """Return a race's outcome: elected (with name and party), uncalled, runoff or pending.

    Pending means the state hasn't published statewide results that could be read (some post
    results only by county until their official count); the row has no leader.
    """
    flagged = open_races.get((row.state, row.office, row.district))
    if flagged is not None:
        if flagged.status == "runoff":
            return {"status": "runoff", "runoff_date": flagged.runoff_date}
        return {"status": "uncalled"}
    if not row.leader.strip():
        return {"status": "pending"}
    return {
        "status": "elected",
        "name": display_name(row.leader),
        "party": party_name(row.leader_party),
    }


def _open_races(uncalled: pd.DataFrame) -> dict:
    """Index the uncalled list by (state, office, district)."""
    return {(r.state, r.office, r.district): r for r in uncalled.itertuples()}


def house_outcomes(results: pd.DataFrame, uncalled: pd.DataFrame) -> dict[str, dict]:
    """Return each House district's outcome, keyed by district ID (see _outcome)."""
    open_races = _open_races(uncalled)
    house = results[results["office"] == "house"]
    return {_house_id(r.state, r.district): _outcome(r, open_races) for r in house.itertuples()}


def senate_outcomes(results: pd.DataFrame, uncalled: pd.DataFrame) -> dict[tuple, dict]:
    """Return each Senate race's outcome, keyed by (state, "regular" or "special")."""
    open_races = _open_races(uncalled)
    senate = results[results["office"] == "senate"]
    return {(r.state, r.district): _outcome(r, open_races) for r in senate.itertuples()}


def result_problems(
    results: pd.DataFrame, uncalled: pd.DataFrame, district_ids: list[str]
) -> list[str]:
    """Return a problem for every district without exactly one result row.

    A row with no leader is allowed (the race shows as pending), but every district must have
    its row, so a state left out is caught. Every uncalled race must match a result row.
    """
    house = results[results["office"] == "house"]
    ids = [_house_id(s, d) for s, d in zip(house["state"], house["district"], strict=True)]
    counts = pd.Series(ids, dtype=str).value_counts()
    open_keys = set(_open_races(uncalled))
    problems = {}
    for district in district_ids:
        n = int(counts.get(district, 0))
        if n != 1:
            problems[district] = (
                f"{district}: {n} result rows" if n else f"{district}: no result row"
            )
    for district in sorted(set(counts.index) - set(district_ids)):
        problems[district] = f"{district}: not a 2026 district"
    row_keys = set(zip(results["state"], results["office"], results["district"], strict=True))
    for state, office, district in sorted(open_keys - row_keys):
        label = _house_id(state, district) if office == "house" else f"{state} Senate {district}"
        problems[label] = f"{label}: listed as uncalled but has no result row"
    return [problems[k] for k in sorted(problems)]


def senate_problems(results: pd.DataFrame, seats_up: set[tuple[str, str]]) -> list[str]:
    """Return a problem for every Senate seat up in 2026 without one result row, and the reverse.

    Args:
        results: From read_results.
        seats_up: (state, "regular" or "special") for every seat on the 2026 ballot.
    """
    senate = results[results["office"] == "senate"]
    keys = list(zip(senate["state"], senate["district"], strict=True))
    counts = pd.Series([f"{s} Senate {d}" for s, d in keys], dtype=str).value_counts()
    problems = []
    for state, seat in sorted(seats_up | set(keys)):
        label = f"{state} Senate {seat}"
        n = int(counts.get(label, 0))
        if (state, seat) not in seats_up:
            problems.append(f"{label}: no seat was up")
        elif n != 1:
            problems.append(f"{label}: {n} result rows" if n else f"{label}: no result row")
    return problems


def state_sources(results: pd.DataFrame) -> dict[str, dict[str, str]]:
    """Return each state's results page: publisher, url and the date it was checked."""
    first = results.drop_duplicates("state").sort_values("state")
    return {
        r.state: {"publisher": r.publisher, "url": r.source_url, "checked": r.checked}
        for r in first.itertuples()
    }
