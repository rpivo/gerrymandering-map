"""Compactness metrics for one district shape.

All four take a shape in metres (or any equal-area units). `compactness` handles the
projection: each district is measured in a Lambert azimuthal equal-area projection
centred on itself, which keeps distortion small anywhere, Alaska and Hawaii included.

A district made of several pieces uses its total area and total perimeter, and one
hull and one circle around all the pieces.
"""

import math

import shapely
from pyproj import CRS, Transformer
from shapely.geometry.base import BaseGeometry

from gerry.generalize import local_crs


def polsby_popper(geometry: BaseGeometry) -> float:
    """Return 4 pi area / perimeter squared: 1 for a circle, lower for jagged or snaking shapes."""
    return 4 * math.pi * geometry.area / geometry.length**2


def reock(geometry: BaseGeometry) -> float:
    """Return area / area of the smallest circle containing the shape: low for stretched shapes."""
    radius = shapely.minimum_bounding_radius(geometry)
    return geometry.area / (math.pi * radius**2)


def convex_hull_ratio(geometry: BaseGeometry) -> float:
    """Return area / area of the convex hull: low for shapes with bites or tentacles."""
    return geometry.area / geometry.convex_hull.area


def schwartzberg(geometry: BaseGeometry) -> float:
    """Return 1 / sqrt(Polsby-Popper): 1 for a circle, higher for less compact shapes."""
    return 1 / math.sqrt(polsby_popper(geometry))


def project_around(geometry: BaseGeometry, crs: CRS | str) -> BaseGeometry:
    """Return a shape in metres, in an equal-area projection centred on the shape itself."""
    to_lonlat = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    lonlat = shapely.transform(geometry, to_lonlat.transform, interleaved=False)
    to_local = Transformer.from_crs(crs, local_crs(lonlat), always_xy=True)
    return shapely.transform(geometry, to_local.transform, interleaved=False)


def compactness(geometry: BaseGeometry, crs: CRS | str) -> dict[str, float]:
    """Project a district (in crs) around itself and return all four scores, each unitless."""
    shape = project_around(geometry, crs)
    return {
        "polsby_popper": polsby_popper(shape),
        "reock": reock(shape),
        "convex_hull": convex_hull_ratio(shape),
        "schwartzberg": schwartzberg(shape),
    }
