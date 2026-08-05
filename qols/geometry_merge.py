"""qols/geometry_merge.py — Z-preserving polygon merge for Transitional
Surface runs (#121).

``TransitionalSurface_UTM.py`` optionally merges this run's Left/Right
pentagons into an already-existing "RWY_Transition Surface" layer instead
of creating a new one. The two source shapes (normal vs. inverted
direction) are typically two elongated wedges pointing opposite ways
along the runway, not one overlapping blob — their 2D union is very often
a genuine MultiPolygon (two disjoint/barely-touching lobes), so nothing
may be discarded: every part of the union must be kept. QGIS/GEOS boolean
geometry operations (``QgsGeometry.combine()``) are also 2D — they may
drop or zero out the Z dimension of a ``PolygonZ``/``MultiPolygonZ``
input. ``recover_ring_z`` is pure Python (no QGIS dependency) so it can be
unit tested directly: given a merged part's 2D boundary and the original
3D source rings (from every part of both inputs), it recovers a Z for
every output vertex by exact-matching an original vertex where the merged
boundary follows an untouched edge, else linearly interpolating along the
nearest original edge from either source ring.
``merge_polygonz_preserving_z`` is the thin QGIS-aware wrapper — it always
returns a MultiPolygonZ geometry (via ``convertToMultiType()``) so the
result's type stays consistent regardless of whether the union happened
to be single- or multi-part.
"""
from __future__ import annotations

from typing import Iterator

Point2 = tuple[float, float]
Point3 = tuple[float, float, float]
Edge3 = tuple[Point3, Point3]

__all__ = [
    "recover_ring_z",
    "merge_polygonz_preserving_z",
]


# ---------------------------------------------------------------------------
# Pure geometry helpers (no QGIS dependency — operate on plain tuples)
# ---------------------------------------------------------------------------

def _match_exact_vertex_z(pt: Point2, vertices_xyz: list[Point3], tol: float) -> float | None:
    """First original vertex within `tol` of `pt`, or None. Iteration order
    of `vertices_xyz` decides ties (existing-layer ring first, by convention
    of the caller)."""
    tol2 = tol * tol
    for x, y, z in vertices_xyz:
        dx = x - pt[0]
        dy = y - pt[1]
        if dx * dx + dy * dy <= tol2:
            return z
    return None


def _iter_edges(ring: list[Point3]) -> Iterator[Edge3]:
    """Closed-ring edges, skipping zero-length (degenerate) segments."""
    n = len(ring)
    for i in range(n):
        a = ring[i]
        b = ring[(i + 1) % n]
        if a[0] == b[0] and a[1] == b[1]:
            continue
        yield a, b


def _project_point_on_segment(pt: Point2, a: Point3, b: Point3) -> tuple[float, float]:
    """Clamped projection parameter t in [0, 1] and squared distance from
    `pt` to the projected point on segment a->b (2D, ignoring Z)."""
    dx = b[0] - a[0]
    dy = b[1] - a[1]
    len2 = dx * dx + dy * dy
    if len2 == 0:
        t = 0.0
    else:
        t = ((pt[0] - a[0]) * dx + (pt[1] - a[1]) * dy) / len2
        t = max(0.0, min(1.0, t))
    proj_x = a[0] + t * dx
    proj_y = a[1] + t * dy
    dist2 = (pt[0] - proj_x) ** 2 + (pt[1] - proj_y) ** 2
    return t, dist2


def _interpolate_nearest_edge_z(pt: Point2, edges: list[Edge3]) -> float:
    """Z at `pt`, linearly interpolated along whichever edge (from either
    source ring) is globally nearest to `pt`."""
    if not edges:
        raise ValueError("no edges to interpolate from")
    best_t = 0.0
    best_dist2 = None
    best_edge = edges[0]
    for a, b in edges:
        t, dist2 = _project_point_on_segment(pt, a, b)
        if best_dist2 is None or dist2 < best_dist2:
            best_dist2 = dist2
            best_t = t
            best_edge = (a, b)
    a, b = best_edge
    return a[2] + best_t * (b[2] - a[2])


