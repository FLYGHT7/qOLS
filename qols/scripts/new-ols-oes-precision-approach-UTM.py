"""
New OLS Concept — OES Surface for Precision Approaches
ICAO Annex 14 Table 4-12 / Figure 4-6 (#135). Ported from qpansopy's
Basic ILS Surfaces tool (Q_Pansopy/modules/basic_ils.py::calculate_basic_ils),
values and shapes kept identical, adapted to this plugin's runway/
threshold/direction resolution (mirrors new-ols-oes-transitional-UTM.py).

One deliberate omission from the qpansopy reference: its "ground
surface" (a flat rectangle connecting the approach surface's inner edge
to the missed-approach surface's inner edge) is not part of Annex 14
Table 4-12 or Figure 4-6 — only Approach, Missed Approach, and
Transitional are ICAO-defined. Confirmed with the user and omitted;
see doc/PR_135.md. The ground surface's own corner points are not lost
by this: they are exactly the same points already needed as the
approach/missed-approach surfaces' own inner-edge corners (gs_a/gs_d
below are the approach surface's inner edge; missed_a/missed_f are the
missed-approach surface's inner edge, used directly wherever qpansopy's
ground-surface corners gs_b/gs_c would have been referenced).

Direction convention: ``approach_azimuth`` points away from the runway,
out over the approach path (qpansopy's ``back_azimuth``);
``missed_azimuth`` continues past the threshold in the landing
direction of travel (qpansopy's ``azimuth``). All LEFT/RIGHT lateral
offsets — for both the approach and missed-approach sides — use
``approach_azimuth ± 90`` consistently (matching qpansopy's own choice
of always offsetting from ``back_azimuth``), so "left" stays the same
physical side across the whole surface; using ``missed_azimuth ± 90``
for the missed-approach half would silently swap left/right there.

Per #159, every genuinely-used Table 4-12 value is UI-editable
(appr_*/missed_*/trans_slope_pct — see the Parameters section below),
defaulting to the ICAO table when not overridden.
``missed_approach.inner_edge_m`` and
``missed_approach.section_1.divergence_pct`` are intentionally not
exposed: this script never reads them (both approach and missed-
approach inner edges reuse ``half_inner`` from ``appr.inner_edge_m``
only, and the missed-approach 1st-section half-width is derived from
the transitional slope, not this divergence percentage — see
qols/surfaces/new_ols_precision_approach.py's module docstring).

Procedure to be used in Projected Coordinate System Only.
"""
myglobals = set(globals().keys())

from qgis.core import *
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from math import sqrt
from qols.parameters_inspector import build_parameters_json, add_parameters_field, register_parameters_action
from qols.surfaces.new_ols_precision_approach import get_precision_approach_dimensions

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


def _closest_feature(features, pt):
    return min(
        features,
        key=lambda f: ((f.geometry().asPoint().x() - pt.x()) ** 2
                       + (f.geometry().asPoint().y() - pt.y()) ** 2),
    )


# ---------------------------------------------------------------------------
# Parameters
# ---------------------------------------------------------------------------
_defaults = get_precision_approach_dimensions()  # Table 4-12, used as fallback only
_d_appr = _defaults['approach']
_d_missed = _defaults['missed_approach']

try:
    start_elevation_m = globals().get('start_elevation_m', 0.0)
    direction = globals().get('direction', 0)
    runway_layer = globals().get('runway_layer', None)
    threshold_layer = globals().get('threshold_layer', None)
    use_runway_selected = globals().get('use_runway_selected', True)
    use_threshold_selected = globals().get('use_threshold_selected', True)
    appr_distance_from_threshold_m = globals().get(
        'appr_distance_from_threshold_m', _d_appr['distance_from_threshold_m'])
    appr_inner_edge_m = globals().get('appr_inner_edge_m', _d_appr['inner_edge_m'])
    appr_s1_length_m = globals().get('appr_s1_length_m', _d_appr['section_1']['length_m'])
    appr_s1_divergence_pct = globals().get('appr_s1_divergence_pct', _d_appr['section_1']['divergence_pct'])
    appr_s1_slope_pct = globals().get('appr_s1_slope_pct', _d_appr['section_1']['slope_pct'])
    appr_s2_length_m = globals().get('appr_s2_length_m', _d_appr['section_2']['length_m'])
    appr_s2_divergence_pct = globals().get('appr_s2_divergence_pct', _d_appr['section_2']['divergence_pct'])
    appr_s2_slope_pct = globals().get('appr_s2_slope_pct', _d_appr['section_2']['slope_pct'])
    missed_distance_after_threshold_m = globals().get(
        'missed_distance_after_threshold_m', _d_missed['distance_after_threshold_m'])
    missed_s1_length_m = globals().get('missed_s1_length_m', _d_missed['section_1']['length_m'])
    missed_s1_slope_pct = globals().get('missed_s1_slope_pct', _d_missed['section_1']['slope_pct'])
    missed_s2_length_m = globals().get('missed_s2_length_m', _d_missed['section_2']['length_m'])
    missed_s2_divergence_pct = globals().get('missed_s2_divergence_pct', _d_missed['section_2']['divergence_pct'])
    missed_s2_slope_pct = globals().get('missed_s2_slope_pct', _d_missed['section_2']['slope_pct'])
    trans_slope_pct = globals().get('trans_slope_pct', _defaults['transitional']['slope_pct'])
