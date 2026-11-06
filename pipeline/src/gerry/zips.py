"""The ZIP codes in each district, from the Census Bureau's ZIP Code Tabulation Areas.

A ZIP code is a set of mail delivery routes, not an area on a map. For statistics, the
Census Bureau draws ZIP Code Tabulation Areas (ZCTAs): each 2020 census block goes to the
ZIP code most of its addresses use, so a ZCTA is a group of whole blocks that matches a
residential ZIP code closely. ZIP codes used only for PO boxes or one large organization,
and ZIP codes created since 2020, have none.

Blocks are already placed in districts (see gerry.population), so adding up a ZCTA's
residents by district says how many of its 2020 residents live in each district. ZCTAs
cross state lines, so a ZCTA's share is of its residents across every state.
"""

import pandas as pd

from gerry.fetch import Source

ZCTA_BLOCKS = Source(
    id="census-zcta520-tabblock20",
    url=(
        "https://www2.census.gov/geo/docs/maps-data/data/rel2020/zcta520/"
        "tab20_zcta520_tabblock20_natl.txt"
    ),
    publisher="U.S. Census Bureau",
    license="Public domain (U.S. Government work)",
    description=(
        "2020 ZIP Code Tabulation Area to 2020 census block relationship file: the ZIP code "
        "area each block belongs to. Page: https://www.census.gov/geographies/reference-files/"
        "time-series/geo/relationship-files.2020.html"
    ),
)

_COLUMNS = {"GEOID_ZCTA5_20": "zcta", "GEOID_TABBLOCK_20": "block", "AREALAND_PART": "land"}


def read_zcta_blocks(path) -> pd.DataFrame:
    """Read the ZCTA-to-block file into one row per block that has a ZIP code area.

    The file is about 1 GB, so only three columns are read, as numbers. A block listed in
    two ZCTAs (a few on ZCTA edges) goes to the one holding more of its land.

    Returns:
        block (the 15-digit block GEOID as an integer) and zcta (the 5-digit ZCTA code as an
        integer; write it back with five digits).
    """
    table = pd.read_csv(
        path,
        sep="|",
        usecols=list(_COLUMNS),
        dtype={"GEOID_ZCTA5_20": "Int32", "GEOID_TABBLOCK_20": "int64", "AREALAND_PART": "int64"},
        encoding="utf-8-sig",
    ).rename(columns=_COLUMNS)
    table = table.dropna(subset=["zcta"])
    table = table.sort_values(["block", "land"], ascending=[True, False], kind="stable")
    table = table.drop_duplicates("block")
    return table[["block", "zcta"]].astype({"zcta": "int32"}).reset_index(drop=True)


def district_zctas(placed: pd.DataFrame, zcta_blocks: pd.DataFrame) -> pd.DataFrame:
    """Count each ZCTA's 2020 residents in each district.

    Args:
        placed: Blocks from gerry.population.assign_blocks: geoid, district_id and pop.
        zcta_blocks: From read_zcta_blocks.

    Returns:
        district_id, zcta and pop (residents of the ZCTA in the district), for every pair
        with residents. Blocks in no ZCTA are left out.
    """
    blocks = placed[["geoid", "district_id", "pop"]].assign(block=placed["geoid"].astype("int64"))
    joined = blocks.merge(zcta_blocks, on="block", how="inner")
    counts = joined.groupby(["district_id", "zcta"], as_index=False)["pop"].sum()
    return counts[counts["pop"] > 0].reset_index(drop=True)


def zcta_shares(counts: pd.DataFrame) -> pd.DataFrame:
    """Add share: the part of each ZCTA's residents, in every state, living in the district.

    Args:
        counts: district_zctas for every state, concatenated.

    Returns:
        counts with share, a 0 to 1 ratio.
    """
    totals = counts.groupby("zcta")["pop"].transform("sum")
    return counts.assign(share=counts["pop"] / totals)
