"""
New OLS Concept — OES Transitional Surface
Two triangular wings flanking the OFS Approach surface, per ICAO Figure 4-1.

Geometry (plan view, one wing):
  near_inner  — approach inner edge at start, Z = start_elevation
  near_outer  — start + lateral_near outward, Z = cap_elevation
  far_vertex  — approach inner edge at d_cap, Z = cap_elevation
where:
  d_cap        = cap_height / approach_slope   (≈ 1 802 m for 3.33 %, 60 m cap)
  lateral_near = cap_height / trans_slope      (≈ 300 m for 20 % slope)

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
    opp_thr_x = globals().get('opp_thr_x', None)
    opp_thr_y = globals().get('opp_thr_y', None)
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

start_point = line_pts[0]
end_point = line_pts[-1]
base_azimuth_deg = start_point.azimuth(end_point)

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

thr_geom = threshold_sel[0].geometry().asPoint()
thr_point = QgsPoint(thr_geom)
thr_point.addZValue(start_elevation_m)

dist_to_start = hypot(thr_point.x() - start_point.x(), thr_point.y() - start_point.y())
dist_to_end = hypot(thr_point.x() - end_point.x(), thr_point.y() - end_point.y())
selected_end = 'start' if dist_to_start <= dist_to_end else 'end'
outward_azimuth = base_azimuth_deg if selected_end == 'start' else (base_azimuth_deg + 180) % 360
azimuth = (outward_azimuth + 180) % 360 if direction == 0 else outward_azimuth

print(f"QOLS New OLS OES: azimuth={azimuth:.2f}°, selected_end={selected_end}")

# ---------------------------------------------------------------------------
# Transitional surface geometry — two triangular wings (ICAO Figure 4-1)
#
# At the near end (approach inner edge start):
#   inner point: half_inner from centreline, Z = start_elevation_m
#   outer point: half_inner + lateral_near from centreline, Z = cap_elevation
#
# At d_cap along the approach, the approach elevation = cap_elevation → wings
# converge to a single point at approach-edge width from centreline, Z = cap_elevation.
#
# Each wing is a triangle: [near_inner, near_outer, far_vertex].
# ---------------------------------------------------------------------------

# Origin: start of approach inner edge
pt_start = thr_point.project(distance_from_threshold_m, azimuth)
pt_start.setZ(start_elevation_m)

# Far convergence vertex (approach elevation = cap)
pt_far_axis = pt_start.project(d_cap, azimuth)
pt_far_axis.setZ(cap_elevation)

# Left wing
near_inner_l = pt_start.project(half_inner, azimuth + 90)
near_inner_l.setZ(start_elevation_m)

near_outer_l = pt_start.project(half_inner + lateral_near, azimuth + 90)
near_outer_l.setZ(cap_elevation)

far_l = pt_far_axis.project(far_half_width, azimuth + 90)
far_l.setZ(cap_elevation)

# Right wing
near_inner_r = pt_start.project(half_inner, azimuth - 90)
near_inner_r.setZ(start_elevation_m)

near_outer_r = pt_start.project(half_inner + lateral_near, azimuth - 90)
near_outer_r.setZ(cap_elevation)

far_r = pt_far_axis.project(far_half_width, azimuth - 90)
far_r.setZ(cap_elevation)

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
feat_l.setGeometry(QgsPolygon(QgsLineString([near_inner_l, near_outer_l, far_l, near_inner_l])))
feat_l.setAttributes([
    1, 'New OLS OES Transitional', 'left',
    slope_pct, round(cap_elevation, 3), round(d_cap, 1), round(lateral_near, 1),
])

feat_r = QgsFeature()
feat_r.setGeometry(QgsPolygon(QgsLineString([near_inner_r, far_r, near_outer_r, near_inner_r])))
feat_r.setAttributes([
    2, 'New OLS OES Transitional', 'right',
    slope_pct, round(cap_elevation, 3), round(d_cap, 1), round(lateral_near, 1),
])

# ---------------------------------------------------------------------------
# Rectangular runway strips (left and right) from THR1 to THR2
# ---------------------------------------------------------------------------
rwy_feats = []
if opp_thr_x is not None and opp_thr_y is not None:
    opp_thr_pt2 = QgsPoint(opp_thr_x, opp_thr_y)
    opp_thr_pt2.addZValue(opp_start_elevation_m)

    # Near end anchored at pt_start (same origin as the approach wings) so
    # there is no gap between the wing near-edge and the strip near-edge.
    # Outer edge at half_inner + lateral_near from centreline, Z = cap_elevation.
    rwy_ni_l = pt_start.project(half_inner, azimuth + 90)
    rwy_ni_l.setZ(start_elevation_m)
    rwy_no_l = pt_start.project(half_inner + lateral_near, azimuth + 90)
    rwy_no_l.setZ(cap_elevation)
    rwy_fi_l = opp_thr_pt2.project(half_inner, azimuth + 90)
    rwy_fi_l.setZ(opp_start_elevation_m)
    rwy_fo_l = opp_thr_pt2.project(half_inner + lateral_near, azimuth + 90)
    rwy_fo_l.setZ(cap_elevation)

    rwy_ni_r = pt_start.project(half_inner, azimuth - 90)
    rwy_ni_r.setZ(start_elevation_m)
    rwy_no_r = pt_start.project(half_inner + lateral_near, azimuth - 90)
    rwy_no_r.setZ(cap_elevation)
    rwy_fi_r = opp_thr_pt2.project(half_inner, azimuth - 90)
    rwy_fi_r.setZ(opp_start_elevation_m)
    rwy_fo_r = opp_thr_pt2.project(half_inner + lateral_near, azimuth - 90)
    rwy_fo_r.setZ(cap_elevation)

    feat_rwy_l = QgsFeature()
    feat_rwy_l.setGeometry(QgsPolygon(QgsLineString([rwy_ni_l, rwy_no_l, rwy_fo_l, rwy_fi_l, rwy_ni_l])))
    feat_rwy_l.setAttributes([
        5, 'New OLS OES Transitional', 'runway_left',
        slope_pct, round(cap_elevation, 3), round(d_cap, 1), round(lateral_near, 1),
    ])

    feat_rwy_r = QgsFeature()
    feat_rwy_r.setGeometry(QgsPolygon(QgsLineString([rwy_ni_r, rwy_fi_r, rwy_fo_r, rwy_no_r, rwy_ni_r])))
    feat_rwy_r.setAttributes([
        6, 'New OLS OES Transitional', 'runway_right',
        slope_pct, round(cap_elevation, 3), round(d_cap, 1), round(lateral_near, 1),
    ])
    rwy_feats = [feat_rwy_l, feat_rwy_r]

oes_layer.dataProvider().addFeatures([feat_l, feat_r] + rwy_feats)

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
    f"QOLS New OLS OES: wings created — d_cap={d_cap:.1f}m, "
    f"lateral_near={lateral_near:.1f}m, cap={cap_elevation:.1f}m"
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
