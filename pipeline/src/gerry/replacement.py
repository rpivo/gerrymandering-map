"""Swap in current district maps for states that redrew after the 2024 election.

The Census CD119 file has the lines used in 2024. For states whose 2026 map differs
(see `data/sources/states.csv`), we load the state's official district file, put it in
the same shape as the Census rows, and clip it to the state's shoreline-clipped
Census outline so every district is measured the same way (state files usually
extend into lakes and the ocean).
"""

import geopandas as gpd
import pandas as pd
import shapely
from shapely.geometry import MultiPolygon
from shapely.geometry.base import BaseGeometry

from gerry.states import STATES_BY_USPS

CENSUS_CRS = "EPSG:4269"
EQUAL_AREA_CRS = "EPSG:6933"


def _district_numbers(values: pd.Series, state: str) -> pd.Series:
    """Parse district numbers such as 1, "01" or 1.0, rejecting anything outside 1..seats."""
    seats = STATES_BY_USPS[state].seats
    numbers = pd.to_numeric(values, errors="coerce")
    bad = values[numbers.isna() | (numbers % 1 != 0) | (numbers < 1) | (numbers > seats)]
    if not bad.empty:
        raise ValueError(f"{state}: district values {sorted(map(str, bad))} not in 1..{seats}.")
    return numbers.astype(int)


def normalize_state_map(raw: gpd.GeoDataFrame, state: str, field: str) -> gpd.GeoDataFrame:
    """Turn one state's district file into standard rows.

    Args:
        raw: The state's district file, in any CRS.
        state: Two-letter state code.
        field: Name of the column holding the district number.

    Returns:
        One row per district with `district_id`, `state`, `number` and `geometry`,
        in the Census CRS, sorted by district number.

    Raises:
        ValueError: if the field is missing, or the districts are not exactly 1..seats.
    """
    if field not in raw.columns:
        raise ValueError(f"{state}: no {field!r} column in {list(raw.columns)}.")
    numbers = _district_numbers(raw[field], state)
    seats = STATES_BY_USPS[state].seats
    if set(numbers) != set(range(1, seats + 1)):
        missing = sorted(set(range(1, seats + 1)) - set(numbers))
        raise ValueError(f"{state}: missing districts {missing}.")
    shapes = gpd.GeoDataFrame({"number": numbers}, geometry=raw.geometry.make_valid(), crs=raw.crs)
    merged = shapes.dissolve(by="number", as_index=False).to_crs(CENSUS_CRS)
    merged = merged.sort_values("number", ignore_index=True)
    return gpd.GeoDataFrame(
        {
            "district_id": [f"{state}-{n:02d}" for n in merged["number"]],
            "state": state,
            "number": pd.array(merged["number"], dtype="Int64"),
            "geometry": merged.geometry.to_numpy(),
        },
        geometry="geometry",
        crs=CENSUS_CRS,
    )


def _polygons_only(geometry: BaseGeometry) -> BaseGeometry:
    """Drop the points and lines an intersection can leave where shapes only touch."""
    parts = [p for p in shapely.get_parts(geometry) if p.geom_type == "Polygon"]
    return parts[0] if len(parts) == 1 else MultiPolygon(parts)


def clip_to_land(districts: gpd.GeoDataFrame, land: BaseGeometry) -> gpd.GeoDataFrame:
    """Clip districts to the state's shoreline-clipped outline. Returns a new frame."""
    clipped = districts.copy()
    clipped["geometry"] = [_polygons_only(g.intersection(land)) for g in districts.geometry]
    return clipped


def coverage_gap(districts: gpd.GeoDataFrame, land: BaseGeometry) -> float:
    """Return the share of the state's land (0 to 1) not covered by any district."""
    projected = districts.to_crs(EQUAL_AREA_CRS)
    land_area = gpd.GeoSeries([land], crs=districts.crs).to_crs(EQUAL_AREA_CRS).iloc[0]
    return land_area.difference(projected.union_all()).area / land_area.area


def replace_states(
    national: gpd.GeoDataFrame, replacements: dict[str, gpd.GeoDataFrame]
) -> gpd.GeoDataFrame:
    """Replace whole states' districts in the national set.

    Raises:
        ValueError: if a replacement contains rows for a different state than its key.
    """
    for state, rows in replacements.items():
        others = sorted(set(rows["state"]) - {state})
        if others:
            raise ValueError(f"Replacement for {state} contains rows for {others}.")
    kept = national[~national["state"].isin(replacements.keys())]
    combined = pd.concat([kept, *replacements.values()], ignore_index=True)
    return gpd.GeoDataFrame(combined, geometry="geometry", crs=national.crs).sort_values(
        "district_id", ignore_index=True
    )


def check_audit_match(
    changed: dict[str, list[str]], registered: set[str], pending: set[str] | None = None
) -> list[str]:
    """Check that replacements exist exactly for the states the audit marks as changed.

    Args:
        changed: Output of `gerry.state_audit.changed_states`.
        registered: States with a replacement map registered.
        pending: Changed states knowingly left on their 2024 lines for now.
    """
    pending = pending or set()
    problems = [
        f"{s}: audit says unclear; resolve it before building the map." for s in changed["unclear"]
    ]
    problems += [
        f"{s}: changed since 2024 but no replacement map is registered."
        for s in sorted(set(changed["yes"]) - registered - pending)
    ]
    problems += [
        f"{s}: marked pending but the audit says unchanged."
        for s in sorted(pending - set(changed["yes"]))
    ]
    problems += [
        f"{s}: marked pending but also has a replacement map." for s in sorted(pending & registered)
    ]
    problems += [
        f"{s}: has a replacement map but the audit says unchanged."
        for s in sorted(registered - set(changed["yes"]))
    ]
    return problems
