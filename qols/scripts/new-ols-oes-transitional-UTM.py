"""
New OLS Concept — OES Transitional Surface
One connected pentagon per side (approach wing + runway strip merged),
flanking the OFS Approach surface, per ICAO Figure 4-1. Layer/figure
construction mirrors the legacy TransitionalSurface_UTM.py script: a single
closed ring per side built from a list of shared points, one feature per
side, no separate wing/strip pieces.

Geometry (plan view, one side):
  near_inner — runway-strip edge at the selected threshold, Z = start_elevation
  near_outer — near_inner + lateral_near outward, Z = cap_elevation
  far_outer  — runway-strip edge at the opposite threshold, offset by
               lateral_far outward, Z = cap_elevation
  far_inner  — runway-strip edge at the opposite threshold, Z = opp_start_elevation
  far_vertex — approach inner edge at d_cap from near_inner, Z = cap_elevation
where:
  d_cap        = cap_height / approach_slope     (≈ 1 802 m for 3.33 %, 60 m cap)
  lateral_near = (cap_elevation - start_elevation)     / trans_slope
  lateral_far  = (cap_elevation - opp_start_elevation) / trans_slope

lateral_near and lateral_far are computed independently from each
threshold's own elevation, matching how the legacy Transitional surface
derives width from Z0 (near) vs ZE (far) rather than a single shared value.

Procedure to be used in Projected Coordinate System Only.
"""
myglobals = set(globals().keys())

from qgis.core import *
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from math import sqrt, hypot

_script_success = False


def _normalize_polyline_points(geometry):
    if geometry is None or geometry.isEmpty():
        raise Exception("Empty geometry provided for runway centerline.")
    if geometry.isMultipart():
        parts = geometry.asMultiPolyline()
        if not parts:
            raise Exception("Empty MultiLineString geometry.")

        def part_len(pts):
            if not pts or len(pts) < 2:
                return 0.0
            total = 0.0
            for i in range(1, len(pts)):
                dx = pts[i].x() - pts[i - 1].x()
                dy = pts[i].y() - pts[i - 1].y()
                total += sqrt(dx * dx + dy * dy)
            return total

        return [QgsPoint(p) for p in max(parts, key=part_len)]
    poly = geometry.asPolyline()
    if poly and len(poly) >= 2:
        return [QgsPoint(p) for p in poly]
    raise Exception("Line geometry cannot be converted to a polyline.")


# ---------------------------------------------------------------------------
# Parameter extraction
# ---------------------------------------------------------------------------
try:
    width_m = globals().get('width_m', 175.0)
    start_elevation_m = globals().get('start_elevation_m', 0.0)
    highest_thr_elev_m = globals().get('highest_thr_elev_m', 0.0)
    slope_pct = globals().get('slope_pct', 20.0)
    cap_height_m = globals().get('cap_height_m', 60.0)
    approach_slope_pct = globals().get('approach_slope_pct', 3.33)
    divergence_ratio = globals().get('divergence_ratio', 0.10)
    distance_from_threshold_m = globals().get('distance_from_threshold_m', 60.0)
    direction = globals().get('direction', 0)
    end_elevation_m = globals().get('end_elevation_m', 0.0)
    opp_start_elevation_m = globals().get('opp_start_elevation_m', 0.0)
    runway_layer = globals().get('runway_layer', None)
    threshold_layer = globals().get('threshold_layer', None)
    use_selected_feature = globals().get('use_selected_feature', True)

    slope_ratio = slope_pct / 100.0
    approach_slope = approach_slope_pct / 100.0
    cap_elevation = highest_thr_elev_m + cap_height_m
    half_inner = width_m / 2.0

    height_to_cap = cap_elevation - start_elevation_m
    if height_to_cap <= 0 or approach_slope <= 0 or slope_ratio <= 0:
        raise Exception(
            f"OES Transitional: degenerate parameters — "
            f"height_to_cap={height_to_cap:.1f}, approach_slope={approach_slope:.4f}"
        )

    d_cap = height_to_cap / approach_slope
    lateral_near = height_to_cap / slope_ratio
    far_half_width = half_inner + d_cap * divergence_ratio

    # lateral_far (width at the opposite threshold) is resolved further
    # down, once the opposite threshold feature has been matched via
    # direction + the runway centerline — placeholder until then.
    lateral_far = lateral_near

    print(
        f"QOLS New OLS OES: slope={slope_pct}%, cap_elev={cap_elevation:.1f}m, "
        f"d_cap={d_cap:.1f}m, lateral_near={lateral_near:.1f}m, "
        f"far_half_width={far_half_width:.1f}m"
    )
except Exception as e:
    print(f"QOLS New OLS OES: Error getting parameters: {e}")
    raise

map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()

