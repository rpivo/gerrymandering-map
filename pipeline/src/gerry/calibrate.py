"""Calibrate gerry.generalize against the Census Bureau's own two versions of CD119.

The Census publishes the same 2024 districts at full detail (TIGER/Line) and
generalized to 1:500,000 (the cartographic file the site uses). Running the
full-detail districts of unchanged states through the same steps as a swapped-in
state file, then comparing with the 1:500,000 versions, shows:

1. how big clipping artifacts get compared with real separate pieces of districts
   (which sets MAX_FRAGMENT_KM2), and
2. which simplification tolerance makes scores match (which sets TOLERANCE_M).

Run it with `python -m gerry calibrate`. It downloads about 11 MB of TIGER files.
"""

import math
from collections.abc import Iterable
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely
from shapely.geometry.base import BaseGeometry

from gerry.boundaries import load_districts, load_state_outlines, normalize_districts
from gerry.fetch import CENSUS_CD119, CENSUS_STATES, Source, fetch
from gerry.generalize import MIN_SHARED_M, absorb_fragments, local_crs, simplify_to_census
from gerry.replacement import clip_to_land
from gerry.states import STATES_BY_USPS

# Unchanged states with a mix of coastline, rivers, lakes and inland borders.
CALIBRATION_STATES = ("AZ", "CO", "GA", "IL", "MA", "MI", "MN", "NJ", "NY", "PA", "VA", "WA")
TOLERANCES_M = (0, 25, 50, 75, 100, 150, 200, 300)


def tiger_source(state: str) -> Source:
    """Return the Census full-detail (TIGER/Line 2025) CD119 file for a state."""
    fips = STATES_BY_USPS[state].fips
    return Source(
        id=f"census-tiger-cd119-2025-{fips}",
        url=f"https://www2.census.gov/geo/tiger/TIGER2025/CD/tl_2025_{fips}_cd119.zip",
        publisher="U.S. Census Bureau",
        license="Public domain (U.S. Government work)",
        description=f"TIGER/Line 2025, 119th Congress districts, full detail, {state}. "
        "Used only to calibrate gerry.generalize.",
    )


def load_tiger_districts(path: Path) -> gpd.GeoDataFrame:
    """Read a TIGER CD119 file into standard rows, dropping unassigned water (code ZZ)."""
    location = f"zip://{path}" if path.suffix == ".zip" else path
    raw = gpd.read_file(location)
    district_column = next(c for c in raw.columns if c.startswith("CD") and c.endswith("FP"))
    return normalize_districts(raw[raw[district_column] != "ZZ"])


def polsby_popper(geometry: BaseGeometry) -> float:
    """Return 4 pi area / perimeter squared: 1 for a circle, lower for less compact shapes."""
    return 4 * math.pi * geometry.area / geometry.length**2


def _projected_by_state(districts: gpd.GeoDataFrame) -> dict[str, gpd.GeoDataFrame]:
    """Project each state's districts into metres around that state, indexed by district."""
    out = {}
    for state, rows in districts.groupby("state"):
        crs = local_crs(rows.to_crs("EPSG:4326").union_all())
        out[state] = rows.set_index("district_id").to_crs(crs)
    return out


def sweep(
    candidate: gpd.GeoDataFrame, reference: gpd.GeoDataFrame, tolerances: Iterable[float]
) -> list[dict]:
    """Compare simplified candidate districts with reference districts at each tolerance.

    Returns one row per tolerance: the median boundary points per km, and the median
    and 10th/90th percentile of candidate Polsby-Popper divided by reference.
    """
    refs = _projected_by_state(reference)
    rows = []
    for tolerance in tolerances:
        ratios, density = [], []
        for state, cand in _projected_by_state(simplify_to_census(candidate, tolerance)).items():
            ref = refs[state].to_crs(cand.crs)
            for district, geometry in cand.geometry.items():
                ratios.append(polsby_popper(geometry) / polsby_popper(ref.geometry.loc[district]))
                density.append(shapely.get_num_coordinates(geometry) / (geometry.length / 1000))
        rows.append(
            {
                "tolerance_m": tolerance,
                "points_per_km": float(np.median(density)),
                "pp_ratio_median": float(np.median(ratios)),
                "pp_ratio_p10": float(np.percentile(ratios, 10)),
                "pp_ratio_p90": float(np.percentile(ratios, 90)),
            }
        )
    return rows


def _touching_pieces(districts: gpd.GeoDataFrame) -> list[tuple[str, BaseGeometry, float]]:
    """Return (district, piece in lon/lat, km2) for stray pieces touching another district."""
    pieces = []
    for state_rows in _projected_by_state(districts).values():
        for district, geometry in state_rows.geometry.items():
            others = state_rows.drop(index=district).union_all()
            for part in sorted(shapely.get_parts(geometry), key=lambda p: -p.area)[1:]:
                if part.boundary.intersection(others).length > MIN_SHARED_M:
                    lonlat = gpd.GeoSeries([part], crs=state_rows.crs).to_crs("EPSG:4326").iloc[0]
                    pieces.append((district, lonlat, part.area / 1e6))
    return pieces


def touching_piece_sizes(districts: gpd.GeoDataFrame) -> list[float]:
    """Return sizes (km2) of stray pieces that share a border with another district."""
    return sorted((km2 for _, _, km2 in _touching_pieces(districts)), reverse=True)


def clipping_artifacts(candidate: gpd.GeoDataFrame, reference: gpd.GeoDataFrame) -> list[float]:
    """Return sizes (km2) of candidate touching pieces with no counterpart in the reference.

    A piece is real if it overlaps a touching piece of the same district in the
    reference; otherwise clipping created it.
    """
    real = _touching_pieces(reference)
    return sorted(
        (
            km2
            for district, piece, km2 in _touching_pieces(candidate)
            if not any(d == district and piece.intersects(r) for d, r, _ in real)
        ),
        reverse=True,
    )


def calibrate(repo_root: Path) -> int:
    """Download the calibration files, print the evidence for both settings."""
    data = repo_root / "data"
    raw, manifest = data / "raw", data / "sources" / "sources.csv"
    states = list(CALIBRATION_STATES)
    reference = load_districts(fetch(CENSUS_CD119, raw, manifest)).query("state in @states")
    land = load_state_outlines(fetch(CENSUS_STATES, raw, manifest))
    tiger = [load_tiger_districts(fetch(tiger_source(s), raw, manifest)) for s in states]
    clipped = pd.concat(
        [
            clip_to_land(t.to_crs(reference.crs), land[s])
            for t, s in zip(tiger, states, strict=True)
        ],
        ignore_index=True,
    )
    clipped = gpd.GeoDataFrame(clipped, geometry="geometry", crs=reference.crs)
    real, artifacts = touching_piece_sizes(reference), clipping_artifacts(clipped, reference)
    print(
        f"Pieces touching another district, 1:500,000 file: smallest {min(real, default=0):.3f} km2"
    )
    print(
        f"Clipping artifacts in full-detail file: {len(artifacts)}, "
        f"largest {max(artifacts, default=0):.3f} km2"
    )
    print("tolerance_m  points/km  PP ratio median [p10, p90]")
    for r in sweep(absorb_fragments(clipped), reference, TOLERANCES_M):
        print(
            f"{r['tolerance_m']:11}  {r['points_per_km']:9.2f}  {r['pp_ratio_median']:.3f} "
            f"[{r['pp_ratio_p10']:.3f}, {r['pp_ratio_p90']:.3f}]"
        )
    return 0
