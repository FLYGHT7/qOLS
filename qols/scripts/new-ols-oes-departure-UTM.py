"""
New OLS Concept — OES Instrument Departure Surface
ICAO Annex 14 Table 4-13 / Figure 4-7 (#136). Ported from qpansopy's
Omnidirectional SID module
(Q_Pansopy/modules/departures/omnidirectional_sid.py::run_omnidirectional_sid),
per the issue's own "similar to the OMNI SID without Area 3" request:
qpansopy's Area 1 (15 deg splay) / Area 2 (30 deg splay) match this
table's section_1/section_2 shape exactly; Area 3 (a circular MSA
buffer, specific to a real departure procedure) has no equivalent in
Table 4-13 and is not built here.

Value differences found and kept as documented (see
qols/surfaces/new_ols_departure.py's module docstring for the full
comparison against qpansopy): the table's own 26.8%/57.8% divergence
percentages are used directly (qpansopy's 15deg/30deg splays give the
same values, just rounded); the table's fixed section lengths
(3500 m/8300 m) and flat 2.5% slope are used as-is, since qpansopy
instead derives its Area 1/2 lengths and effective slope from a
user-supplied Procedure Design Gradient for a specific procedure -- not
applicable to this generic protection surface.

DER (Departure End of Runway) is the runway centerline's own far
endpoint in the direction of travel -- no separate DER point layer is
requested or needed. der_azimuth points away from the runway, in the
takeoff/climb-out direction (the same direction
new-ols-oes-precision-approach-UTM.py calls missed_azimuth).

Per #159, every Table 4-13 value is UI-editable
(initial_height_above_der_m/inner_edge_m/slope_pct/s1_length_m/
s1_divergence_pct/s2_length_m/s2_divergence_pct), defaulting to the
ICAO table when not overridden.

Procedure to be used in Projected Coordinate System Only.
"""
myglobals = set(globals().keys())

from qgis.core import *
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from math import sqrt
from qols.parameters_inspector import build_parameters_json, add_parameters_field, register_parameters_action
from qols.surfaces.new_ols_departure import get_departure_surface_dimensions

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
# Parameters
# ---------------------------------------------------------------------------
_defaults = get_departure_surface_dimensions()  # Table 4-13, used as fallback only

try:
    start_elevation_m = globals().get('start_elevation_m', 0.0)
    direction = globals().get('direction', 0)
    runway_layer = globals().get('runway_layer', None)
    use_runway_selected = globals().get('use_runway_selected', True)
    initial_height_above_der_m = globals().get(
        'initial_height_above_der_m', _defaults['initial_height_above_der_m'])
    inner_edge_m = globals().get('inner_edge_m', _defaults['inner_edge_m'])
    slope_pct = globals().get('slope_pct', _defaults['slope_pct'])
    s1_length_m = globals().get('s1_length_m', _defaults['section_1']['length_m'])
    s1_divergence_pct = globals().get('s1_divergence_pct', _defaults['section_1']['divergence_pct'])
    s2_length_m = globals().get('s2_length_m', _defaults['section_2']['length_m'])
    s2_divergence_pct = globals().get('s2_divergence_pct', _defaults['section_2']['divergence_pct'])
except Exception as e:
    print(f"NewOLS_OES_Departure: Error getting parameters, using defaults: {e}")
    start_elevation_m = 0.0
    direction = 0
    runway_layer = None
    use_runway_selected = True
    initial_height_above_der_m = _defaults['initial_height_above_der_m']
    inner_edge_m = _defaults['inner_edge_m']
    slope_pct = _defaults['slope_pct']
    s1_length_m = _defaults['section_1']['length_m']
    s1_divergence_pct = _defaults['section_1']['divergence_pct']
    s2_length_m = _defaults['section_2']['length_m']
    s2_divergence_pct = _defaults['section_2']['divergence_pct']

# #159 — "expose all the parameters": every Table 4-13 value above is
# UI-editable, defaulting to the ICAO table when not overridden.
dims = {
    'initial_height_above_der_m': initial_height_above_der_m,
    'inner_edge_m': inner_edge_m,
    'slope_pct': slope_pct,
    'section_1': {'length_m': s1_length_m, 'divergence_pct': s1_divergence_pct},
    'section_2': {'length_m': s2_length_m, 'divergence_pct': s2_divergence_pct},
}
s1 = dims['section_1']
s2 = dims['section_2']
slope = dims['slope_pct'] / 100.0

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