# ---------------------------------------------------------------------------
# Runway layer
# ---------------------------------------------------------------------------
try:
    if runway_layer is None:
        raise Exception("No Runway Layer Centerline provided.")
    if use_selected_feature:
        selection = runway_layer.selectedFeatures()
        if not selection:
            raise Exception("No runway features selected.")
    else:
        selection = runway_layer.selectedFeatures() or list(runway_layer.getFeatures())
        if not selection:
            raise Exception("No features found in Runway Layer.")
except Exception as e:
    iface.messageBar().pushMessage("QOLS Error", str(e), level=MSG_CRITICAL)
    raise

for feat in selection:
    line_pts = _normalize_polyline_points(feat.geometry())
    break

# ---------------------------------------------------------------------------
# Threshold layer
# ---------------------------------------------------------------------------
try:
    if threshold_layer is None:
        raise Exception("No threshold layer provided.")
    if use_selected_feature:
        threshold_sel = threshold_layer.selectedFeatures()
        if not threshold_sel:
            raise Exception("No threshold features selected.")
    else:
        threshold_sel = threshold_layer.selectedFeatures() or list(threshold_layer.getFeatures())
        if not threshold_sel:
            raise Exception("No features found in threshold layer.")
except Exception as e:
    iface.messageBar().pushMessage("QOLS Error", str(e), level=MSG_CRITICAL)
    raise


def _closest_feature(features, pt):
    return min(
        features,
        key=lambda f: hypot(f.geometry().asPoint().x() - pt.x(), f.geometry().asPoint().y() - pt.y()),
    )


# direction picks the runway-centerline endpoint directly (0 = Start to
# End, -1 = End to Start), mirroring the legacy TransitionalSurface_UTM.py
# line_pts[-1-s]/line_pts[s] convention — no threshold-distance matching or
# post-hoc azimuth flip needed.
s = direction
near_end_pt = line_pts[s]
far_end_pt = line_pts[-1 - s]
azimuth = far_end_pt.azimuth(near_end_pt)

# Anchored to the selected threshold (threshold_sel), same as legacy
# TransitionalSurface_UTM.py — direction changes azimuth (which way the
# surface points), not which threshold is used. In "Selected Only" mode
# with a single feature selected, re-selecting the matching threshold when
# toggling direction is the user's responsibility (same as legacy); in
# "All" mode threshold_sel already covers every feature, so the nearest
# match still follows direction automatically.
near_thr_feat = _closest_feature(threshold_sel, near_end_pt)
thr_geom = near_thr_feat.geometry().asPoint()
thr_point = QgsPoint(thr_geom)
thr_point.addZValue(start_elevation_m)

# Opposite/far anchor — taken directly from the runway centerline's far
# endpoint (far_end_pt), exactly like legacy's pt_02T = start_point.project(...).
# It is NOT matched against the threshold layer: the runway strip always
# runs to the far end of *this* runway centerline, regardless of whether a
# threshold point feature happens to sit there, and it stays consistent
# with azimuth (both derive from the same direction-selected endpoints).
has_opposite_threshold = (far_end_pt.x(), far_end_pt.y()) != (near_end_pt.x(), near_end_pt.y())
opp_thr_x = opp_thr_y = None
if has_opposite_threshold:
    height_to_cap_far = cap_elevation - opp_start_elevation_m
    if height_to_cap_far <= 0:
        raise Exception(
            f"OES Transitional: degenerate parameters — "
            f"height_to_cap_far={height_to_cap_far:.1f}"
        )
    lateral_far = height_to_cap_far / slope_ratio
    opp_thr_x, opp_thr_y = far_end_pt.x(), far_end_pt.y()

print(f"QOLS New OLS OES: azimuth={azimuth:.2f}°, direction={direction}, lateral_far={lateral_far:.1f}m")

# ---------------------------------------------------------------------------
# Transitional surface geometry — one connected pentagon per side, merging
# the approach wing with the runway strip (ICAO Figure 4-1). Vertex order
# and single-ring-per-side construction mirror the legacy
# TransitionalSurface_UTM.py SurfaceArea = [pt_08, pt_01T, pt_02T, pt_02, pt_01A]
# pattern, so wing and strip are never separate features and can't show a
# seam.
#
# At the near end (selected threshold, approach inner edge start):
#   inner point: half_inner from centreline, Z = start_elevation_m
#   outer point: half_inner + lateral_near from centreline, Z = cap_elevation
# At the far end (opposite threshold):
#   inner point: half_inner from centreline, Z = opp_start_elevation_m
#   outer point: half_inner + lateral_far from centreline, Z = cap_elevation
# lateral_near/lateral_far are each derived from that end's own elevation —
# not a single shared value — so the band narrows/widens realistically.
#
# At d_cap along the approach, the approach elevation = cap_elevation → wings
# converge to a single point at approach-edge width from centreline, Z = cap_elevation.
# ---------------------------------------------------------------------------

# Origin: start of approach inner edge
pt_start = thr_point.project(distance_from_threshold_m, azimuth)
pt_start.setZ(start_elevation_m)