def recover_ring_z(
    merged_xy: list[Point2],
    source_rings_xyz: list[list[Point3]],
    exact_match_tol: float = 1e-6,
) -> list[Point3]:
    """For each 2D vertex of a unioned polygon boundary, recover a Z by
    exact-matching an original 3D vertex from either source ring, else by
    linear interpolation along the nearest original edge from either ring.
    """
    if not merged_xy:
        return []
    all_vertices = [v for ring in source_rings_xyz for v in ring]
    all_edges = [e for ring in source_rings_xyz for e in _iter_edges(ring)]
    result = []
    for pt in merged_xy:
        z = _match_exact_vertex_z(pt, all_vertices, exact_match_tol)
        if z is None:
            z = _interpolate_nearest_edge_z(pt, all_edges)
        result.append((pt[0], pt[1], z))
    return result


# ---------------------------------------------------------------------------
# QGIS-aware wrapper
# ---------------------------------------------------------------------------

def _geometry_parts(geom) -> list:
    """Every polygon part of `geom` — `[geom]` if single-part, else each
    member of a multi-part geometry."""
    if not geom.isMultipart():
        return [geom]
    parts = geom.asGeometryCollection()
    return parts if parts else [geom]


def _all_exterior_rings_xyz(geom) -> list[list[Point3]]:
    """Exterior ring of every polygon part of `geom` (handles both a plain
    Polygon and an already multi-part MultiPolygon — e.g. the existing
    layer's feature may itself be the result of a previous merge)."""
    rings = []
    for part in _geometry_parts(geom):
        ring = part.constGet().exteriorRing()
        pts = [(ring.pointN(i).x(), ring.pointN(i).y(), ring.pointN(i).z()) for i in range(ring.numPoints())]
        if len(pts) > 1 and pts[0][:2] == pts[-1][:2]:
            pts = pts[:-1]
        rings.append(pts)
    return rings


def _polygon_exterior_xy(geom) -> list[Point2]:
    ring = geom.constGet().exteriorRing()
    pts = [(ring.pointN(i).x(), ring.pointN(i).y()) for i in range(ring.numPoints())]
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    return pts


def merge_polygonz_preserving_z(
    existing_geom,
    new_geom,
    exact_match_tol: float = 1e-6,
):
    """2D-union `existing_geom` and `new_geom` (PolygonZ or MultiPolygonZ,
    no holes), recover Z per output vertex via `recover_ring_z`, and
    return a new MultiPolygonZ QgsGeometry. The two source shapes are
    often two disjoint/barely-touching lobes (e.g. two Transitional runs
    pointing opposite ways along the runway) rather than one overlapping
    blob, so EVERY part of the union is kept — nothing is discarded, even
    when the result is genuinely multi-part. Falls back to `new_geom`
    unchanged if the union or Z-recovery cannot proceed — a failed merge
    must not lose the run the user just calculated."""
    from qgis.core import QgsGeometry, QgsLineString, QgsMultiPolygon, QgsPoint, QgsPolygon

    try:
        existing_rings = _all_exterior_rings_xyz(existing_geom)
        new_rings = _all_exterior_rings_xyz(new_geom)
        if not existing_rings or not new_rings:
            return new_geom

        unioned = existing_geom.combine(new_geom)
        if unioned is None or unioned.isEmpty():
            return new_geom

        source_rings = existing_rings + new_rings
        rebuilt_parts = []
        for part in _geometry_parts(unioned):
            part_xy = _polygon_exterior_xy(part)
            if len(part_xy) < 3:
                continue
            part_xyz = recover_ring_z(part_xy, source_rings, exact_match_tol)
            points = [QgsPoint(x, y, z) for x, y, z in part_xyz]
            rebuilt_parts.append(QgsPolygon(QgsLineString(points), rings=[]))

        if not rebuilt_parts:
            return new_geom

        if len(rebuilt_parts) == 1:
            result = QgsGeometry(rebuilt_parts[0])
        else:
            multi = QgsMultiPolygon()
            for poly in rebuilt_parts:
                multi.addGeometry(poly)
            result = QgsGeometry(multi)

        result.convertToMultiType()
        return result
    except Exception:
        return new_geom
