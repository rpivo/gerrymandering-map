"""Each state's two U.S. senators, from the Senate's own list of current members.

Senators are elected statewide, so district lines don't affect them: every district in a
state shares the same two. The list is the Senate's contact list, which it keeps current.
It changes when a senator leaves or takes office (next on January 3, 2027, for the seats on
the November 2026 ballot), and the checksum in the sources manifest then stops matching, so
a refresh is deliberate (see the README).
"""

import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

import pandas as pd

from gerry.fetch import Source
from gerry.states import STATES

SENATORS = Source(
    id="senate-senators",
    url="https://www.senate.gov/general/contact_information/senators_cfm.xml",
    publisher="U.S. Senate",
    license="Public domain (U.S. Government work)",
    description=(
        "Senators of the United States: contact information for current senators, "
        "with name, party and state. Page: https://www.senate.gov/senators/"
    ),
)

_PARTIES = {"D": "Democrat", "R": "Republican", "I": "Independent"}


def display_name(first: str, last: str) -> str:
    """Return a senator's name as it reads in a sentence.

    The Senate puts a suffix after the first name ("Angus S., Jr."); it goes after the last
    name instead: "Angus S. King Jr.".
    """
    given, _, suffix = first.partition(",")
    return " ".join(p for p in (given.strip(), last.strip(), suffix.strip()) if p)


def read_senators(path: Path) -> pd.DataFrame:
    """Read the Senate's list of senators.

    Returns:
        state (USPS code), last (last name, for sorting), name (see display_name) and party
        ("Democrat", "Republican" or "Independent"), in file order.

    Raises:
        ValueError: on a party letter other than D, R or I, rather than guessing its name.
    """
    rows = []
    for m in ET.parse(path).getroot().iter("member"):
        letter = (m.findtext("party") or "").strip()
        if letter not in _PARTIES:
            raise ValueError(f"Unknown party {letter!r} for {m.findtext('member_full')}")
        last = (m.findtext("last_name") or "").strip()
        rows.append({
            "state": (m.findtext("state") or "").strip(),
            "last": last,
            "name": display_name(m.findtext("first_name") or "", last),
            "party": _PARTIES[letter],
        })  # fmt: skip
    return pd.DataFrame(rows, columns=["state", "last", "name", "party"])


def senator_problems(table: pd.DataFrame) -> list[str]:
    """Return a problem for every state (or other place) without exactly two senators.

    A place that isn't one of the 50 states should have none.
    """
    counts = Counter(table["state"])
    expected = {s.usps: 2 for s in STATES}
    return [
        f"{state}: {counts.get(state, 0)} senators, expected {expected.get(state, 0)}"
        for state in sorted(set(counts) | set(expected))
        if counts.get(state, 0) != expected.get(state, 0)
    ]