# Far convergence vertex (approach elevation = cap)
pt_far_axis = pt_start.project(d_cap, azimuth)
pt_far_axis.setZ(cap_elevation)

# Left side — near end (selected threshold)
near_inner_l = pt_start.project(half_inner, azimuth + 90)
near_inner_l.setZ(start_elevation_m)

near_outer_l = pt_start.project(half_inner + lateral_near, azimuth + 90)
near_outer_l.setZ(cap_elevation)

far_l = pt_far_axis.project(far_half_width, azimuth + 90)
far_l.setZ(cap_elevation)

# Right side — near end (selected threshold)
near_inner_r = pt_start.project(half_inner, azimuth - 90)
near_inner_r.setZ(start_elevation_m)

near_outer_r = pt_start.project(half_inner + lateral_near, azimuth - 90)
near_outer_r.setZ(cap_elevation)

far_r = pt_far_axis.project(far_half_width, azimuth - 90)
far_r.setZ(cap_elevation)

if has_opposite_threshold:
    opp_thr_pt2 = QgsPoint(opp_thr_x, opp_thr_y)
    opp_thr_pt2.addZValue(opp_start_elevation_m)

    far_inner_l = opp_thr_pt2.project(half_inner, azimuth + 90)
    far_inner_l.setZ(opp_start_elevation_m)
    far_outer_l = opp_thr_pt2.project(half_inner + lateral_far, azimuth + 90)
    far_outer_l.setZ(cap_elevation)

    far_inner_r = opp_thr_pt2.project(half_inner, azimuth - 90)
    far_inner_r.setZ(opp_start_elevation_m)
    far_outer_r = opp_thr_pt2.project(half_inner + lateral_far, azimuth - 90)
    far_outer_r.setZ(cap_elevation)

    # Same vertex order for both sides — mirroring comes from azimuth + 90
    # vs azimuth - 90 in the point projections above, not from reordering.
    left_ring = [far_l, near_outer_l, far_outer_l, far_inner_l, near_inner_l]
    right_ring = [far_r, near_outer_r, far_outer_r, far_inner_r, near_inner_r]
else:
    # No opposite threshold available — fall back to the wing-only triangle.
    left_ring = [near_inner_l, near_outer_l, far_l]
    right_ring = [near_inner_r, near_outer_r, far_r]

# ---------------------------------------------------------------------------
# Memory layer
# ---------------------------------------------------------------------------
layer_name = "NewOLS_OES_Transitional"
oes_layer = QgsVectorLayer("PolygonZ?crs=" + map_srid, layer_name, "memory")
oes_layer.dataProvider().addAttributes([
    QgsField('ID', QVariant.Int),
    QgsField('SurfaceName', QVariant.String),
    QgsField('side', QVariant.String),
    QgsField('slope_pct', QVariant.Double),
    QgsField('cap_elevation_m', QVariant.Double),
    QgsField('d_cap_m', QVariant.Double),
    QgsField('lateral_near_m', QVariant.Double),
])
oes_layer.updateFields()

feat_l = QgsFeature()
feat_l.setGeometry(QgsPolygon(QgsLineString(left_ring + [left_ring[0]])))
feat_l.setAttributes([
    1, 'New OLS OES Transitional', 'left',
    slope_pct, round(cap_elevation, 3), round(d_cap, 1), round(lateral_near, 1),
])

feat_r = QgsFeature()
feat_r.setGeometry(QgsPolygon(QgsLineString(right_ring + [right_ring[0]])))
feat_r.setAttributes([
    2, 'New OLS OES Transitional', 'right',
    slope_pct, round(cap_elevation, 3), round(d_cap, 1), round(lateral_near, 1),
])

oes_layer.dataProvider().addFeatures([feat_l, feat_r])

QgsProject.instance().addMapLayers([oes_layer])
oes_layer.renderer().symbol().setColor(QColor("#87CEEB"))  # sky blue
oes_layer.renderer().symbol().setOpacity(0.4)
oes_layer.triggerRepaint()

oes_layer.selectAll()
canvas = iface.mapCanvas()
canvas.zoomToSelected(oes_layer)
oes_layer.removeSelection()
sc = canvas.scale()
if sc < 20000:
    sc = 20000
canvas.zoomScale(sc)

print(
    f"QOLS New OLS OES: surfaces created — d_cap={d_cap:.1f}m, "
    f"lateral_near={lateral_near:.1f}m, lateral_far={lateral_far:.1f}m, "
    f"cap={cap_elevation:.1f}m"
)
iface.messageBar().pushMessage(
    "QOLS Success",
    f"New OLS OES Transitional (slope {slope_pct}%, cap +{cap_height_m}m, extent {d_cap:.0f}m) "
    f"calculated successfully",
    level=MSG_SUCCESS,
)
_script_success = True

for _g in set(globals().keys()).difference(myglobals):
    if _g not in ('myglobals', '_script_success'):
        del globals()[_g]
