"""Precompute district outlines as SVG paths for the site.

The site draws every map as inline SVG at build time, with no map library in the
browser. Each outline is projected the same way it is measured (an equal-area
projection centered on the district, or on the state for state maps), simplified to
the detail the page needs, scaled into a VIEW_SIZE box, and written as a path with
whole-number coordinates. Holes and separate pieces are extra subpaths, so the site
draws paths with `fill-rule="evenodd"`.
"""

import shapely
from shapely import affinity
from shapely.geometry.base import BaseGeometry

from gerry.metrics import local_projection

VIEW_SIZE = 1000


def _ring_path(coords) -> str:
    """Return one closed subpath for a ring, dropping points that round to the same spot."""
    rounded = []
    for x, y in coords[:-1]:
        point = (round(x), round(y))
        if not rounded or point != rounded[-1]:
            rounded.append(point)
    if len(rounded) > 1 and rounded[0] == rounded[-1]:
        rounded.pop()
    if len(rounded) < 3:
        return ""
    return "M" + "L".join(f"{x} {y}" for x, y in rounded) + "Z"


def svg_path(geometry: BaseGeometry) -> str:
    """Return an SVG path for a shape already in view coordinates (whole numbers)."""
    rings = []
    for polygon in shapely.get_parts(geometry):
        rings.append(polygon.exterior.coords)
        rings.extend(interior.coords for interior in polygon.interiors)
    return "".join(_ring_path(list(ring)) for ring in rings)


def fit_to_view(
    geometries: list[BaseGeometry], size: int = VIEW_SIZE
) -> tuple[list[BaseGeometry], tuple[int, int]]:
    """Scale shapes together into a box whose longer side is size, with y pointing down.

    Returns:
        The transformed shapes and the (width, height) of the box.
    """
    minx, miny, maxx, maxy = shapely.union_all(geometries).bounds
    scale = size / max(maxx - minx, maxy - miny)
    matrix = [scale, 0, 0, -scale, -minx * scale, maxy * scale]
    fitted = [affinity.affine_transform(g, matrix) for g in geometries]
    return fitted, (round((maxx - minx) * scale), round((maxy - miny) * scale))


def _tolerance(geometry: BaseGeometry, detail: float) -> float:
    """Return a simplification distance: detail times the shape's longer side."""
    minx, miny, maxx, maxy = geometry.bounds
    return detail * max(maxx - minx, maxy - miny)


def _visible_parts(geometry: BaseGeometry, tolerance: float) -> BaseGeometry:
    """Drop pieces smaller than (2 x tolerance) squared: too small to see at this detail.

    The largest piece always stays.
    """
    parts = sorted(shapely.get_parts(geometry), key=lambda p: -p.area)
    kept = [parts[0], *(p for p in parts[1:] if p.area >= (2 * tolerance) ** 2)]
    return shapely.union_all(kept)


def district_outline(geometry: BaseGeometry, crs, detail: float) -> dict[str, str]:
    """Return one district's outline as {"viewBox": "0 0 w h", "d": path}.

    Args:
        geometry: The district, in crs.
        crs: Its coordinate reference system.
        detail: Simplification as a share of the district's longer side (smaller is finer).
    """
    shape = local_projection(geometry, crs)(geometry)
    tolerance = _tolerance(shape, detail)
    shape = shapely.simplify(_visible_parts(shape, tolerance), tolerance, preserve_topology=True)
    (fitted,), (width, height) = fit_to_view([shape])
    return {"viewBox": f"0 0 {width} {height}", "d": svg_path(fitted)}


def state_map(districts, detail: float) -> dict:
    """Return one state's districts drawn together, with shared borders kept identical.

    Args:
        districts: One state's districts with `district_id` and `geometry`.
        detail: Simplification as a share of the state's longer side.

    Returns:
        {"viewBox": "0 0 w h", "paths": {district_id: path}}.
    """
    project = local_projection(districts.union_all(), districts.crs)
    shapes = [project(g) for g in districts.geometry]
    state = shapely.union_all(shapes)
    shapes = list(shapely.coverage_simplify(shapes, _tolerance(state, detail)))
    fitted, (width, height) = fit_to_view(shapes)
    paths = {d: svg_path(g) for d, g in zip(districts["district_id"], fitted, strict=True)}
    return {"viewBox": f"0 0 {width} {height}", "paths": paths}
