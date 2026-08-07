"""qols/geometry_difference.py — flat-Z-preserving polygon difference for
the Conical vs. Inner Horizontal surfaces (#124).

`conical.py` and `inner-horizontal-racetrack.py` are independently
implemented but geometrically concentric: both build a racetrack polygon
(two circular arcs at the runway's start/end thresholds, joined by
tangents) from the *same* runway centerline/threshold points and azimuth,
differing only in radius `L` — Conical's radius is always >= Inner
Horizontal's (`Height/Slope + InnerHorizontalRadius`, see
`dockwidget.py::recalculate_conical_radius`), so Conical's solid disk
always fully covers Inner Horizontal's, and the two rendered layers
visually overlap. Per ICAO Annex 14, Conical's footprint should be the
ring beyond Inner Horizontal's edge.

Unlike `qols/geometry_merge.py`'s union work (#121), no Z-interpolation
is needed here: each script's polygon is already flat — every vertex
shares one uniform `height` value — so the differenced ring just needs
that same flat Z re-applied to whatever vertices GEOS's 2D
`QgsGeometry.difference()` produces (which doesn't reliably carry Z
through a boolean op). `difference_flat()` is the thin QGIS-aware
wrapper; the ring-flattening step is pure enough to unit test directly
via `flatten_ring_z`.
"""
from __future__ import annotations

Point2 = tuple[float, float]
Point3 = tuple[float, float, float]

__all__ = [
    "flatten_ring_z",
    "difference_flat",
]


# ---------------------------------------------------------------------------
# Pure geometry helper (no QGIS dependency — operates on plain tuples)
# ---------------------------------------------------------------------------

def flatten_ring_z(ring_xy: list[Point2], z: float) -> list[Point3]:
    """Return `ring_xy` with `z` applied to every vertex — no
    interpolation, since both source polygons are already flat."""
    return [(x, y, z) for x, y in ring_xy]


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


def _ring_xy(ring) -> list[Point2]:
    return [(ring.pointN(i).x(), ring.pointN(i).y()) for i in range(ring.numPoints())]


def _base_flat_z(geom) -> float | None:
    """The single Z value shared by every vertex of `geom`'s first part —
    read from its exterior ring's first point (both source scripts here
    only ever build flat, single-Z polygons)."""
    parts = _geometry_parts(geom)
    if not parts:
        return None
    ring = parts[0].constGet().exteriorRing()
    if ring.numPoints() == 0:
        return None
    return ring.pointN(0).z()


def difference_flat(base_geom, subtract_geom):
    """2D-difference `base_geom` minus `subtract_geom`, re-applying
    `base_geom`'s own flat Z to every vertex of every ring (exterior
    *and* interior/hole rings — a polygon-with-a-hole is a single
    `QgsPolygon` with multiple rings, not a `MultiPolygon`, which is the
    expected result here since Inner Horizontal is fully contained
    within Conical) of every part of the result (multipart handled
    defensively for unusual/self-intersecting input). Falls back to
    `base_geom` unchanged if the difference is empty or anything fails —
    a failed trim must not delete the surface the user just calculated.
    """
    from qgis.core import QgsGeometry, QgsLineString, QgsMultiPolygon, QgsPoint, QgsPolygon

    try:
        base_area = base_geom.area()
        print(f"difference_flat: base area={base_area}, base isMultipart={base_geom.isMultipart()}, "
              f"base wkbType={base_geom.wkbType()}")

        z = _base_flat_z(base_geom)
        print(f"difference_flat: detected flat z={z}")
        if z is None:
            print("difference_flat: z is None, returning base_geom unchanged")
            return base_geom

        diff = base_geom.difference(subtract_geom)
        if diff is None:
            print("difference_flat: base_geom.difference() returned None, returning base_geom unchanged")
            return base_geom
        print(f"difference_flat: diff area={diff.area()}, diff isEmpty={diff.isEmpty()}, "
              f"diff isMultipart={diff.isMultipart()}, diff wkbType={diff.wkbType()}")
        if diff.isEmpty():
            print("difference_flat: diff is empty, returning base_geom unchanged")
            return base_geom
        if abs(diff.area() - base_area) < 1e-6:
            print("difference_flat: WARNING - diff area equals base area, subtraction had no visible effect")

        rebuilt_parts = []
        for part in _geometry_parts(diff):
            abstract = part.constGet()
            ext_pts = [QgsPoint(x, y, pz) for x, y, pz in flatten_ring_z(_ring_xy(abstract.exteriorRing()), z)]
            if len(ext_pts) < 3:
                continue
            interior_rings = []
            for i in range(abstract.numInteriorRings()):
                hole_xy = _ring_xy(abstract.interiorRing(i))
                if len(hole_xy) < 3:
                    continue
                hole_pts = [QgsPoint(x, y, pz) for x, y, pz in flatten_ring_z(hole_xy, z)]
                interior_rings.append(QgsLineString(hole_pts))
            print(f"difference_flat: part with {len(ext_pts)} exterior pts, {len(interior_rings)} interior ring(s)")
            rebuilt_parts.append(QgsPolygon(QgsLineString(ext_pts), rings=interior_rings))

        if not rebuilt_parts:
            print("difference_flat: no rebuilt parts, returning base_geom unchanged")
            return base_geom

        if len(rebuilt_parts) == 1:
            result = QgsGeometry(rebuilt_parts[0])
        else:
            multi = QgsMultiPolygon()
            for poly in rebuilt_parts:
                multi.addGeometry(poly)
            result = QgsGeometry(multi)
        print(f"difference_flat: returning trimmed geometry, area={result.area()}")
        return result
    except Exception as e:
        import traceback
        print(f"difference_flat: FAILED with {e!r}")
        traceback.print_exc()
        return base_geom
