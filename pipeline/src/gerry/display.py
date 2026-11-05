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
    matrix, box_size = _fit_matrix(geometries, size)
    return [affinity.affine_transform(g, matrix) for g in geometries], box_size


def _fit_matrix(geometries: list[BaseGeometry], size: int) -> tuple[list[float], tuple[int, int]]:
    """Return fit_to_view's affine matrix and box size, so points can follow the same scaling."""
    minx, miny, maxx, maxy = shapely.union_all(geometries).bounds
    scale = size / max(maxx - minx, maxy - miny)
    matrix = [scale, 0, 0, -scale, -minx * scale, maxy * scale]
    return matrix, (round((maxx - minx) * scale), round((maxy - miny) * scale))


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
    _, to_view, shape, (width, height) = _district_frame(geometry, crs, detail)
    fitted = affinity.affine_transform(shape, to_view)
    return {"viewBox": f"0 0 {width} {height}", "d": svg_path(fitted)}


def _district_frame(geometry: BaseGeometry, crs, detail: float):
    """Project and simplify one district as district_outline draws it.

    Returns:
        The projection, the view matrix, the projected shape and the view box size.
    """
    project = local_projection(geometry, crs)
    shape = project(geometry)
    tolerance = _tolerance(shape, detail)
    shape = shapely.simplify(_visible_parts(shape, tolerance), tolerance, preserve_topology=True)
    matrix, box_size = _fit_matrix([shape], VIEW_SIZE)
    return project, matrix, shape, box_size


def district_points(geometry: BaseGeometry, crs, detail: float, points: list[BaseGeometry]) -> dict:
    """Return points placed on district_outline's drawing of the same district and detail.

    Returns:
        {"viewBox": "0 0 w h", "points": [[x, y], ...]} in view coordinates (whole numbers,
        y down), in the order given.
    """
    project, to_view, _, box_size = _district_frame(geometry, crs, detail)
    return _points_in_view(points, project, to_view, box_size)


def state_map(districts, detail: float) -> dict:
    """Return one state's districts drawn together, with shared borders kept identical.

    Args:
        districts: One state's districts with `district_id` and `geometry`.
        detail: Simplification as a share of the state's longer side.

    Returns:
        {"viewBox": "0 0 w h", "paths": {district_id: path}}.
    """
    _, to_view, shapes, (width, height) = _state_frame(districts, detail)
    fitted = [affinity.affine_transform(g, to_view) for g in shapes]
    paths = {d: svg_path(g) for d, g in zip(districts["district_id"], fitted, strict=True)}
    return {"viewBox": f"0 0 {width} {height}", "paths": paths}


def _state_frame(districts, detail: float):
    """Project and simplify a state's districts.

    Returns:
        The projection, the view matrix, the projected shapes and the view box size.

    The shapes are projected but not yet scaled into the view, so state_points can put
    points through the same projection and matrix.
    """
    project, shapes = _state_projected(districts)
    state = shapely.union_all(shapes)
    shapes = list(shapely.coverage_simplify(shapes, _tolerance(state, detail)))
    matrix, box_size = _fit_matrix(shapes, VIEW_SIZE)
    return project, matrix, shapes, box_size


def _state_projected(districts):
    """Return a state's projection and its districts projected at full detail."""
    project = local_projection(districts.union_all(), districts.crs)
    return project, [project(g) for g in districts.geometry]


def state_points(districts, detail: float, points: list[BaseGeometry]) -> dict:
    """Return points placed on state_map's drawing of the same districts and detail.

    Args:
        districts: As for state_map.
        detail: As for state_map; the same value gives the same view.
        points: Points in the districts' coordinate reference system.

    Returns:
        {"viewBox": "0 0 w h", "points": [[x, y], ...]} in view coordinates (whole numbers,
        y down), in the order given. A point outside the drawing's box falls outside 0..w, 0..h.
    """
    project, to_view, _, box_size = _state_frame(districts, detail)
    return _points_in_view(points, project, to_view, box_size)


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


def _points_in_view(points, project, to_view, box_size: tuple[int, int]) -> dict:
    """Project points and scale them into a drawing's view, rounded to whole units."""
    placed = [affinity.affine_transform(project(p), to_view) for p in points]
    width, height = box_size
    return {
        "viewBox": f"0 0 {width} {height}",
        "points": [[round(p.x), round(p.y)] for p in placed],
    }


# Close-ups: squares of a state map shown enlarged beside it, where districts are drawn too small
# to see or click. Sizes are in view units (VIEW_SIZE on the map's longer side).
# A district is too small when its widest inner circle has a radius under 8 pixels on a map
# drawn 512 pixels on its longer side, as a state page draws a tall state on a desktop screen.
CLOSEUP_SMALL_RADIUS = 8 * VIEW_SIZE / 512
# Small districts closer than this share a close-up.
CLOSEUP_GAP = 60
# Space around a cluster, as a share of its size, so its edges aren't on the frame.
CLOSEUP_PADDING = 0.15
# The smallest square, so a close-up enlarges at most 8 times...
CLOSEUP_MIN_SIDE = VIEW_SIZE / 8
# ...and the largest, since enlarging under 2 times isn't worth a second map.
CLOSEUP_MAX_SIDE = VIEW_SIZE / 2