except Exception as e:
    print(f"NewOLS_OES_PrecisionApproach: Error getting parameters, using defaults: {e}")
    start_elevation_m = 0.0
    direction = 0
    runway_layer = None
    threshold_layer = None
    use_runway_selected = True
    use_threshold_selected = True
    appr_distance_from_threshold_m = _d_appr['distance_from_threshold_m']
    appr_inner_edge_m = _d_appr['inner_edge_m']
    appr_s1_length_m = _d_appr['section_1']['length_m']
    appr_s1_divergence_pct = _d_appr['section_1']['divergence_pct']
    appr_s1_slope_pct = _d_appr['section_1']['slope_pct']
    appr_s2_length_m = _d_appr['section_2']['length_m']
    appr_s2_divergence_pct = _d_appr['section_2']['divergence_pct']
    appr_s2_slope_pct = _d_appr['section_2']['slope_pct']
    missed_distance_after_threshold_m = _d_missed['distance_after_threshold_m']
    missed_s1_length_m = _d_missed['section_1']['length_m']
    missed_s1_slope_pct = _d_missed['section_1']['slope_pct']
    missed_s2_length_m = _d_missed['section_2']['length_m']
    missed_s2_divergence_pct = _d_missed['section_2']['divergence_pct']
    missed_s2_slope_pct = _d_missed['section_2']['slope_pct']
    trans_slope_pct = _defaults['transitional']['slope_pct']

# #159 — "expose all the parameters": every genuinely-used Table 4-12
# value above is UI-editable, defaulting to the ICAO table when not
# overridden. missed_approach.inner_edge_m and
# missed_approach.section_1.divergence_pct are intentionally excluded
# (not read by this script at all — see module docstring — exposing
# them as editable would mislead).
dims = {
    'approach': {
        'distance_from_threshold_m': appr_distance_from_threshold_m,
        'inner_edge_m': appr_inner_edge_m,
        'section_1': {'length_m': appr_s1_length_m, 'divergence_pct': appr_s1_divergence_pct,
                      'slope_pct': appr_s1_slope_pct},
        'section_2': {'length_m': appr_s2_length_m, 'divergence_pct': appr_s2_divergence_pct,
                      'slope_pct': appr_s2_slope_pct},
    },
    'missed_approach': {
        'distance_after_threshold_m': missed_distance_after_threshold_m,
        'section_1': {'length_m': missed_s1_length_m, 'slope_pct': missed_s1_slope_pct},
        'section_2': {'length_m': missed_s2_length_m, 'divergence_pct': missed_s2_divergence_pct,
                      'slope_pct': missed_s2_slope_pct},
    },
    'transitional': {'slope_pct': trans_slope_pct},
}
appr = dims['approach']
missed = dims['missed_approach']

map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()

# ---------------------------------------------------------------------------
# Runway layer
# ---------------------------------------------------------------------------
try:
    if runway_layer is None:
        raise Exception("No Runway Layer Centerline provided.")
    if use_runway_selected:
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
    if use_threshold_selected:
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

# direction picks the runway-centerline endpoint (0 = Start to End,
# -1 = End to Start), same convention as new-ols-oes-transitional-UTM.py.
s = direction
near_end_pt = line_pts[s]
far_end_pt = line_pts[-1 - s]
approach_azimuth = far_end_pt.azimuth(near_end_pt)      # away from runway, over the approach path
missed_azimuth = (approach_azimuth + 180.0) % 360.0     # continues past threshold, landing direction of travel

near_thr_feat = _closest_feature(threshold_sel, near_end_pt)
thr_geom = near_thr_feat.geometry().asPoint()
thr_point = QgsPoint(thr_geom)
thr_point.addZValue(start_elevation_m)

print(f"NewOLS_OES_PrecisionApproach: approach_azimuth={approach_azimuth:.2f} missed_azimuth={missed_azimuth:.2f}")

# ---------------------------------------------------------------------------
# Geometry — ported 1:1 from calculate_basic_ils(), ground surface omitted
# ---------------------------------------------------------------------------
half_inner = appr['inner_edge_m'] / 2.0  # 150 m — shared by approach & missed approach

