"""Bring swapped-in state maps to the same level of detail as the Census file.

State district files are drawn at full detail, while the Census cartographic file is
generalized to 1:500,000. Measured perimeter grows with detail, so without this step
the swapped-in districts would score as less compact than Census districts for no
real reason. Clipping a full-detail file to the Census state outline also leaves
small slivers where the two disagree.

Both settings were calibrated by running the Census Bureau's own full-detail CD119
districts for 12 unchanged states through the same steps and comparing them with its
1:500,000 version (`python -m gerry calibrate`):

- Every clipping artifact was at most 0.084 km2, and every real separate piece of a
  district at least 0.94 km2, so pieces under 0.25 km2 that touch another district
  are artifacts.
- The Census 1:500,000 file has no piece under 0.01 km2 anywhere in the country, so
  isolated specks smaller than that are dropped.
- A 75 m tolerance matched Polsby-Popper scores best: median ratio 0.998, 80% of
  districts within -0.9% to +0.5%. Without simplification the median was 1.8% low.
"""

from collections.abc import Callable

import geopandas as gpd
import shapely
from pyproj import CRS, Transformer
from shapely.geometry import MultiPolygon
from shapely.geometry.base import BaseGeometry

MAX_FRAGMENT_KM2 = 0.25
# The Census 1:500,000 district file has no piece smaller than this.
MIN_PIECE_KM2 = 0.01
TOLERANCE_M = 75
# Shared border shorter than this (metres) counts as touching at a point.
MIN_SHARED_M = 1.0


def local_crs(geometry: BaseGeometry) -> CRS:
    """Return an equal-area projection in metres centred on a (lon/lat) geometry."""
    c = geometry.centroid
    return CRS.from_proj4(f"+proj=laea +lat_0={c.y} +lon_0={c.x} +ellps=GRS80 +units=m +no_defs")


def _projector(crs: CRS, around: BaseGeometry) -> Callable[[BaseGeometry], BaseGeometry]:
    """Return a function that projects a geometry from crs into metres around a geometry."""
    lonlat = gpd.GeoSeries([around], crs=crs).to_crs("EPSG:4326").iloc[0]
    transformer = Transformer.from_crs(crs, local_crs(lonlat), always_xy=True)
    return lambda geometry: shapely.transform(geometry, transformer.transform, interleaved=False)


def _absorbing_neighbour(
    part: BaseGeometry, own: int, geoms: dict, project: Callable, max_km2: float
) -> int | None:
    """Return the district a stray piece should join, or None to keep it where it is."""
    projected = project(part)
    if projected.area / 1e6 >= max_km2:
        return None
    shared = {
        other: projected.boundary.intersection(project(geometry)).length
        for other, geometry in geoms.items()
        if other != own
    }
    best = max(shared, key=shared.get, default=None)
    return best if best is not None and shared[best] > MIN_SHARED_M else None


def _absorb_state(geoms: dict, project: Callable, max_km2: float) -> dict:
    """Run absorb_fragments over one state's districts, keyed by row label."""
    for own in list(geoms):
        parts = sorted(shapely.get_parts(geoms[own]), key=lambda p: -project(p).area)
        keep = [parts[0]]
        for part in parts[1:]:
            target = _absorbing_neighbour(part, own, geoms, project, max_km2)
            if target is not None:
                geoms[target] = shapely.union(geoms[target], part)
            elif project(part).area / 1e6 >= MIN_PIECE_KM2:
                keep.append(part)  # a real island; smaller specks are dropped
        geoms[own] = keep[0] if len(keep) == 1 else MultiPolygon(keep)
    return geoms


def absorb_fragments(
    districts: gpd.GeoDataFrame, max_km2: float = MAX_FRAGMENT_KM2
) -> gpd.GeoDataFrame:
    """Merge small stray pieces into the neighbouring district they share the most border with.

    A piece (other than a district's largest) moves when it is under max_km2 and shares
    a border with another district in the same state. Islands, which touch no other
    district, stay unless they are under MIN_PIECE_KM2, the smallest piece the Census
    1:500,000 file keeps. Larger pieces stay. Returns a new frame.
    """
    result = districts.copy()
    for _, labels in districts.groupby("state").groups.items():
        geoms = {label: districts.geometry.loc[label] for label in labels}
        project = _projector(districts.crs, shapely.union_all(list(geoms.values())))
        for label, geometry in _absorb_state(geoms, project, max_km2).items():
            result.loc[label, "geometry"] = geometry
    return result


def simplify_to_census(
    districts: gpd.GeoDataFrame, tolerance_m: float = TOLERANCE_M
) -> gpd.GeoDataFrame:
    """Simplify internal district borders to roughly the Census 1:500,000 level.

    Borders stay shared, so no gaps or overlaps appear, and each state's outer edge
    (already the Census outline) is left alone. Returns a new frame in the same CRS.
    """
    result = districts.copy()
    if tolerance_m == 0:
        return result
    for _, labels in districts.groupby("state").groups.items():
        rows = districts.loc[labels]
        center = rows.to_crs("EPSG:4326").union_all()
        projected = rows.to_crs(local_crs(center))
        simplified = shapely.coverage_simplify(
            projected.geometry.to_numpy(), tolerance_m, simplify_boundary=False
        )
        back = gpd.GeoSeries(simplified, index=rows.index, crs=projected.crs).to_crs(rows.crs)
        result.loc[labels, "geometry"] = back
    return result
