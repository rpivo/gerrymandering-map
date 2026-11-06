"""2024 presidential votes by congressional district, from MIT's precinct-level returns.

The presidential file lists votes by precinct but not by congressional district. The House file
uses the same precinct IDs and says which district each precinct voted in, so joining the two
places each precinct's presidential votes in its district. This only works where the 2024
districts were used again in 2026; redrawn states need other sources.

Two states need official data on top: King County, WA is a single county-wide row in MIT's file,
so the county's own precinct file replaces it; and New Jersey's counts are short in some
counties (Mercer has no early votes), so each county is scaled to the official totals in
data/sources/votes/. Redrawn states can't use the join; Texas and North Carolina published
2024 results on their new maps (`OFFICIAL_RESULTS`).

Rules, each found in the data (see plans/PLAN.md section 3.3):
- Count each precinct once: its TOTAL rows if it has them, else the sum of its other modes.
- Ignore House rows with zero votes (Ohio lists every precinct under all 15 districts) and
  rows whose district isn't a number (Rhode Island adds STATEWIDE rows).
- Drop rows that total other rows: town totals and county totals (New Jersey's Bergen and
  Gloucester counties list both, doubling their votes).
- A precinct in more than one district is split by its House votes. A big row (a county's mail
  ballots, say) is split the same way, but each district gets its own partisan mix, taken from
  the county's single-district precincts (Missouri, Oklahoma).
- A precinct whose name differs from the House file's only by a municipal type ("Deptford Twp"
  and "Deptford", Gloucester County, NJ) takes the House precinct's districts, unless the
  President file already uses that name in the same county.
- A row marked NONPARTISAN takes its party from party_detailed (MIT's 2024 presidential file
  marks all of Nebraska's rows NONPARTISAN).
- A precinct with no House votes goes to the state's unopposed district if it has exactly one
  (Oklahoma's 3rd had no race on the ballot), else each party's votes are spread the way that
  party's matched votes are spread across the county's districts.
"""

import re
from pathlib import Path

import pandas as pd

from gerry.fetch import Source
from gerry.states import STATES_BY_USPS

KEY = ["state_po", "county_fips", "jurisdiction_fips", "precinct"]
COLUMNS = KEY + ["mode", "party_detailed", "party_simplified", "votes", "district"]
# party_simplified values that party_detailed overrides for the two major parties.
_UNLABELED = {"NONPARTISAN"}
# A non-exact row bigger than this is a catch-all (a county's mail ballots, a whole county),
# so splitting it gives every district the same partisan mix. The share of votes in such rows
# says how far to trust a state's district results.
BIG_ROW_VOTES = 5000
KING_COUNTY_FIPS = "53033"
# A town or county total row may differ from the precincts it totals by this share (rounding).
AGGREGATE_TOLERANCE = 0.01

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


KING_COUNTY_2024 = Source(
    id="wa-king-county-precincts-2024-votes",
    url="https://data.kingcounty.gov/api/views/uuda-pmuy/rows.csv?accessType=DOWNLOAD",
    publisher="King County Elections (King County open data)",
    license="Public domain",
    description=(
        "November 2024 General Election Final Precinct Results, with each precinct's "
        "congressional district. Page: https://data.kingcounty.gov/d/uuda-pmuy"
    ),
    filename="November_2024_General_Election_Final_Precinct_Results.csv",
)