# Approach surface — origin (inner edge)
gs_center = thr_point.project(appr['distance_from_threshold_m'], approach_azimuth)
gs_a = gs_center.project(half_inner, approach_azimuth - 90)
gs_d = gs_center.project(half_inner, approach_azimuth + 90)

# Approach section 1
as1_len = appr['section_1']['length_m']
as1_div = appr['section_1']['divergence_pct'] / 100.0
as1_slope = appr['section_1']['slope_pct'] / 100.0
as1_center = gs_center.project(as1_len, approach_azimuth)
as1_half_width = half_inner + as1_len * as1_div
as1_a = as1_center.project(as1_half_width, approach_azimuth - 90)
as1_d = as1_center.project(as1_half_width, approach_azimuth + 90)
as1_height = as1_len * as1_slope  # 60 m

# Approach section 2 (divergence/height measured cumulatively from the origin)
as2_len = appr['section_2']['length_m']
as2_div = appr['section_2']['divergence_pct'] / 100.0
as2_slope = appr['section_2']['slope_pct'] / 100.0
as2_center = as1_center.project(as2_len, approach_azimuth)
as2_half_width = half_inner + (as1_len + as2_len) * as2_div
as2_a = as2_center.project(as2_half_width, approach_azimuth - 90)
as2_d = as2_center.project(as2_half_width, approach_azimuth + 90)
as2_height = as1_height + as2_len * as2_slope  # 300 m

# Missed approach surface — origin (inner edge)
missed_center = thr_point.project(missed['distance_after_threshold_m'], missed_azimuth)
missed_a = missed_center.project(half_inner, approach_azimuth - 90)
missed_f = missed_center.project(half_inner, approach_azimuth + 90)

# Missed approach section 1 — half-width derived from the transitional
# slope reaching this section's own height of rise (not a literal
# ×divergence_pct multiply — see module docstring and new_ols_precision_
# approach.py docstring for why).
m1_len = missed['section_1']['length_m']
m1_slope = missed['section_1']['slope_pct'] / 100.0
m1_height = m1_len * m1_slope  # 45 m
m1_half_width = half_inner + m1_height / (trans_slope_pct / 100.0)
missed_m_center = missed_center.project(m1_len, missed_azimuth)
missed_b = missed_m_center.project(m1_half_width, approach_azimuth - 90)
missed_e = missed_m_center.project(m1_half_width, approach_azimuth + 90)

# Missed approach section 2 (slope unchanged at 2.5%, so height accumulates
# linearly from the origin; divergence is this section's own 25% splay
# added on top of the 1st section's half-width)
m2_len = missed['section_2']['length_m']
m2_div = missed['section_2']['divergence_pct'] / 100.0
m2_slope = missed['section_2']['slope_pct'] / 100.0
m2_height = m1_height + m2_len * m2_slope  # 300 m
m2_half_width = m1_half_width + m2_len * m2_div
missed_f_center = missed_center.project(m1_len + m2_len, missed_azimuth)
missed_c = missed_f_center.project(m2_half_width, approach_azimuth - 90)
missed_d = missed_f_center.project(m2_half_width, approach_azimuth + 90)

# Transitional surface side distances (14.3% slope connecting the
# approach/missed-approach height steps: 0 -> as1_height -> as2_height,
# and as2_height -> m1_height)
trans_slope = trans_slope_pct / 100.0
transition_distance_1 = (as2_height - as1_height) / trans_slope
transition_distance_2 = as2_height / trans_slope
transition_distance_3 = (as2_height - m1_height) / trans_slope

transition_e1_left = as1_d.project(transition_distance_1, approach_azimuth + 90)
transition_e1_right = as1_a.project(transition_distance_1, approach_azimuth - 90)
transition_e2_left = gs_d.project(transition_distance_2, approach_azimuth + 90)
transition_e2_right = gs_a.project(transition_distance_2, approach_azimuth - 90)
transition_e3_left = missed_e.project(transition_distance_3, approach_azimuth + 90)
transition_e3_right = missed_b.project(transition_distance_3, approach_azimuth - 90)

# ---------------------------------------------------------------------------
# Elevations
# ---------------------------------------------------------------------------
z0 = start_elevation_m
z_as1 = start_elevation_m + as1_height
z_as2 = start_elevation_m + as2_height
z_m1 = start_elevation_m + m1_height
z_m2 = start_elevation_m + m2_height  # numerically == z_as2 (both 300 m)


def _pz(pt, z):
    p = QgsPoint(pt.x(), pt.y())
    p.addZValue(z)
    return p


