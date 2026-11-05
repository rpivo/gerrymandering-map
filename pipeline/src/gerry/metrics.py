"""Compactness metrics for one district shape.

All four take a shape in meters (or any equal-area units). `compactness` handles the
projection: each district is measured in a Lambert azimuthal equal-area projection
centered on itself, which keeps distortion small anywhere, Alaska and Hawaii included.

A district made of several pieces uses its total area and total perimeter, and one
hull and one circle around all the pieces.

Reock and convex hull are measured against land: given the state's land, they count
only the part of the circle or hull that is on it. Water between islands, or beyond
a coast, is space no district could use, so it doesn't count against a district,
while land a district leaves out still does. Polsby-Popper has no such adjustment.

`state_edge_share` measures how much of a district's border is the state's own edge (a
coast, national border or state line), which mapmakers don't choose. It isn't part of
the score; district pages show it as context.
"""

import math

import shapely
from pyproj import CRS, Transformer
from shapely.geometry.base import BaseGeometry

from gerry.generalize import local_crs

# Segments per quarter circle when building the enclosing circle to clip it to land.
CIRCLE_SEGMENTS = 128


def polsby_popper(geometry: BaseGeometry) -> float:
    """Return 4 pi area / perimeter squared: 1 for a circle, lower for jagged or snaking shapes."""
    return 4 * math.pi * geometry.area / geometry.length**2


def _usable(land: BaseGeometry, geometry: BaseGeometry) -> BaseGeometry:
    """Return the land a district could use: the land plus the district itself.

    A district always counts as usable land, so the ratios stay at or below 1 even
    when projection or rounding leaves its edge a hair outside the land outline.
    """
    return shapely.union(land, geometry)


def reock(geometry: BaseGeometry, land: BaseGeometry | None = None) -> float:
    """Return area / area of the smallest circle containing the shape: low for stretched shapes.

    With land, only the part of the circle on land counts.
    """
    radius = shapely.minimum_bounding_radius(geometry)
    if land is None:
        return geometry.area / (math.pi * radius**2)
    center = shapely.minimum_bounding_circle(geometry).centroid
    # The polygon circle sits just inside the true one, so add the district back in.
    circle = shapely.union(center.buffer(radius, quad_segs=CIRCLE_SEGMENTS), geometry)
    return geometry.area / circle.intersection(_usable(land, geometry)).area


def convex_hull_ratio(geometry: BaseGeometry, land: BaseGeometry | None = None) -> float:
    """Return area / area of the convex hull: low for shapes with bites or tentacles.

    With land, only the part of the hull on land counts.
    """
    hull = geometry.convex_hull
    if land is not None:
        hull = hull.intersection(_usable(land, geometry))
    return geometry.area / hull.area


def schwartzberg(geometry: BaseGeometry) -> float:
    """Return 1 / sqrt(Polsby-Popper): 1 for a circle, higher for less compact shapes."""
    return 1 / math.sqrt(polsby_popper(geometry))


# How close (in meters) a district's border must be to the state's outline to count as the
# state's edge. Generalizing the redrawn maps moves their edges up to 75 m (gerry.generalize).
EDGE_TOLERANCE_M = 100


def state_edge_share(
    geometry: BaseGeometry, outline: BaseGeometry, tolerance: float = EDGE_TOLERANCE_M
) -> float:
    """Return the share (0 to 1) of a district's border on its state's outline.

    The outline's edge is the coast, a national border or a state line: lines the district's
    mapmakers didn't draw. Both shapes are in meters. A border leaving the edge counts its
    first stretch inland, up to the tolerance, which is well under 1% for real districts.
    """
    edge = shapely.boundary(outline).buffer(tolerance)
    border = shapely.boundary(geometry)
    return border.intersection(edge).length / border.length


def local_projection(geometry: BaseGeometry, crs: CRS | str):
    """Return a function projecting shapes from crs into meters centered on geometry."""
    to_lonlat = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    lonlat = shapely.transform(geometry, to_lonlat.transform, interleaved=False)
    to_local = Transformer.from_crs(crs, local_crs(lonlat), always_xy=True)
    return lambda shape: shapely.transform(shape, to_local.transform, interleaved=False)


def project_around(geometry: BaseGeometry, crs: CRS | str) -> BaseGeometry:
    """Return a shape in meters, in an equal-area projection centered on the shape itself."""
    return local_projection(geometry, crs)(geometry)


def compactness(
    geometry: BaseGeometry, crs: CRS | str, land: BaseGeometry | None = None
) -> dict[str, float]:
    """Project a district (in crs) around itself and return its four scores and edge share.

    Args:
        geometry: The district.
        crs: The CRS of geometry and land.
        land: The state's land, for measuring Reock and convex hull against land, and the
            share of the district's border on the state's edge (None without land).
    """
    project = local_projection(geometry, crs)
    shape = project(geometry)
    local_land = project(land) if land is not None else None
    return {
        "polsby_popper": polsby_popper(shape),
        "reock": reock(shape, local_land),
        "convex_hull": convex_hull_ratio(shape, local_land),
        "schwartzberg": schwartzberg(shape),
        "state_edge_share": None if local_land is None else state_edge_share(shape, local_land),
    }