# direction picks the runway-centerline endpoint (0 = Start to End,
# -1 = End to Start), same convention as the other New OLS OES scripts.
# DER is the far endpoint itself -- the physical end of the runway in
# the direction of takeoff travel.
s = direction
near_end_pt = line_pts[s]
far_end_pt = line_pts[-1 - s]
der_azimuth = near_end_pt.azimuth(far_end_pt)  # away from the runway, takeoff/climb-out direction

der_point = QgsPoint(far_end_pt.x(), far_end_pt.y())
der_point.addZValue(start_elevation_m + dims['initial_height_above_der_m'])

print(f"NewOLS_OES_Departure: der_azimuth={der_azimuth:.2f}")

# ---------------------------------------------------------------------------
# Geometry -- ported from run_omnidirectional_sid()'s Area 1 / Area 2,
# using Table 4-13's fixed lengths/divergence/slope instead of a
# PDG-derived climb profile.
# ---------------------------------------------------------------------------
half_inner = dims['inner_edge_m'] / 2.0  # 150 m

der_a = der_point.project(half_inner, der_azimuth - 90)
der_b = der_point.project(half_inner, der_azimuth + 90)

s1_len = s1['length_m']
s1_div = s1['divergence_pct'] / 100.0
s1_height = s1_len * slope  # 87.5 m
s1_half_width = half_inner + s1_len * s1_div
s1_center = der_point.project(s1_len, der_azimuth)
s1_a = s1_center.project(s1_half_width, der_azimuth - 90)
s1_b = s1_center.project(s1_half_width, der_azimuth + 90)

# Section 2's divergence differs from section 1's, so the boundary
# genuinely kinks -- widen incrementally from section 1's own edge
# (mirrors qpansopy's width_area_2 = width_area_1 + distance_area_2 *
# tan(...)), not cumulatively from DER.
s2_len = s2['length_m']
s2_div = s2['divergence_pct'] / 100.0
s2_height = s1_height + s2_len * slope  # 295 m
s2_half_width = s1_half_width + s2_len * s2_div
s2_center = s1_center.project(s2_len, der_azimuth)
s2_a = s2_center.project(s2_half_width, der_azimuth - 90)
s2_b = s2_center.project(s2_half_width, der_azimuth + 90)

# ---------------------------------------------------------------------------
# Elevations
# ---------------------------------------------------------------------------
z0 = start_elevation_m + dims['initial_height_above_der_m']
z1 = z0 + s1_height
z2 = z0 + s2_height


def _pz(pt, z):
    p = QgsPoint(pt.x(), pt.y())
    p.addZValue(z)
    return p


# ---------------------------------------------------------------------------
# Memory layer
# ---------------------------------------------------------------------------
layer_name = "NewOLS_OES_Departure"
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
_params_json = build_parameters_json('New OLS OES Instrument Departure Surface', {
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
    f.setAttributes(["Instrument Departure Surface", component, slope_pct, _active_rule_set, _params_json])
    features.append(f)


_add_feature('section 1', dims['slope_pct'], [
    _pz(der_a, z0), _pz(der_b, z0), _pz(s1_b, z1), _pz(s1_a, z1),
])
_add_feature('section 2', dims['slope_pct'], [
    _pz(s1_a, z1), _pz(s1_b, z1), _pz(s2_b, z2), _pz(s2_a, z2),
])

v_layer_provider.addFeatures(features)
v_layer.updateExtents()
print(f"NewOLS_OES_Departure: Created {len(features)} feature(s)")

register_parameters_action(v_layer)

QgsProject.instance().addMapLayers([v_layer])

symbol = QgsFillSymbol.createSimple({
    'color': '220,20,60,90',  # crimson, transparent
    'style': 'solid',
    'outline_color': '178,10,46,220',
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

iface.messageBar().pushMessage(
    "QOLS Success",
    "New OLS OES Instrument Departure Surface calculated successfully",
    level=MSG_SUCCESS,
)

_script_success = True

for _g in set(globals().keys()).difference(myglobals):
    if _g not in ('myglobals', '_script_success'):
        del globals()[_g]