# ---------------------------------------------------------------------------
# Memory layer
# ---------------------------------------------------------------------------
layer_name = "NewOLS_OES_PrecisionApproach"
v_layer = QgsVectorLayer(f"PolygonZ?crs={map_srid}", layer_name, "memory")
v_layer_provider = v_layer.dataProvider()
v_layer_provider.addAttributes([
    QgsField("surface_type", QVariant.String),
    QgsField("component", QVariant.String),
    QgsField("slope_pct", QVariant.Double),
    QgsField("rule_set", QVariant.String),
])
v_layer.updateFields()

_active_rule_set = globals().get('active_rule_set', None)
_params_json = build_parameters_json('New OLS OES Surface for Precision Approaches', {
    'start_elevation_m': round(start_elevation_m, 3),
    'direction': direction,
    'dimensions': dims,
    'rule_set': _active_rule_set,
})
add_parameters_field(v_layer)

features = []


def _add_feature(component, slope_pct, ring_pts_with_z):
    f = QgsFeature()
    f.setGeometry(QgsPolygon(QgsLineString(ring_pts_with_z)))
    f.setAttributes(["Surface for Precision Approaches", component, slope_pct, _active_rule_set, _params_json])
    features.append(f)


_add_feature('approach section 1', appr['section_1']['slope_pct'], [
    _pz(as1_a, z_as1), _pz(gs_a, z0), _pz(gs_d, z0), _pz(as1_d, z_as1),
])
_add_feature('approach section 2', appr['section_2']['slope_pct'], [
    _pz(as2_a, z_as2), _pz(as1_a, z_as1), _pz(as1_d, z_as1), _pz(as2_d, z_as2),
])
_add_feature('missed approach', missed['section_1']['slope_pct'], [
    _pz(missed_a, z0), _pz(missed_b, z_m1), _pz(missed_c, z_m2),
    _pz(missed_d, z_m2), _pz(missed_e, z_m1), _pz(missed_f, z0),
])
_add_feature('transitional - left 1', trans_slope_pct, [
    _pz(as2_d, z_as2), _pz(as1_d, z_as1), _pz(transition_e1_left, z_as2),
])
_add_feature('transitional - left 2', trans_slope_pct, [
    _pz(as1_d, z_as1), _pz(transition_e1_left, z_as2), _pz(transition_e2_left, z_as2), _pz(gs_d, z0),
])
_add_feature('transitional - left 3', trans_slope_pct, [
    _pz(transition_e2_left, z_as2), _pz(gs_d, z0), _pz(missed_f, z0),
    _pz(missed_e, z_m1), _pz(transition_e3_left, z_as2),
])
_add_feature('transitional - left 4', trans_slope_pct, [
    _pz(missed_e, z_m1), _pz(missed_d, z_m2), _pz(transition_e3_left, z_as2),
])
_add_feature('transitional - right 1', trans_slope_pct, [
    _pz(as2_a, z_as2), _pz(as1_a, z_as1), _pz(transition_e1_right, z_as2),
])
_add_feature('transitional - right 2', trans_slope_pct, [
    _pz(as1_a, z_as1), _pz(transition_e1_right, z_as2), _pz(transition_e2_right, z_as2), _pz(gs_a, z0),
])
_add_feature('transitional - right 3', trans_slope_pct, [
    _pz(transition_e2_right, z_as2), _pz(transition_e3_right, z_as2),
    _pz(missed_b, z_m1), _pz(missed_a, z0), _pz(gs_a, z0),
])
_add_feature('transitional - right 4', trans_slope_pct, [
    _pz(missed_b, z_m1), _pz(missed_c, z_m2), _pz(transition_e3_right, z_as2),
])

v_layer_provider.addFeatures(features)
v_layer.updateExtents()
print(f"NewOLS_OES_PrecisionApproach: Created {len(features)} feature(s)")

register_parameters_action(v_layer)

QgsProject.instance().addMapLayers([v_layer])

symbol = QgsFillSymbol.createSimple({
    'color': '255,165,0,90',  # soft amber/orange, transparent
    'style': 'solid',
    'outline_color': '255,140,0,220',
    'outline_style': 'solid',
    'outline_width': '0.7',
})
v_layer.renderer().setSymbol(symbol)
v_layer.triggerRepaint()

if features:
    v_layer.selectAll()
    canvas = iface.mapCanvas()
    canvas.zoomToSelected(v_layer)
    v_layer.removeSelection()
    sc = canvas.scale()
    if sc < 50000:
        sc = 50000
    canvas.zoomScale(sc)

if not use_runway_selected and runway_layer:
    runway_layer.removeSelection()
if not use_threshold_selected and threshold_layer:
    threshold_layer.removeSelection()

iface.messageBar().pushMessage(
    "QOLS Success",
    "New OLS OES Surface for Precision Approaches calculated successfully",
    level=MSG_SUCCESS,
)

_script_success = True

for _g in set(globals().keys()).difference(myglobals):
    if _g not in ('myglobals', '_script_success'):
        del globals()[_g]