def read_precinct_returns(path: Path) -> pd.DataFrame:
    """Read an MIT precinct returns CSV. Codes stay strings; redacted votes ("*") count as 0.

    MIT's 2024 presidential file marks all of Nebraska's rows NONPARTISAN in party_simplified,
    though party_detailed names the party, so a Democratic or Republican party_detailed wins.
    """
    df = pd.read_csv(path, usecols=COLUMNS, dtype=str, keep_default_na=False)
    df["votes"] = pd.to_numeric(df["votes"], errors="coerce").fillna(0.0)
    fix = df["party_simplified"].isin(_UNLABELED) & df["party_detailed"].isin(
        ["DEMOCRAT", "REPUBLICAN"]
    )
    df.loc[fix, "party_simplified"] = df.loc[fix, "party_detailed"]
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
    """Place precincts the House file covers, splitting multi-district ones by weight.

    A big multi-district row is a catch-all (a county's mail ballots), not a precinct. Its
    House votes still say how many of its voters live in each district, but each district
    gets its own partisan mix, taken from the county's single-district precincts.
    """
    m = two.merge(weights, on=KEY)
    parts = m.groupby(KEY)["district"].transform("size")
    m["kind"] = parts.map(lambda n: "exact" if n == 1 else "split")
    m["row_votes"] = m["dem"] + m["rep"]
    big = (m["kind"] == "split") & (m["row_votes"] > BIG_ROW_VOTES)
    shares = m[["dem", "rep"]].mul(m["weight"], axis=0)
    split, m["own_mix"] = _party_shares(m, big), False
    shares[big] = split[["dem", "rep"]]
    # A row where any district had no county pattern is only as good as a uniform split.
    m.loc[big, "own_mix"] = split["own_mix"].groupby([m.loc[big, k] for k in KEY]).transform("any")
    m[["dem", "rep"]] = shares
    return m


def _party_shares(m: pd.DataFrame, big: pd.Series) -> pd.DataFrame:
    """Split big rows' votes by House weight times each district's county mix, party by party."""
    county = ["state_po", "county_fips", "district"]
    exact = m[m["kind"] == "exact"].groupby(county)[["dem", "rep"]].sum()
    mix = (exact["dem"] / (exact["dem"] + exact["rep"])).rename("mix").reset_index()
    rows = m[big].reset_index().merge(mix, on=county, how="left").set_index("index")
    out = pd.DataFrame({"own_mix": rows["mix"].isna()}, index=rows.index)
    # A district with no single-district precincts in the county takes the row's own mix.
    rows["mix"] = rows["mix"].fillna(rows["dem"] / rows["row_votes"])
    for party, seed in (("dem", rows["mix"]), ("rep", 1 - rows["mix"])):
        weight = rows["weight"] * seed
        total = weight.groupby([rows[k] for k in KEY]).transform("sum")
        out[party] = rows[party] * (weight / total).fillna(0.0)
    return out


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
    # Each party's unmatched votes follow where that party's matched votes are in the county.
    county = ["state_po", "county_fips"]
    share = matched.groupby(county + ["district"], as_index=False)[["dem", "rep"]].sum()
    for party in ("dem", "rep"):
        share[f"w_{party}"] = share[party] / share.groupby(county)[party].transform("sum")
    b = unmatched[~to_lone].merge(share.drop(columns=["dem", "rep"]), on=county, how="left")
    b["kind"] = b["district"].isna().map({True: "lost", False: "county"})
    for party in ("dem", "rep"):
        b[party] = b[party] * b[f"w_{party}"].fillna(1.0)
    b = b.drop(columns=["w_dem", "w_rep"])
    return pd.concat([a, b], ignore_index=True)


_MUNICIPAL_SUFFIX = re.compile(r"\s+(TWP|TOWNSHIP|BORO|BOROUGH|CITY|TOWN|VILLAGE)$")


def _town(name: str) -> str:
    """A precinct name without a trailing municipal type, for loose matching."""
    return _MUNICIPAL_SUFFIX.sub("", name.strip().upper())


def _rename_by_town(two: pd.DataFrame, weights: pd.DataFrame) -> pd.DataFrame:
    """Give unmatched precincts the House file's name when only the municipal type differs.

    Gloucester County, NJ lists "Deptford Twp" for President and "Deptford" for the House. A
    match is used only when exactly one House precinct in the county has that short name.
    """
    county = ["state_po", "county_fips", "jurisdiction_fips"]
    house = weights[KEY].drop_duplicates().assign(town=lambda d: d["precinct"].map(_town))
    unique = house.groupby(county + ["town"]).filter(lambda g: len(g) == 1)
    unmatched = _unmatched(two, weights).drop(columns="row_votes")
    unmatched = unmatched.assign(town=unmatched["precinct"].map(_town))
    hits = unmatched.merge(unique, on=county + ["town"], suffixes=("", "_house"))
    # A House name the President file already uses in the same county is that precinct's own.
    taken = pd.MultiIndex.from_frame(two[KEY])
    house_keys = pd.MultiIndex.from_frame(hits[county + ["precinct_house"]].set_axis(KEY, axis=1))
    hits = hits[~house_keys.isin(taken)]
    hit_keys = pd.MultiIndex.from_frame(hits[KEY])
    rename = dict(zip(hit_keys, hits["precinct_house"], strict=True))
    keys = pd.MultiIndex.from_frame(two[KEY])
    return two.assign(precinct=[rename.get(k, k[3]) for k in keys])


