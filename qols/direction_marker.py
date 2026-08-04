"""qols/direction_marker.py — live direction-preview triangle for the
Approach/Transitional (and OFS/OES) dockwidget tabs (#117).

Mirrors qpansopy's OMNI SID DER marker: a small triangle, tip pointing the
way the surface will extend, sized in screen pixels so it stays visible at
any zoom. The triangle/azimuth math is pure Python (no QGIS dependency) so
it can be unit tested directly; ``build_marker_geometry`` is the thin
QGIS-aware wrapper the dockwidgets call.

The direction formula mirrors the ``s``-index convention ported from the
legacy ``TransitionalSurface_UTM.py`` into the New OLS scripts (see #113):
``s = direction; near_end_pt = line_pts[s]; far_end_pt = line_pts[-1 - s]``.
"""
from __future__ import annotations

import math

__all__ = [
    "resolve_direction_azimuth",
    "triangle_marker_vertices",
    "build_marker_geometry",
]


# ---------------------------------------------------------------------------
# Pure geometry helpers (no QGIS dependency — operate on plain (x, y) tuples)
# ---------------------------------------------------------------------------

def _azimuth_deg(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    """Bearing from p1 to p2, degrees clockwise from north (matches QgsPoint.azimuth)."""
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    return math.degrees(math.atan2(dx, dy)) % 360


def _project(pt: tuple[float, float], distance: float, azimuth_deg: float) -> tuple[float, float]:
    """Mirrors QgsPoint.project(distance, azimuth): 0° = north (+y), 90° = east (+x)."""
    rad = math.radians(azimuth_deg)
    return (pt[0] + distance * math.sin(rad), pt[1] + distance * math.cos(rad))


def resolve_direction_azimuth(
    line_pts: list[tuple[float, float]], direction: int,
) -> tuple[tuple[float, float], tuple[float, float], float]:
    """Given the runway centerline's endpoints and ``direction`` (0 = Start
    to End, -1 = End to Start), returns (near_end_pt, far_end_pt, azimuth_deg).

    Mirrors: s = direction; near_end_pt = line_pts[s]; far_end_pt = line_pts[-1-s];
    azimuth = far_end_pt.azimuth(near_end_pt).
    """
    s = direction
    near_end_pt = line_pts[s]
    far_end_pt = line_pts[-1 - s]
    azimuth_deg = _azimuth_deg(far_end_pt, near_end_pt)
    return near_end_pt, far_end_pt, azimuth_deg


def triangle_marker_vertices(
    tip: tuple[float, float], azimuth_deg: float, length: float, half_width: float,
) -> tuple[tuple[float, float], tuple[float, float], tuple[float, float]]:
    """Returns (tip, base_left, base_right) — a triangle pointing along
    azimuth_deg from tip, base trailing back. Mirrors qpansopy's DER marker:
    back_azimuth = azimuth + 180; base_center = tip.project(length, back_azimuth);
    base_left/right = base_center.project(half_width, azimuth -+ 90).
    """
    back_azimuth = (azimuth_deg + 180) % 360
    base_center = _project(tip, length, back_azimuth)
    base_left = _project(base_center, half_width, (azimuth_deg - 90) % 360)
    base_right = _project(base_center, half_width, (azimuth_deg + 90) % 360)
    return tip, base_left, base_right


# ---------------------------------------------------------------------------
# QGIS-aware wrapper
# ---------------------------------------------------------------------------

def _resolve_features(layer, use_selected_feature):
    if use_selected_feature:
        return list(layer.selectedFeatures())
    return list(layer.selectedFeatures()) or list(layer.getFeatures())


def _normalize_polyline_points(geometry) -> list[tuple[float, float]]:
    """Returns the runway centerline as a list of (x, y) tuples, picking the
    longest part for a MultiLineString. Returns [] on anything unusable —
    this feeds a live preview, so it must never raise."""
    if geometry is None or geometry.isEmpty():
        return []
    if geometry.isMultipart():
        parts = geometry.asMultiPolyline()
        if not parts:
            return []

        def part_len(pts):
            if not pts or len(pts) < 2:
                return 0.0
            total = 0.0
            for i in range(1, len(pts)):
                total += math.hypot(pts[i].x() - pts[i - 1].x(), pts[i].y() - pts[i - 1].y())
            return total

        longest = max(parts, key=part_len)
        return [(p.x(), p.y()) for p in longest]
    poly = geometry.asPolyline()
    if poly and len(poly) >= 2:
        return [(p.x(), p.y()) for p in poly]
    return []


def _closest_feature(features, pt: tuple[float, float]):
    return min(
        features,
        key=lambda f: math.hypot(f.geometry().asPoint().x() - pt[0], f.geometry().asPoint().y() - pt[1]),
    )


def build_marker_geometry(
    runway_layer,
    threshold_layer,
    direction: int,
    use_selected_feature: bool,
    length_px: float,
    half_width_px: float,
    map_units_per_pixel: float,
):
    """Returns a QgsGeometry triangle pointing the way an Approach/
    Transitional surface would extend for the current runway/threshold
    selection and direction, or None when inputs aren't ready yet (no
    layer/feature selected, degenerate centerline, zero-size canvas, etc.)
    — callers should treat None as "hide the marker", never as an error.
    """
    if runway_layer is None or threshold_layer is None or not map_units_per_pixel:
        return None

    from qgis.core import QgsGeometry, QgsLineString, QgsPoint, QgsPolygon

    runway_sel = _resolve_features(runway_layer, use_selected_feature)
    threshold_sel = _resolve_features(threshold_layer, use_selected_feature)
    if not runway_sel or not threshold_sel:
        return None

    line_pts = _normalize_polyline_points(runway_sel[0].geometry())
    if len(line_pts) < 2:
        return None

    try:
        near_end_pt, _far_end_pt, azimuth_deg = resolve_direction_azimuth(line_pts, direction)
    except IndexError:
        return None

    near_thr_feat = _closest_feature(threshold_sel, near_end_pt)
    thr_pt = near_thr_feat.geometry().asPoint()
    tip = (thr_pt.x(), thr_pt.y())

    length_m = length_px * map_units_per_pixel
    half_width_m = half_width_px * map_units_per_pixel
    tip_xy, base_left, base_right = triangle_marker_vertices(tip, azimuth_deg, length_m, half_width_m)

    ring = [QgsPoint(*tip_xy), QgsPoint(*base_left), QgsPoint(*base_right)]
    return QgsGeometry(QgsPolygon(QgsLineString(ring)))
