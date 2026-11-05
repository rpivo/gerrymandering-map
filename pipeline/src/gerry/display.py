"""Precompute district outlines as SVG paths for the site.

The site draws every map as inline SVG at build time, with no map library in the
browser. Each outline is projected the same way it is measured (an equal-area
projection centered on the district, or on the state for state maps), simplified to
the detail the page needs, scaled into a VIEW_SIZE box, and written as a path with
whole-number coordinates. Holes and separate pieces are extra subpaths, so the site
draws paths with `fill-rule="evenodd"`.
"""

import geopandas as gpd
import shapely
from shapely import affinity
from shapely.geometry.base import BaseGeometry
from shapely.ops import polylabel

from gerry.metrics import local_projection

VIEW_SIZE = 1000

# Areas some states' drawings are cut to (west, south, east, north in degrees), with the note
# shown beside them. HI-02 reaches 1,900 km west to Kure Atoll through the small, nearly
# uninhabited Northwestern Hawaiian Islands, which would shrink the main islands to a corner.
DISPLAY_CROPS = {
    "HI": (
        shapely.box(-161.0, 18.5, -154.5, 22.5),
        "The Northwestern Hawaiian Islands, part of District 2, are not shown.",
    ),
}


def display_crop(state: str, geometry: BaseGeometry) -> tuple[BaseGeometry, str | None]:
    """Return a shape cut to what its drawings show, with a note if anything was left out.

    Display only: scores are always measured on the full shape. The geometry is in
    NAD83 degrees (EPSG:4269).
    """
    if state not in DISPLAY_CROPS:
        return geometry, None
    area, note = DISPLAY_CROPS[state]
    if geometry.difference(area).is_empty or not geometry.intersects(area):
        return geometry, None
    return geometry.intersection(area), note


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


# The US map: the lower 48 in the Census Bureau's Albers projection for the contiguous US,
# with Alaska and Hawaii as insets at the bottom left in their own Albers projections, as most
# US maps draw them. Alaska is shrunk so it doesn't dwarf the rest.
_LOWER_48_CRS = "EPSG:5070"
_INSETS = {"AK": ("EPSG:3338", 0.35), "HI": ("ESRI:102007", 1.0)}
# Gap between insets, and how far an inset moves down at a time until it clears the mainland,
# as shares of the lower 48's width.
_INSET_GAP = 0.02


def _to_crs(geometry: BaseGeometry, crs: str) -> BaseGeometry:
    return gpd.GeoSeries([geometry], crs="EPSG:4269").to_crs(crs).iloc[0]


def _place_inset(shape: BaseGeometry, left: float, bottom: float, mainland: BaseGeometry,
                 step: float) -> BaseGeometry:  # fmt: skip
    """Move a shape so its box starts at (left, bottom), then down until it clears the mainland."""
    minx, miny, _, _ = shape.bounds
    placed = affinity.translate(shape, left - minx, bottom - miny)
    while placed.intersects(mainland):
        placed = affinity.translate(placed, 0, -step)
    return placed


def _label_point(shape: BaseGeometry) -> list[int]:
    """Return a point well inside a shape's largest piece, for its label."""
    largest = max(shapely.get_parts(shape), key=lambda p: p.area)
    point = polylabel(largest, tolerance=1.0)
    return [round(point.x), round(point.y)]


def us_map(states: dict[str, BaseGeometry], detail: float) -> dict:
    """Return the 50 states drawn together as a map of the US, with a label point for each.

    Args:
        states: {USPS code: outline} in NAD83 degrees (EPSG:4269), such as the Census state
            file. Hawaii is cut like its state map (display_crop).
        detail: Simplification as a share of the lower 48's width.

    Returns:
        {"viewBox": "0 0 w h", "paths": {usps: path}, "labels": {usps: [x, y]}}.
    """
    shapes = {s: _to_crs(g, _LOWER_48_CRS) for s, g in states.items() if s not in _INSETS}
    mainland = shapely.union_all(list(shapes.values()))
    minx, miny, maxx, _ = mainland.bounds
    step = _INSET_GAP * (maxx - minx)
    left = minx
    for state, (crs, scale) in _INSETS.items():
        if state not in states:
            continue
        shape = _to_crs(display_crop(state, states[state])[0], crs)
        shape = affinity.scale(shape, scale, scale, origin=(0, 0))
        shapes[state] = _place_inset(shape, left, miny, mainland, step)
        left = shapes[state].bounds[2] + step
    tolerance = detail * (maxx - minx)
    names = list(shapes)
    simplified = [_visible_parts(shapes[s], tolerance) for s in names]
    simplified = list(shapely.coverage_simplify(simplified, tolerance))
    fitted, (width, height) = fit_to_view(simplified)
    return {
        "viewBox": f"0 0 {width} {height}",
        "paths": {s: svg_path(g) for s, g in zip(names, fitted, strict=True)},
        "labels": {s: _label_point(g) for s, g in zip(names, fitted, strict=True)},
    }