def _inner_radius(shape: BaseGeometry) -> float:
    """Return the radius of the widest circle that fits inside a shape's largest piece."""
    largest = max(shapely.get_parts(shape), key=lambda p: p.area)
    return polylabel(largest, tolerance=0.5).distance(largest.boundary)


def _square_around(cluster: BaseGeometry, size: tuple[int, int]) -> tuple[float, ...]:
    """Return a padded square centered on a cluster, moved (or cut) to stay inside the map."""
    minx, miny, maxx, maxy = cluster.bounds
    side = max(max(maxx - minx, maxy - miny) * (1 + 2 * CLOSEUP_PADDING), CLOSEUP_MIN_SIDE)
    square = []
    for low, high, extent in ((minx, maxx, size[0]), (miny, maxy, size[1])):
        start = min(max((low + high - side) / 2, 0), max(extent - side, 0))
        square.append((start, min(start + side, extent)))
    (x0, x1), (y0, y1) = square
    return x0, y0, x1, y1


def closeup_boxes(shapes: list[BaseGeometry], size: tuple[int, int]) -> list[tuple[float, ...]]:
    """Return the squares of a state map to show enlarged, so its smallest districts can be seen.

    Args:
        shapes: The districts as drawn, in view units (as state_map draws them).
        size: The map's (width, height) in view units.

    Returns:
        (x0, y0, x1, y1) boxes in view units, inside the map, largest first. Each is square
        unless the map's edge cuts it, and none overlap.
    """
    small = [s for s in shapes if not s.is_empty and _inner_radius(s) < CLOSEUP_SMALL_RADIUS]
    if not small:
        return []
    near = shapely.union_all([s.buffer(CLOSEUP_GAP / 2) for s in small])
    clusters = [
        shapely.union_all([s for s in small if s.intersects(b)]) for b in shapely.get_parts(near)
    ]
    # Merge clusters until no two squares overlap. Squares only grow as clusters merge, so
    # this always ends.
    merged = True
    while merged:
        merged = False
        for i in range(len(clusters)):
            for j in range(i + 1, len(clusters)):
                a, b = (shapely.box(*_square_around(clusters[k], size)) for k in (i, j))
                if a.intersection(b).area > 0:
                    clusters[i] = clusters[i].union(clusters.pop(j))
                    merged = True
                    break
            if merged:
                break
    boxes = [_square_around(c, size) for c in clusters]
    boxes = [b for b in boxes if max(b[2] - b[0], b[3] - b[1]) <= CLOSEUP_MAX_SIDE]
    return sorted(boxes, key=lambda b: (-(b[2] - b[0]) * (b[3] - b[1]), b[0], b[1]))


def _polygons(geometry: BaseGeometry) -> BaseGeometry:
    """Return only the polygon pieces of a geometry (a cut can leave stray lines and points)."""
    parts = [p for p in shapely.get_parts(geometry) if p.geom_type == "Polygon"]
    return shapely.union_all(parts) if parts else shapely.Polygon()


def state_closeups(districts, detail: float) -> list[dict]:
    """Return a state map's close-ups: its squares with small districts, redrawn enlarged.

    Each close-up is drawn from the full-detail districts cut to its square, simplified at
    detail times the square's side, so it's as sharp as the state map is.

    Args:
        districts: As for state_map.
        detail: As for state_map.

    Returns:
        [{"box": [x0, y0, x1, y1], "viewBox": "0 0 w h", "paths": {district_id: path}}], where box
        is the square in state_map's view units (to two decimal places) and the close-up's view
        maps it to VIEW_SIZE on its longer side. Only districts inside the square are drawn.
    """
    _, to_view, simplified, size = _state_frame(districts, detail)
    drawn = [affinity.affine_transform(g, to_view) for g in simplified]
    _, full = _state_projected(districts)
    scale, _, _, _, offset_x, offset_y = to_view
    closeups = []
    for x0, y0, x1, y1 in closeup_boxes(drawn, size):
        # Back from view units to projected meters (the view flips y).
        area = shapely.box((x0 - offset_x) / scale, (offset_y - y1) / scale,
                           (x1 - offset_x) / scale, (offset_y - y0) / scale)  # fmt: skip
        ids, cut = [], []
        for district, shape in zip(districts["district_id"], full, strict=True):
            piece = _polygons(shape.intersection(area))
            if not piece.is_empty:
                ids.append(district)
                cut.append(piece)
        cut = list(shapely.coverage_simplify(cut, _tolerance(area, detail)))
        matrix, (width, height) = _fit_matrix([area], VIEW_SIZE)
        fitted = [affinity.affine_transform(g, matrix) for g in cut]
        closeups.append({
            "box": [round(v, 2) for v in (x0, y0, x1, y1)],
            "viewBox": f"0 0 {width} {height}",
            "paths": {d: svg_path(g) for d, g in zip(ids, fitted, strict=True)},
        })  # fmt: skip
    return closeups
