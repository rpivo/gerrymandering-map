"""Partisan fairness measures for a state's congressional map.

Each takes two-party votes (Democratic and Republican) by district and returns a number where
0 means neither party is favored. Sign convention, used throughout the site: **positive favors
Republicans, negative favors Democrats.** All are measured on the 2024 presidential vote, so a
"seat" here means the district the party's presidential candidate carried.

- Efficiency gap: the difference in the two parties' wasted votes as a share of all votes. A
  vote is wasted if it was cast for the loser, or for the winner beyond the half needed to win.
- Mean-median difference: a party's average district vote share minus its median one. When
  the median is below the mean, the party's voters are packed into a few lopsided districts.
- Declination (Warrington 2018): the angle between the two parties' winning districts when
  districts are sorted by vote share, scaled to -1 to 1. Undefined if one party wins every seat.

These measures are noisy with few districts, so states need MIN_DISTRICTS to be scored.
"""

import math
from collections.abc import Sequence
from statistics import mean, median

import pandas as pd

MIN_DISTRICTS = 4


def efficiency_gap(dem: Sequence[float], rep: Sequence[float]) -> float:
    """Return the efficiency gap from votes by district, as a share of all votes (-1 to 1).

    Positive means Democrats waste more votes, which favors Republicans.
    """
    wasted_dem = wasted_rep = 0.0
    for d, r in zip(dem, rep, strict=True):
        needed = (d + r) / 2
        if d > r:
            wasted_dem += d - needed
            wasted_rep += r
        else:
            wasted_rep += r - needed
            wasted_dem += d
    return (wasted_dem - wasted_rep) / (sum(dem) + sum(rep))


def mean_median(dem_shares: Sequence[float]) -> float:
    """Return the mean minus the median Democratic share (a 0 to 1 share difference).

    Positive means the median district is less Democratic than the average, favoring Republicans.
    """
    return mean(dem_shares) - median(dem_shares)


def declination(dem_shares: Sequence[float]) -> float | None:
    """Return the declination (-1 to 1) from Democratic shares by district.

    Returns None if one party wins every district, where the measure is undefined.

    Positive means Democratic wins are more lopsided than Republican ones, favoring Republicans.
    """
    dem_won = [s for s in dem_shares if s > 0.5]
    rep_won = [s for s in dem_shares if s <= 0.5]
    if not dem_won or not rep_won:
        return None
    n = len(dem_shares)
    theta_rep = math.atan((0.5 - mean(rep_won)) / (len(rep_won) / n / 2))
    theta_dem = math.atan((mean(dem_won) - 0.5) / (len(dem_won) / n / 2))
    return 2 / math.pi * (theta_dem - theta_rep)


def state_fairness(totals: pd.DataFrame) -> pd.DataFrame:
    """Score every state with at least MIN_DISTRICTS districts.

    Args:
        totals: Votes by district: state, district, dem, rep, dem_share, method.

    Returns:
        One row per state: districts, dem_vote_share (0 to 1), dem_seats, efficiency_gap,
        mean_median, declination (missing if one party carried every district) and method.
    """
    rows = []
    for state, g in totals.groupby("state"):
        if len(g) < MIN_DISTRICTS:
            continue
        shares = g["dem_share"].tolist()
        rows.append(
            {
                "state": state,
                "districts": len(g),
                "dem_vote_share": g["dem"].sum() / (g["dem"].sum() + g["rep"].sum()),
                "dem_seats": int((g["dem_share"] > 0.5).sum()),
                "efficiency_gap": efficiency_gap(g["dem"].tolist(), g["rep"].tolist()),
                "mean_median": mean_median(shares),
                "declination": declination(shares),
                "method": g["method"].iloc[0],
            }
        )
    return pd.DataFrame(rows)
