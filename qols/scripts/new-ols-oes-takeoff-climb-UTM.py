"""
New OLS Concept — OES Take-off Climb Surface
ICAO Annex 14 Table 4-14 (mass up to 5 700 kg) / Table 4-15 (mass
above 5 700 kg) / Figure 4-8 (#161).

Geometry ported from the classic OLS's own take-off climb surface
script (qols/scripts/take-off-surface_UTM.py), the only existing
implementation of this exact surface in this codebase:

* Origin offset dD = max(distance_from_runway_end_m, cwy_length_m) —
  Table 4-14's own footnote ("the surface starts at the end of the
  clearway if the clearway length exceeds the specified distance").
  Table 4-15's "Distance from TODA" column is "-" for every ADG (the
  surface starts right at TODA = runway end + clearway); modeled in
  qols/surfaces/new_ols_takeoff_climb.py as distance_from_runway_end_m
  = 0.0 for Table 4-15 rows, so the same max() formula produces the
  correct TODA-relative origin (max(0, cwy) == cwy) without any
  mass-category branching here.
* Plan view is a single hexagon: diverge from inner_edge_m at the
  origin until final_width_m is reached (distance_to_max_width), then
  continue at constant final_width_m out to length_m.
* The sloped plane climbs for the FULL length_m, independent of
  distance_to_max_width — confirmed against the classic script, where
  the far-end point's Z uses surfaceLength * slope_ratio while the
  cap-point's Z uses only distance_to_max_width * slope_ratio. For
  Table 4-14 both values coincide (distance_to_max_width == length_m
  exactly for its two rows), degenerating to a plain trapezoid; for
  Table 4-15 they differ, producing a genuine diverge-then-constant
  shape with the plane still climbing past the width cap.
* Cross-sections are flat (not gabled) — same precedent as every other
  planar OLS surface in this codebase (Approach, Departure, classic
  Take-off).

Independently cross-checked against ../flight/tofpa's own TOFPA AOC
Type A implementation (ICAO Doc 8168, the PANS-OPS analogue the issue
itself points to for the CWY-override provision) — ``tofpa.py``'s
``pt_02D``/``pt_03D`` Z assignment (cap point uses only
``distance_to_max_width``, end point uses the full
``TOFPA_SURFACE_LENGTH``) and its hexagon ring order
(``[pt_03DR, pt_03DL, pt_02DL, pt_01DL, pt_01DR, pt_02DR]``) match this
script's geometry vertex-for-vertex. Confirms the hexagon shape,
full-length slope, and flat cross-sections above are not just an
inference from the classic qOLS script but agree with a second,
independent implementation of the same surface concept.

Unlike the classic panel, every Table 4-14/4-15 value here is
independently user-editable (#159 convention), so an inconsistent
combination (e.g. divergence_pct too small for final_width_m/length_m)
is reachable; distance_to_max_width is defensively clamped to
length_m, which the classic script does not need since its own fields
aren't independently overridable.

DER (runway end) resolution mirrors new-ols-oes-departure-UTM.py: the
runway centerline's own far endpoint in the direction of travel, no
separate DER point layer needed.

Procedure to be used in Projected Coordinate System Only.
"""
myglobals = set(globals().keys())

from qgis.core import *
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from math import sqrt
from qols.parameters_inspector import build_parameters_json, add_parameters_field, register_parameters_action
from qols.surfaces.new_ols_takeoff_climb import get_takeoff_climb_surface_dimensions, MASS_CATEGORY_LE_5700

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
_defaults = get_takeoff_climb_surface_dimensions(MASS_CATEGORY_LE_5700, "I")  # Table 4-14 ADG I, fallback only

try:
    start_elevation_m = globals().get('start_elevation_m', 0.0)
    direction = globals().get('direction', 0)
    runway_layer = globals().get('runway_layer', None)
    use_runway_selected = globals().get('use_runway_selected', True)
    cwy_length_m = globals().get('cwy_length_m', 0.0)
    distance_from_runway_end_m = globals().get(
        'distance_from_runway_end_m', _defaults['distance_from_runway_end_m'])
    inner_edge_m = globals().get('inner_edge_m', _defaults['inner_edge_m'])
    divergence_pct = globals().get('divergence_pct', _defaults['divergence_pct'])
    final_width_m = globals().get('final_width_m', _defaults['final_width_m'])
    length_m = globals().get('length_m', _defaults['length_m'])
    slope_pct = globals().get('slope_pct', _defaults['slope_pct'])
except Exception as e:
    print(f"NewOLS_OES_TakeoffClimb: Error getting parameters, using defaults: {e}")
    start_elevation_m = 0.0
    direction = 0
    runway_layer = None
    use_runway_selected = True
    cwy_length_m = 0.0
    distance_from_runway_end_m = _defaults['distance_from_runway_end_m']
    inner_edge_m = _defaults['inner_edge_m']
    divergence_pct = _defaults['divergence_pct']
    final_width_m = _defaults['final_width_m']
    length_m = _defaults['length_m']
    slope_pct = _defaults['slope_pct']