def assign_to_districts(
    two: pd.DataFrame, weights: pd.DataFrame, unopposed: dict[str, list[int]]
) -> pd.DataFrame:
    """Place every precinct's two-party presidential votes in congressional districts.

    Returns one row per precinct part: state, district (missing for votes that couldn't be
    placed), kind (exact, split, unopposed, county or lost), dem, rep, and row_votes, the
    precinct row's whole two-party vote, for judging how much rests on catch-all rows.
    """
    two = _rename_by_town(two, weights)
    matched = _matched(two, weights)
    placed = _place_unmatched(_unmatched(two, weights), matched, unopposed)
    out = pd.concat([matched, placed], ignore_index=True)
    out = out.rename(columns={"state_po": "state"})
    out["district"] = out["district"].astype("Int64")
    out["own_mix"] = out["own_mix"].fillna(False).astype(bool)
    return out[["state", "district", "kind", "dem", "rep", "row_votes", "own_mix"]]


def state_quality(assigned: pd.DataFrame) -> pd.DataFrame:
    """Per state, the percent of two-party votes placed exactly, in big catch-all rows, and lost."""
    a = assigned.assign(t=assigned["dem"] + assigned["rep"])
    # Catch-all rows that couldn't follow a county pattern: big unmatched rows, and big split
    # rows where a district had no single-district precincts in the county.
    big = a["row_votes"] > BIG_ROW_VOTES
    a["big"] = big & ((a["kind"] == "county") | a["own_mix"].fillna(False).astype(bool))
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
    return out.assign(method="precinct join")


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


def _aggregate_keys(totals: pd.Series) -> set[tuple]:
    """Find the precinct keys in one county that only repeat other rows' votes."""
    names = {key[3]: key for key in totals.index}
    children: dict[str, list[str]] = {}
    for name in names:
        base = re.sub(r"\s+\d+\w*$", "", name)
        if base != name:
            children.setdefault(base, []).append(name)
    drop = set()
    for name, key in names.items():
        if "COUNTY TOTAL" in name.upper():
            parts = totals.drop(index=key).sum()
        elif name in children:
            parts = sum(totals[names[c]] for c in children[name])
        else:
            continue
        if abs(totals[key] - parts) <= AGGREGATE_TOLERANCE * max(parts, 1):
            drop.add(key)
    return drop


def drop_aggregate_rows(df: pd.DataFrame) -> pd.DataFrame:
    """Drop rows that only total other rows: town totals and county totals.

    A town total is "Allendale" over "Allendale 1", "Allendale 2". New Jersey's Bergen and
    Gloucester counties list both kinds, doubling their votes.

    A row is dropped only if its votes match the rows it would total, to within 1%.
    """
    totals = df.groupby(KEY)["votes"].sum()
    drop = set()
    for _, county in totals.groupby(level=["state_po", "county_fips"]):
        drop |= _aggregate_keys(county)
    if not drop:
        return df
    keys = pd.MultiIndex.from_frame(df[KEY])
    return df[~keys.isin(list(drop))].reset_index(drop=True)


