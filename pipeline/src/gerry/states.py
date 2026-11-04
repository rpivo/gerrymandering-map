"""The 50 states, their FIPS codes, and their House seats under the 2020 apportionment.

DC and the territories elect non-voting delegates, so they are not included.
Source: U.S. Census Bureau, 2020 Census Apportionment Results.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    """A state and its number of congressional districts."""

    usps: str
    fips: str
    name: str
    seats: int


# (USPS code, FIPS code, name, seats)
_ROWS = [
    ("AL", "01", "Alabama", 7),
    ("AK", "02", "Alaska", 1),
    ("AZ", "04", "Arizona", 9),
    ("AR", "05", "Arkansas", 4),
    ("CA", "06", "California", 52),
    ("CO", "08", "Colorado", 8),
    ("CT", "09", "Connecticut", 5),
    ("DE", "10", "Delaware", 1),
    ("FL", "12", "Florida", 28),
    ("GA", "13", "Georgia", 14),
    ("HI", "15", "Hawaii", 2),
    ("ID", "16", "Idaho", 2),
    ("IL", "17", "Illinois", 17),
    ("IN", "18", "Indiana", 9),
    ("IA", "19", "Iowa", 4),
    ("KS", "20", "Kansas", 4),
    ("KY", "21", "Kentucky", 6),
    ("LA", "22", "Louisiana", 6),
    ("ME", "23", "Maine", 2),
    ("MD", "24", "Maryland", 8),
    ("MA", "25", "Massachusetts", 9),
    ("MI", "26", "Michigan", 13),
    ("MN", "27", "Minnesota", 8),
    ("MS", "28", "Mississippi", 4),
    ("MO", "29", "Missouri", 8),
    ("MT", "30", "Montana", 2),
    ("NE", "31", "Nebraska", 3),
    ("NV", "32", "Nevada", 4),
    ("NH", "33", "New Hampshire", 2),
    ("NJ", "34", "New Jersey", 12),
    ("NM", "35", "New Mexico", 3),
    ("NY", "36", "New York", 26),
    ("NC", "37", "North Carolina", 14),
    ("ND", "38", "North Dakota", 1),
    ("OH", "39", "Ohio", 15),
    ("OK", "40", "Oklahoma", 5),
    ("OR", "41", "Oregon", 6),
    ("PA", "42", "Pennsylvania", 17),
    ("RI", "44", "Rhode Island", 2),
    ("SC", "45", "South Carolina", 7),
    ("SD", "46", "South Dakota", 1),
    ("TN", "47", "Tennessee", 9),
    ("TX", "48", "Texas", 38),
    ("UT", "49", "Utah", 4),
    ("VT", "50", "Vermont", 1),
    ("VA", "51", "Virginia", 11),
    ("WA", "53", "Washington", 10),
    ("WV", "54", "West Virginia", 2),
    ("WI", "55", "Wisconsin", 8),
    ("WY", "56", "Wyoming", 1),
]

STATES: tuple[State, ...] = tuple(State(*row) for row in _ROWS)
STATES_BY_FIPS: dict[str, State] = {s.fips: s for s in STATES}
STATES_BY_USPS: dict[str, State] = {s.usps: s for s in STATES}
TOTAL_SEATS = sum(s.seats for s in STATES)