# #159 — every Table 4-14/4-15 value above is UI-editable, defaulting to
# the ICAO table when not overridden.
dims = {
    'distance_from_runway_end_m': distance_from_runway_end_m,
    'inner_edge_m': inner_edge_m,
    'divergence_pct': divergence_pct,
    'final_width_m': final_width_m,
    'length_m': length_m,
    'slope_pct': slope_pct,
}

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
# The far endpoint is the physical runway end in the direction of takeoff.
s = direction
near_end_pt = line_pts[s]
far_end_pt = line_pts[-1 - s]
rwy_end_azimuth = near_end_pt.azimuth(far_end_pt)  # away from the runway, takeoff/climb-out direction

rwy_end_point = QgsPoint(far_end_pt.x(), far_end_pt.y())
rwy_end_point.addZValue(start_elevation_m)

print(f"NewOLS_OES_TakeoffClimb: rwy_end_azimuth={rwy_end_azimuth:.2f}")

# ---------------------------------------------------------------------------
# Geometry — ported from take-off-surface_UTM.py's own hexagon/slope math.
# ---------------------------------------------------------------------------
divergence_ratio = dims['divergence_pct'] / 100.0
slope_ratio = dims['slope_pct'] / 100.0
half_inner = dims['inner_edge_m'] / 2.0
half_final = dims['final_width_m'] / 2.0

# Origin offset — the CWY footnote applies identically to both tables
# (max(0, cwy) == cwy for Table 4-15's zero distance_from_runway_end_m).
dD = max(dims['distance_from_runway_end_m'], cwy_length_m)

origin_pt = rwy_end_point.project(dD, rwy_end_azimuth)
origin_pt.addZValue(start_elevation_m)
origin_l = origin_pt.project(half_inner, rwy_end_azimuth + 90)
origin_r = origin_pt.project(half_inner, rwy_end_azimuth - 90)

distance_to_max_width = ((half_final - half_inner) / divergence_ratio) if divergence_ratio else 0.0
# Defensive clamp: every field here is independently user-editable
# (unlike the classic panel's fixed relationship), so an inconsistent
# combination could otherwise push the cap point past the surface end.
distance_to_max_width = min(distance_to_max_width, dims['length_m'])


def _pz(pt, z):
    p = QgsPoint(pt.x(), pt.y())
    p.addZValue(z)
    return p


mid_pt = origin_pt.project(distance_to_max_width, rwy_end_azimuth)
z_mid = start_elevation_m + distance_to_max_width * slope_ratio
mid_l = _pz(mid_pt.project(half_final, rwy_end_azimuth + 90), z_mid)
mid_r = _pz(mid_pt.project(half_final, rwy_end_azimuth - 90), z_mid)

end_pt = origin_pt.project(dims['length_m'], rwy_end_azimuth)
# Slope runs the full surface length, independent of the divergence cap.
z_end = start_elevation_m + dims['length_m'] * slope_ratio
end_l = _pz(end_pt.project(half_final, rwy_end_azimuth + 90), z_end)
end_r = _pz(end_pt.project(half_final, rwy_end_azimuth - 90), z_end)

origin_l = _pz(origin_l, start_elevation_m)
origin_r = _pz(origin_r, start_elevation_m)

# ---------------------------------------------------------------------------
# Memory layer
# ---------------------------------------------------------------------------
layer_name = "NewOLS_OES_TakeoffClimb"
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
_params_json = build_parameters_json('New OLS OES Take-off Climb Surface', {
    'start_elevation_m': round(start_elevation_m, 3),
    'direction': direction,
    'cwy_length_m': cwy_length_m,
    'dimensions': dims,
    'rule_set': _active_rule_set,
})
add_parameters_field(v_layer)

features = []


def _add_feature(component, slope_pct, ring_pts_with_z):
    f = QgsFeature()
    f.setGeometry(QgsPolygon(QgsLineString(ring_pts_with_z)))
    f.setAttributes(["Take-off Climb Surface", component, slope_pct, _active_rule_set, _params_json])
    features.append(f)


_add_feature('Take-off Climb Surface', dims['slope_pct'], [
    end_r, end_l, mid_l, origin_l, origin_r, mid_r,
])

v_layer_provider.addFeatures(features)
v_layer.updateExtents()
print(f"NewOLS_OES_TakeoffClimb: Created {len(features)} feature(s)")

register_parameters_action(v_layer)

QgsProject.instance().addMapLayers([v_layer])

symbol = QgsFillSymbol.createSimple({
    'color': '34,139,34,90',  # forest green, transparent
    'style': 'solid',
    'outline_color': '0,100,0,220',
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
    "New OLS OES Take-off Climb Surface calculated successfully",
    level=MSG_SUCCESS,
)

_script_success = True

for _g in set(globals().keys()).difference(myglobals):
    if _g not in ('myglobals', '_script_success'):
        del globals()[_g]
