"""2024 presidential votes by congressional district, from MIT's precinct-level returns.

The presidential file lists votes by precinct but not by congressional district. The House file
uses the same precinct IDs and says which district each precinct voted in, so joining the two
places each precinct's presidential votes in its district. This only works where the 2024
districts were used again in 2026; redrawn states need other sources.

Rules, each found in the data (see plans/PLAN.md section 3.3):
- Count each precinct once: its TOTAL rows if it has them, else the sum of its other modes.
- Ignore House rows with zero votes (Ohio lists every precinct under all 15 districts) and
  rows whose district isn't a number (Rhode Island adds STATEWIDE rows).
- A precinct in more than one district is split by its House votes.
- A precinct with no House votes goes to the state's unopposed district if it has exactly one
  (Oklahoma's 3rd had no race on the ballot), else is spread by its county's matched votes.
"""

from pathlib import Path

import pandas as pd

from gerry.fetch import Source
from gerry.states import STATES_BY_USPS

KEY = ["state_po", "county_fips", "jurisdiction_fips", "precinct"]
COLUMNS = KEY + ["mode", "party_simplified", "votes", "district"]
# A non-exact row bigger than this is a catch-all (a county's mail ballots, a whole county),
# so splitting it gives every district the same partisan mix. The share of votes in such rows
# says how far to trust a state's district results.
BIG_ROW_VOTES = 5000

_MEDSL = "MIT Election Data and Science Lab (Harvard Dataverse)"
_PAGE = "https://doi.org/10.7910/DVN/"

PRESIDENT_2024 = Source(
    id="medsl-president-precinct-2024",
    url="https://dataverse.harvard.edu/api/access/datafile/13730901",
    publisher=_MEDSL,
    license="CC0 1.0 (public domain dedication)",
    description=f"U.S. President Precinct-Level Returns 2024. Page: {_PAGE}XDJYKC",
    filename="PRESIDENT_precinct_general.csv",
)

HOUSE_2024 = Source(
    id="medsl-house-precinct-2024",
    url="https://dataverse.harvard.edu/api/access/datafile/13731101",
    publisher=_MEDSL,
    license="CC0 1.0 (public domain dedication)",
    description=f"U.S. House of Representatives Precinct-Level Returns 2024. Page: {_PAGE}USBYR4",
    filename="HOUSE_precinct_general.csv",
)


def read_precinct_returns(path: Path) -> pd.DataFrame:
    """Read an MIT precinct returns CSV. Codes stay strings; redacted votes ("*") count as 0."""
    df = pd.read_csv(path, usecols=COLUMNS, dtype=str, keep_default_na=False)
    df["votes"] = pd.to_numeric(df["votes"], errors="coerce").fillna(0.0)
    return df


def one_count_per_precinct(df: pd.DataFrame) -> pd.DataFrame:
    """Keep a precinct's TOTAL rows if it has any, else all its rows, so no vote counts twice."""
    has_total = df.loc[df["mode"] == "TOTAL", KEY].drop_duplicates().assign(_total=True)
    df = df.merge(has_total, on=KEY, how="left")
    keep = df["_total"].isna() | (df["mode"] == "TOTAL")
    return df.loc[keep].drop(columns="_total").reset_index(drop=True)


def two_party_by_precinct(df: pd.DataFrame) -> pd.DataFrame:
    """Return Democratic and Republican presidential votes per precinct (columns: KEY, dem, rep)."""
    parties = {"DEMOCRAT": "dem", "REPUBLICAN": "rep"}
    df = df[df["party_simplified"].isin(parties)]
    wide = df.groupby(KEY + ["party_simplified"])["votes"].sum().unstack()
    wide = wide.rename(columns=parties).reindex(columns=["dem", "rep"]).astype(float).fillna(0.0)
    return wide.reset_index().rename_axis(columns=None)


def district_weights(house: pd.DataFrame) -> pd.DataFrame:
    """Return each precinct's districts and the share of its House votes in each.

    Columns: KEY, district (int), weight (0 to 1, summing to 1 per precinct).
    """
    house = house[house["district"].str.isdigit() & (house["votes"] > 0)]
    w = house.groupby(KEY + ["district"], as_index=False)["votes"].sum()
    w["district"] = w["district"].astype(int)
    w["weight"] = w["votes"] / w.groupby(KEY)["votes"].transform("sum")
    return w.drop(columns="votes")


def unopposed_districts(weights: pd.DataFrame) -> dict[str, list[int]]:
    """Return, per multi-seat state, the districts with no House votes anywhere (no race held)."""
    found = weights.groupby("state_po")["district"].agg(set)
    missing = {}
    for state, districts in found.items():
        seats = STATES_BY_USPS[state].seats if state in STATES_BY_USPS else 0
        gaps = sorted(set(range(1, seats + 1)) - districts) if seats > 1 else []
        if gaps:
            missing[str(state)] = gaps
    return missing


