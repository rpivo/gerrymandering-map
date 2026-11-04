"""Load Census congressional district boundaries into a standard shape.

Census district files have one row per district with a state FIPS code (`STATEFP`)
and a district code in a column named for the Congress, such as `CD119FP`. The code
is `00` for at-large districts and `98` for DC and the territories' delegates.
"""

import re
from pathlib import Path

import geopandas as gpd
import pandas as pd
from shapely.geometry.base import BaseGeometry

from gerry.states import STATES_BY_FIPS

_DISTRICT_COLUMN = re.compile(r"^CD\d{3}FP$")
_DISTRICT_CODE = re.compile(r"^\d{2}$")
AT_LARGE_CODE = "00"


def district_id(usps: str, code: str) -> str:
    """Return the standard ID for a district, such as `TX-35` or `WY-AL`.

    Args:
        usps: Two-letter state code.
        code: Census two-digit district code. `00` means at-large.

    Raises:
        ValueError: if code is not a two-digit district number or `00`.
    """
    if not _DISTRICT_CODE.match(code) or code == "98":
        raise ValueError(f"Not a congressional district code: {code!r}")
    return f"{usps}-{'AL' if code == AT_LARGE_CODE else code}"


def _district_column(raw: gpd.GeoDataFrame) -> str:
    """Return the name of the Census district code column, such as `CD119FP`."""
    matches = [c for c in raw.columns if _DISTRICT_COLUMN.match(str(c))]
    if len(matches) != 1:
        raise ValueError(f"Expected one district column like CD119FP, found {matches}")
    return matches[0]


def normalize_districts(raw: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """Turn a Census district file into one row per district with standard IDs.

    Drops DC and the territories, which have non-voting delegates.

    Returns:
        Columns `district_id`, `state` (USPS code), `number` (nullable integer, null
        for at-large) and `geometry`, sorted by `district_id`, in the input's CRS.
    """
    column = _district_column(raw)
    states = raw[raw["STATEFP"].isin(STATES_BY_FIPS.keys())]
    usps = states["STATEFP"].map(lambda fips: STATES_BY_FIPS[fips].usps)
    codes = states[column]
    ids = [district_id(s, c) for s, c in zip(usps, codes, strict=True)]  # validates codes
    numbers = codes.where(codes != AT_LARGE_CODE).astype("Int64")
    result = gpd.GeoDataFrame(
        {
            "district_id": ids,
            "state": usps.to_numpy(),
            "number": pd.array(numbers, dtype="Int64"),
            "geometry": states.geometry.to_numpy(),
        },
        geometry="geometry",
        crs=raw.crs,
    )
    return result.sort_values("district_id", ignore_index=True)


def load_state_outlines(path: Path) -> dict[str, BaseGeometry]:
    """Read a Census state boundary file into {USPS code: outline} for the 50 states.

    The cartographic boundary files are clipped to the shoreline, so these outlines
    are the land each state's districts are clipped to.
    """
    location = f"zip://{path}" if path.suffix == ".zip" else path
    states = gpd.read_file(location)
    states = states[states["STATEFP"].isin(STATES_BY_FIPS.keys())]
    return {
        STATES_BY_FIPS[fips].usps: geometry
        for fips, geometry in zip(states["STATEFP"], states.geometry, strict=True)
    }


def load_districts(path: Path) -> gpd.GeoDataFrame:
    """Read a Census district file (shapefile, zip or GeoPackage) and normalize it."""
    location = f"zip://{path}" if path.suffix == ".zip" else path
    return normalize_districts(gpd.read_file(location))
