"""Voting-age population by race and Hispanic origin for every district, from 2020 Census blocks.

The 2020 redistricting file (PL 94-171) gives each census block's population, its
voting-age population (18 and over) by race and Hispanic origin (table P4), and a point
inside the block. Each block is placed in the district whose shape contains that point.
The district shapes are simplified at the edges, so a few blocks on a coast fall just
outside every district; those go to the nearest district in the same state.

Groups follow table P4: Hispanic or Latino of any race, non-Hispanic white people (white
alone), and non-Hispanic people who are Black, American Indian and Alaska Native, Asian, or
Native Hawaiian and Pacific Islander, alone or with another race, as Voting Rights Act
analyses count them. A person of two minority races counts in both, so groups can overlap.
"Minority" is everyone except non-Hispanic white people.

Every map in use was drawn on 2020 Census data with nearly equal populations, so each
district's 2020 population should be close to its state's average. That is the check.
"""

import zipfile
from itertools import combinations
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

from gerry.fetch import Source
from gerry.states import STATES_BY_USPS

PL_BASE = (
    "https://www2.census.gov/programs-surveys/decennial/2020/data/01-Redistricting_File--PL_94-171"
)
GROUPS = ["hispanic", "nh_white", "nh_black", "nh_aian", "nh_asian", "nh_nhpi"]
# A district's 2020 population may differ from its state's average by at most this share.
# Most maps are drawn to within a person or two of the raw Census counts. California,
# Maryland, New Jersey, Virginia and some others draw on counts that move prisoners to their
# home addresses, so districts with large prisons run high on raw counts: CA-22 is the
# largest at +2.3% (24,114 people in adult prisons; under 0.7% with them taken out).
MAX_POPULATION_DEVIATION = 0.03

# 0-based field positions in the PL 94-171 geoheader (97 fields, pipe-delimited).
_GEO_FIELDS = {"sumlev": 2, "logrecno": 7, "geoid": 9, "pop": 90, "lat": 92, "lon": 93}
_BLOCK = "750"
# Segment 2 holds five ID fields, then table P3 (71 counts), then table P4 (73 counts).
_P4_START = 5 + 71
# Not-Hispanic part of P4, from position 3: one race, the six races alone, two or more races,
# then for 2 to 6 races a subtotal and every combination in this race order.
_RACES = "WBIAPO"  # white, Black, AIAN, Asian, NHPI, some other race
_NH_COLUMNS = ["one_race", *_RACES, "two_or_more"]
for _k in range(2, 7):
    _NH_COLUMNS += [f"{_k}_races", *("".join(c) for c in combinations(_RACES, _k))]
# P4 positions (0-based within P4) added up for the voting-age total and each group.
# Minority groups count people of that race alone or with other races, as Voting Rights Act
# analyses do ("any part Black"); white means white alone, so minority = vap - nh_white.
_P4_FIELDS = {"vap": [0], "hispanic": [1], "nh_white": [3 + _NH_COLUMNS.index("W")]}
for _group, _race in [("nh_black", "B"), ("nh_aian", "I"), ("nh_asian", "A"), ("nh_nhpi", "P")]:
    _P4_FIELDS[_group] = [
        3 + i for i, c in enumerate(_NH_COLUMNS) if set(c) <= set(_RACES) and _race in c
    ]


def pl_source(state: str) -> Source:
    """Return the 2020 Census redistricting file (PL 94-171) for a state."""
    info = STATES_BY_USPS[state]
    folder = info.name.replace(" ", "_")
    return Source(
        id=f"census-pl94171-2020-{info.fips}",
        url=f"{PL_BASE}/{folder}/{state.lower()}2020.pl.zip",
        publisher="U.S. Census Bureau",
        license="Public domain (U.S. Government work)",
        description=f"2020 Census Redistricting Data (PL 94-171), {info.name}: population "
        "and voting-age population by race and Hispanic origin for every block.",
    )