def read_king_county(path: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Read King County's own 2024 precinct results (WA).

    MIT's file has King County as one 1.08 million vote row spanning four districts. The
    county's file has every precinct and the congressional district it's in.

    Returns:
        Two-party votes per precinct (as `two_party_by_precinct`) and each precinct's district
        with weight 1 (as `district_weights`), keyed like MIT's rows with state WA, county 53033
        and precincts prefixed "KC ".
    """
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    df = df[df["Race"].str.startswith("President and Vice President")]
    candidate = df["CounterType"].map(_kc_party)
    df = df.assign(party=candidate, votes=pd.to_numeric(df["SumOfCount"])).dropna(subset=["party"])
    df = df.assign(
        state_po="WA", county_fips=KING_COUNTY_FIPS, jurisdiction_fips=KING_COUNTY_FIPS,
        precinct="KC " + df["Precinct"],
    )  # fmt: skip
    two = df.pivot_table(index=KEY, columns="party", values="votes", aggfunc="sum")
    two = two.reindex(columns=["dem", "rep"]).fillna(0.0).astype(float).reset_index()
    weights = df[KEY + ["CongressionalDistrict"]].drop_duplicates()
    weights = weights.rename(columns={"CongressionalDistrict": "district"})
    weights = weights.assign(district=weights["district"].astype(int), weight=1.0)
    return two.rename_axis(columns=None), weights.reset_index(drop=True)


def _kc_party(candidate: str) -> str | None:
    """Map King County's candidate labels to dem or rep; None for everyone else."""
    if candidate.startswith("Kamala D. Harris"):
        return "dem"
    return "rep" if candidate.startswith("Donald J. Trump") else None


def replace_county(
    two: pd.DataFrame, weights: pd.DataFrame, new_two: pd.DataFrame, new_weights: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Drop every row of the counties in `new_two` and add the new rows in their place."""
    counties = new_two[["state_po", "county_fips"]].drop_duplicates().assign(_new=True)

    def keep(df: pd.DataFrame) -> pd.DataFrame:
        flagged = df.merge(counties, on=["state_po", "county_fips"], how="left")
        return df[flagged["_new"].isna().to_numpy()]

    return (
        pd.concat([keep(two), new_two], ignore_index=True),
        pd.concat([keep(weights), new_weights], ignore_index=True),
    )


def calibrate_to_county_totals(two: pd.DataFrame, official: pd.DataFrame) -> pd.DataFrame:
    """Scale each listed county's precinct votes, party by party, to its official totals.

    For counties whose precinct data is incomplete (New Jersey's Mercer County has no early
    votes): the missing votes are assumed to be spread like the county's other votes.

    Args:
        two: Two-party votes per precinct.
        official: Columns state, county_fips, harris, trump.

    Raises:
        ValueError: if a listed county has no precinct votes to scale.
    """
    county = ["state_po", "county_fips"]
    ours = two.groupby(county)[["dem", "rep"]].sum()
    target = official.rename(columns={"state": "state_po"}).set_index(county)
    missing = target.index.difference(ours.index)
    if len(missing):
        raise ValueError(f"No precinct votes to scale in {', '.join(c for _, c in missing)}.")
    ours = ours.reindex(target.index).astype(float)
    factors = pd.DataFrame(
        {
            "f_dem": target["harris"].astype(float) / ours["dem"],
            "f_rep": target["trump"].astype(float) / ours["rep"],
        }
    )
    out = two.merge(factors.reset_index(), on=county, how="left")
    for party in ("dem", "rep"):
        out[party] = out[party] * out[f"f_{party}"].fillna(1.0)
    return out.drop(columns=["f_dem", "f_rep"])


# Redrawn states whose legislature published 2024 president results on the 2026 map,
# transcribed in data/sources/votes/ (see its README).
OFFICIAL_RESULTS = {
    "TX": "tx-planc2333-president-2024.csv",
    "NC": "nc-s249-president-2024.csv",
}


def read_official_results(path: Path) -> pd.DataFrame:
    """Read a transcribed official report of presidential votes by district.

    Returns rows like `district_totals` (state, district, dem, rep, dem_share) plus
    method "official report".
    """
    df = pd.read_csv(path, dtype={"state": str})
    out = df.rename(columns={"harris": "dem", "trump": "rep"})[["state", "district", "dem", "rep"]]
    out = out.astype({"district": int, "dem": float, "rep": float})
    out["dem_share"] = out["dem"] / (out["dem"] + out["rep"])
    return out.assign(method="official report")