def _matched(two: pd.DataFrame, weights: pd.DataFrame) -> pd.DataFrame:
    """Place precincts the House file covers, splitting multi-district ones by weight."""
    m = two.merge(weights, on=KEY)
    parts = m.groupby(KEY)["district"].transform("size")
    m["kind"] = parts.map(lambda n: "exact" if n == 1 else "split")
    m["row_votes"] = m["dem"] + m["rep"]
    m[["dem", "rep"]] = m[["dem", "rep"]].mul(m["weight"], axis=0)
    return m


def _unmatched(two: pd.DataFrame, weights: pd.DataFrame) -> pd.DataFrame:
    """Return the precincts the House file doesn't cover."""
    seen = weights[KEY].drop_duplicates().assign(_seen=True)
    u = two.merge(seen, on=KEY, how="left")
    return (
        u[u["_seen"].isna()].drop(columns="_seen").assign(row_votes=lambda d: d["dem"] + d["rep"])
    )


def _place_unmatched(
    unmatched: pd.DataFrame, matched: pd.DataFrame, unopposed: dict[str, list[int]]
) -> pd.DataFrame:
    """Send unmatched precincts to a lone unopposed district, else spread them by county."""
    lone = {s: d[0] for s, d in unopposed.items() if len(d) == 1}
    to_lone = unmatched["state_po"].isin(list(lone))
    a = unmatched[to_lone].assign(district=lambda d: d["state_po"].map(lone), kind="unopposed")
    county = ["state_po", "county_fips"]
    share = (
        matched.assign(t=matched["dem"] + matched["rep"])
        .groupby(county + ["district"], as_index=False)["t"]
        .sum()
    )
    share["weight"] = share["t"] / share.groupby(county)["t"].transform("sum")
    b = unmatched[~to_lone].merge(share.drop(columns="t"), on=county, how="left")
    b["kind"] = b["district"].isna().map({True: "lost", False: "county"})
    b[["dem", "rep"]] = b[["dem", "rep"]].mul(b["weight"].fillna(1.0), axis=0)
    return pd.concat([a, b], ignore_index=True)


def assign_to_districts(
    two: pd.DataFrame, weights: pd.DataFrame, unopposed: dict[str, list[int]]
) -> pd.DataFrame:
    """Place every precinct's two-party presidential votes in congressional districts.

    Returns one row per precinct part: state, district (missing for votes that couldn't be
    placed), kind (exact, split, unopposed, county or lost), dem, rep, and row_votes, the
    precinct row's whole two-party vote, for judging how much rests on catch-all rows.
    """
    matched = _matched(two, weights)
    placed = _place_unmatched(_unmatched(two, weights), matched, unopposed)
    out = pd.concat([matched, placed], ignore_index=True)
    out = out.rename(columns={"state_po": "state"})
    out["district"] = out["district"].astype("Int64")
    return out[["state", "district", "kind", "dem", "rep", "row_votes"]]


def state_quality(assigned: pd.DataFrame) -> pd.DataFrame:
    """Per state, the percent of two-party votes placed exactly, in big catch-all rows, and lost."""
    a = assigned.assign(t=assigned["dem"] + assigned["rep"])
    a["big"] = (a["kind"] != "exact") & (a["row_votes"] > BIG_ROW_VOTES)
    total = a.groupby("state")["t"].sum()
    pct = pd.DataFrame(
        {
            "exact_pct": a[a["kind"] == "exact"].groupby("state")["t"].sum(),
            "big_row_pct": a[a["big"]].groupby("state")["t"].sum(),
            "lost_pct": a[a["kind"] == "lost"].groupby("state")["t"].sum(),
        }
    )
    pct = (100 * pct.div(total, axis=0)).reindex(total.index).fillna(0.0)
    return pct.reset_index().round(2)


def district_totals(assigned: pd.DataFrame) -> pd.DataFrame:
    """Sum placed votes per district: state, district, dem, rep and dem_share (0 to 1)."""
    placed = assigned[assigned["district"].notna()]
    out = placed.groupby(["state", "district"], as_index=False)[["dem", "rep"]].sum()
    out["dem_share"] = out["dem"] / (out["dem"] + out["rep"])
    return out


def check_reference(
    totals: pd.DataFrame, state: str, reference: pd.DataFrame, tolerance_pts: float
) -> list[str]:
    """Compare one state's district results with published ones.

    Args:
        totals: Output of `district_totals`.
        state: Two-letter state code.
        reference: Published results with columns district, harris, trump.
        tolerance_pts: Largest allowed difference in Democratic share, in percentage points.

    Returns:
        One problem per district that is missing or differs by more than the tolerance.
    """
    ours = totals[totals["state"] == state].set_index("district")["dem_share"]
    problems = []
    for r in reference.itertuples():
        label = f"{state}-{int(r.district):02d}"
        published = r.harris / (r.harris + r.trump)
        if r.district not in ours.index:
            problems.append(f"{label}: missing from the results.")
        elif abs(100 * (ours[r.district] - published)) > tolerance_pts:
            problems.append(
                f"{label}: Democratic share {ours[r.district]:.2%} vs published {published:.2%}."
            )
    return problems