def read_pl_blocks(path: Path) -> pd.DataFrame:
    """Read a state's PL 94-171 zip into one row per block.

    Returns:
        geoid, lat, lon (a point inside the block, NAD83 degrees), pop (all ages), vap
        (18 and over) and each group in GROUPS (voting-age counts).
    """
    with zipfile.ZipFile(path) as zf:
        names = zf.namelist()
        geo_name = next(n for n in names if n.endswith("geo2020.pl"))
        seg2_name = next(n for n in names if n.endswith("000022020.pl"))
        with zf.open(geo_name) as f:
            geo = pd.read_csv(f, sep="|", header=None, dtype=str, encoding="latin-1",
                              usecols=list(_GEO_FIELDS.values()))  # fmt: skip
        with zf.open(seg2_name) as f:
            p4 = pd.read_csv(f, sep="|", header=None, dtype=str)
    # read_csv keeps file order whatever order usecols lists, so name columns by position.
    geo = geo.rename(columns={i: n for n, i in _GEO_FIELDS.items()})
    counts = pd.DataFrame({"logrecno": p4[4]})
    for name, positions in _P4_FIELDS.items():
        counts[name] = sum(p4[_P4_START + i].astype(int) for i in positions)
    blocks = geo[geo["sumlev"] == _BLOCK].merge(counts, on="logrecno", validate="one_to_one")
    blocks["pop"] = blocks["pop"].astype(int)
    for column in ["lat", "lon"]:
        blocks[column] = blocks[column].astype(float)
    return blocks[["geoid", "lat", "lon", "pop", *_P4_FIELDS]].reset_index(drop=True)


def assign_blocks(blocks: pd.DataFrame, districts: gpd.GeoDataFrame) -> pd.DataFrame:
    """Place each block in a district of its state.

    Args:
        blocks: From read_pl_blocks, plus a `state` column (USPS code).
        districts: `district_id`, `state` and `geometry`, in NAD83 degrees (EPSG:4269).

    Returns:
        The blocks with `district_id`, and `placed` ("inside", or "nearest" for a block
        whose point fell outside every district in its state).
    """
    out = blocks.copy()
    out["district_id"] = None
    out["placed"] = "inside"
    for state, rows in out.groupby("state"):
        mine = districts[districts["state"] == state].reset_index(drop=True)
        tree = shapely.STRtree(mine.geometry.values)
        points = shapely.points(rows["lon"].to_numpy(), rows["lat"].to_numpy())
        hit = np.full(len(rows), -1)
        point_i, district_i = tree.query(points, predicate="within")
        hit[point_i] = district_i
        missing = hit < 0
        # Distances in degrees are fine for ranking districts a few hundred meters away.
        hit[missing] = tree.query_nearest(points[missing], all_matches=False)[1]
        out.loc[rows.index, "district_id"] = mine["district_id"].to_numpy()[hit]
        out.loc[rows.index[missing], "placed"] = "nearest"
    return out


def district_population(placed: pd.DataFrame) -> pd.DataFrame:
    """Add up placed blocks by district.

    Returns:
        One row per district: district_id, state, pop, vap, each group's voting-age count,
        `minority` (vap minus non-Hispanic white), and `nearest_pop`, the population of
        blocks placed by distance rather than inside the district.
    """
    counts = ["pop", "vap", *GROUPS]
    table = placed.groupby(["district_id", "state"], as_index=False)[counts].sum()
    table["minority"] = table["vap"] - table["nh_white"]
    nearest = placed[placed["placed"] == "nearest"].groupby("district_id")["pop"].sum()
    table["nearest_pop"] = table["district_id"].map(nearest).fillna(0).astype(int)
    return table.sort_values("district_id", ignore_index=True)


def population_problems(table: pd.DataFrame) -> list[str]:
    """Return a problem for every district whose population is off its state's average.

    The limit is MAX_POPULATION_DEVIATION; states must also have every district present.
    """
    problems = []
    for state, rows in table.groupby("state"):
        seats = STATES_BY_USPS[state].seats
        if len(rows) != seats:
            problems.append(f"{state}: population for {len(rows)} of {seats} districts")
        average = rows["pop"].mean()
        for row in rows.itertuples():
            deviation = row.pop / average - 1
            if abs(deviation) > MAX_POPULATION_DEVIATION:
                problems.append(
                    f"{row.district_id}: 2020 population {row.pop:,} is {deviation:+.1%} "
                    f"off the state average {average:,.0f}"
                )
    return problems
