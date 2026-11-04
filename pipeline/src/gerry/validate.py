"""Checks that a set of districts is complete and well formed.

Each check returns a list of plain-language problems. `validate_districts` runs them
all, so one run reports everything that is wrong rather than stopping at the first.
"""

import geopandas as gpd
import pandas as pd
import shapely
from shapely.validation import explain_validity

from gerry.states import STATES, STATES_BY_USPS, TOTAL_SEATS

# Equal-area projection, so overlap areas are comparable anywhere in the country.
EQUAL_AREA_CRS = "EPSG:6933"
# Overlaps smaller than this are slivers from generalized boundaries, not real overlaps.
OVERLAP_TOLERANCE_KM2 = 0.01


def check_total(districts: gpd.GeoDataFrame) -> list[str]:
    """Check that there are exactly 435 districts."""
    if len(districts) == TOTAL_SEATS:
        return []
    return [f"Found {len(districts)} districts, expected {TOTAL_SEATS}."]


def check_unique_ids(districts: gpd.GeoDataFrame) -> list[str]:
    """Check that no district ID appears twice."""
    dupes = sorted(districts.loc[districts["district_id"].duplicated(), "district_id"].unique())
    return [f"Duplicate district IDs: {', '.join(dupes)}."] if dupes else []


def check_states(districts: gpd.GeoDataFrame) -> list[str]:
    """Check each state's district count and numbering against its apportionment."""
    problems = [
        f"{usps}: not a state (DC and territories have no voting districts)."
        for usps in sorted(set(districts["state"]) - STATES_BY_USPS.keys())
    ]
    for state in STATES:
        rows = districts[districts["state"] == state.usps]
        if len(rows) != state.seats:
            problems.append(f"{state.usps}: {len(rows)} districts, expected {state.seats}.")
        problems.extend(_check_numbering(state.usps, state.seats, rows["number"]))
    return problems


def _check_numbering(usps: str, seats: int, numbers: pd.Series) -> list[str]:
    """Check that an at-large state is unnumbered and others are numbered 1 to seats."""
    if numbers.empty:
        return []
    if seats == 1:
        return [] if numbers.isna().all() else [f"{usps}: should be a single at-large district."]
    problems = []
    if numbers.isna().any():
        problems.append(f"{usps}: has an at-large district but {seats} seats.")
    missing = sorted(set(range(1, seats + 1)) - set(numbers.dropna()))
    if missing:
        problems.append(f"{usps}: missing district numbers {', '.join(map(str, missing))}.")
    return problems


def check_geometry(districts: gpd.GeoDataFrame) -> list[str]:
    """Check that every district has a non-empty, valid shape."""
    problems = []
    for district, geometry in zip(districts["district_id"], districts.geometry, strict=True):
        if geometry is None or geometry.is_empty:
            problems.append(f"{district}: empty geometry.")
        elif not geometry.is_valid:
            problems.append(f"{district}: invalid geometry ({explain_validity(geometry)}).")
    return problems


def check_overlaps(districts: gpd.GeoDataFrame) -> list[str]:
    """Check that no two districts in the same state overlap by more than the tolerance."""
    geoms = districts.geometry.to_numpy()
    usable = ~shapely.is_missing(geoms) & ~shapely.is_empty(geoms) & shapely.is_valid(geoms)
    shapes = districts[usable].to_crs(EQUAL_AREA_CRS)
    pairs = gpd.sjoin(shapes, shapes, predicate="intersects")
    pairs = pairs[
        (pairs["state_left"] == pairs["state_right"])
        & (pairs["district_id_left"] < pairs["district_id_right"])
    ]
    problems = []
    for left_index, row in pairs.iterrows():
        right = shapes.geometry.loc[row["index_right"]]
        area_km2 = shapes.geometry.loc[left_index].intersection(right).area / 1e6
        if area_km2 > OVERLAP_TOLERANCE_KM2:
            problems.append(
                f"{row['district_id_left']} and {row['district_id_right']} "
                f"overlap by {area_km2:.2f} km2."
            )
    return problems


def validate_districts(districts: gpd.GeoDataFrame) -> list[str]:
    """Return a list of problems with the districts. An empty list means all checks pass."""
    return [
        *check_total(districts),
        *check_unique_ids(districts),
        *check_states(districts),
        *check_geometry(districts),
        *check_overlaps(districts),
    ]
