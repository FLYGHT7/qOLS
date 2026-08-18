"""
New OLS Concept — OES Surface for Straight-in Instrument Approaches
ICAO Annex 14 Table 4-11 / Figure 4-5 (#137). Single "I to V" column —
no Aeroplane Design Group variation, so this surface is always drawn
the same way regardless of the runway's ADG (per the issue's own
"this surface is always done for all ADG" note).

Table 4-11's Lower section is an explicit cross-reference to the
Horizontal OES surface's ADG-I ring ("Length: Horizontal OES as per
ADG I") — its racetrack radius comes from
qols.surfaces.new_ols_horizontal.get_horizontal_surface_rings('I')
rather than a hardcoded value, so it stays in sync with Table 4-10.

Geometry, per Figure 4-5 (a rectangle enclosing the whole runway, with
a racetrack drawn inside it) and this codebase's established flat-tier
convention (#134/#134-followup2 — OES tiers are flat annuli, not
sloped cones, each at its own height above the aerodrome elevation):

* Lower section — the ADG-I Horizontal racetrack itself (full disc,
  no hole), reusing the exact racetrack-ring construction from
  new-ols-oes-horizontal-UTM.py (same coord()/coord2() trig closures).
* Upper section — a runway-azimuth-aligned rectangle (half-width =
  upper_shorter_side_m / 2 across the runway, extended
  upper_longer_side_from_threshold_m beyond each runway end), minus
  the Lower section's racetrack as a hole — a flat annulus built with
  the same difference_flat() utility #124/#134 established for
  Conical/Horizontal.

Both sections go on one output layer, distinguished by a `component`
attribute ("lower_section"/"upper_section") — mirroring how the other
OES scripts identify their own sub-parts on a shared layer.

Per #159, every Table 4-11 value is UI-editable
(lower_height_m/lower_length_m/upper_height_m/upper_shorter_side_m/
upper_longer_side_from_threshold_m), defaulting to the ICAO table when
not overridden.

Procedure to be used in Projected Coordinate System Only.
"""
myglobals = set(globals().keys())

from qgis.core import *
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
import math
from math import sqrt
from qols.parameters_inspector import build_parameters_json, add_parameters_field, register_parameters_action
from qols.surfaces.new_ols_straight_in_approach import get_straight_in_approach_dimensions
from qols.geometry_difference import difference_flat, flatten_ring_z

_script_success = False


def _normalize_polyline_points(geometry):
    if geometry is None or geometry.isEmpty():
        raise Exception("Empty geometry provided for runway centerline.")
    if geometry.isMultipart():
        parts = geometry.asMultiPolyline()
        if not parts:
            raise Exception("Empty MultiLineString geometry.")

        def length_of(pts):
            if not pts or len(pts) < 2:
                return 0.0
            total = 0.0
            for i in range(1, len(pts)):
                dx = pts[i].x() - pts[i - 1].x()
                dy = pts[i].y() - pts[i - 1].y()
                total += sqrt(dx * dx + dy * dy)
            return total
        return [QgsPoint(p) for p in max(parts, key=length_of)]
    poly = geometry.asPolyline()
    if poly and len(poly) >= 2:
        return [QgsPoint(p) for p in poly]
    raise Exception("Line geometry cannot be converted to a polyline.")


def _racetrack_ring_xy(start_point, end_point, angle0, back_angle0, radius, trto, trfm):
    """Builds one closed racetrack ring boundary (list of (x, y) tuples,
    first == last) at the given radius, in flat 2D. Verbatim copy of
    new-ols-oes-horizontal-UTM.py's helper of the same name (this
    codebase's established convention: duplicate per-script rather
    than extract a shared racetrack-geometry module)."""

    def coord(angle0, dist1, off):
        bearing = angle0 + off
        angle = math.radians(90 - bearing)
        bearing = math.radians(bearing)
        dist_x, dist_y = (dist1 * math.cos(angle), dist1 * math.sin(angle))
        xfinal, yfinal = (start_point.x() + dist_x, start_point.y() + dist_y)
        return trto.transform(trfm.transform(xfinal, yfinal))

    def coord2(angle0, dist1, off):
        bearing = angle0 + off
        angle = math.radians(90 - bearing)
        bearing = math.radians(bearing)
        dist_x, dist_y = (dist1 * math.cos(angle), dist1 * math.sin(angle))
        xfinal, yfinal = (end_point.x() + dist_x, end_point.y() + dist_y)
        return trto.transform(trfm.transform(xfinal, yfinal))

    pro_coords = coord(angle0, radius, -90)   # Starting point left
    x2 = coord(angle0, radius, 90)            # Starting point right
    xc = coord(angle0, radius, 0)             # Starting center point
    x4 = coord2(back_angle0, radius, 90)      # Ending point right
    x5 = coord2(back_angle0, radius, 0)       # Ending center point
    x6 = coord2(back_angle0, radius, -90)     # Ending point left

    ring_xy = []

    def _append_arc(p1, p2, p3, skip_first):
        cstring = QgsCircularString()
        cstring.setPoints([QgsPoint(p1[0], p1[1]), QgsPoint(p2[0], p2[1]), QgsPoint(p3[0], p3[1])])
        segmented = QgsGeometry(cstring).convertToType(GEOM_TYPE_LINE, True)
        pts = []
        if segmented:
            if segmented.wkbType() == WKB_LINE_STRING:
                pts = list(segmented.asPolyline())
            elif segmented.wkbType() == WKB_MULTI_LINE_STRING:
                for part in segmented.asMultiPolyline():
                    pts.extend(part)
        if not pts:
            pts = [QgsPointXY(p1[0], p1[1]), QgsPointXY(p2[0], p2[1]), QgsPointXY(p3[0], p3[1])]
        for i, pt in enumerate(pts):
            if skip_first and i == 0:
                continue
            ring_xy.append((pt.x(), pt.y()))

    _append_arc(pro_coords, xc, x2, skip_first=False)
    ring_xy.append((x6[0], x6[1]))
    _append_arc(x6, x5, x4, skip_first=True)
    ring_xy.append((pro_coords[0], pro_coords[1]))

    return ring_xy


def _rectangle_ring_xy(start_point, end_point, angle0, back_angle0, half_width, extension):
    """Builds one closed rectangle ring (list of (x, y) tuples, first ==
    last) enclosing the whole runway: `extension` beyond each end along
    the runway azimuth, `half_width` on either side across it."""
    ext_start = start_point.project(extension, angle0)
    ext_end = end_point.project(extension, back_angle0)
    corner_start_a = ext_start.project(half_width, angle0 - 90)
    corner_end_a = ext_end.project(half_width, back_angle0 + 90)
    corner_end_b = ext_end.project(half_width, back_angle0 - 90)
    corner_start_b = ext_start.project(half_width, angle0 + 90)
    return [
        (corner_start_a.x(), corner_start_a.y()),
        (corner_end_a.x(), corner_end_a.y()),
        (corner_end_b.x(), corner_end_b.y()),
        (corner_start_b.x(), corner_start_b.y()),
        (corner_start_a.x(), corner_start_a.y()),
    ]


def _ring_polygon_2d(ring_xy):
    """Flat 2D QgsGeometry polygon (no Z) from a closed point ring, for
    use as input to QgsGeometry.difference()."""
    return QgsGeometry(QgsPolygon(QgsLineString([QgsPoint(x, y) for x, y in ring_xy])))


# ---------------------------------------------------------------------------
# Parameter extraction
# ---------------------------------------------------------------------------
_defaults = get_straight_in_approach_dimensions()  # Table 4-11, used as fallback only

try:
    aerodrome_elevation_m = globals().get('aerodrome_elevation_m', 0.0)
    direction = globals().get('direction', 0)
    runway_layer = globals().get('runway_layer', None)
    use_runway_selected = globals().get('use_runway_selected', True)
    lower_height_m = globals().get('lower_height_m', _defaults['lower_section']['height_m'])
    lower_length_m = globals().get('lower_length_m', _defaults['lower_section']['length_m'])
    upper_height_m = globals().get('upper_height_m', _defaults['upper_section']['height_m'])
    upper_shorter_side_m = globals().get(
        'upper_shorter_side_m', _defaults['upper_section']['shorter_side_m'])
    upper_longer_side_from_threshold_m = globals().get(
        'upper_longer_side_from_threshold_m',
        _defaults['upper_section']['longer_side_from_threshold_m'])
except Exception as e:
    print(f"NewOLS_OES_StraightInApproach: Error getting parameters, using defaults: {e}")
    aerodrome_elevation_m = 0.0
    direction = 0
    runway_layer = None
    use_runway_selected = True
    lower_height_m = _defaults['lower_section']['height_m']
    lower_length_m = _defaults['lower_section']['length_m']
    upper_height_m = _defaults['upper_section']['height_m']
    upper_shorter_side_m = _defaults['upper_section']['shorter_side_m']
    upper_longer_side_from_threshold_m = _defaults['upper_section']['longer_side_from_threshold_m']

# #159 — "expose all the parameters": every Table 4-11 value above is
# UI-editable, defaulting to the ICAO table when not overridden.
dims = {
    'lower_section': {'height_m': lower_height_m, 'length_m': lower_length_m},
    'upper_section': {
        'height_m': upper_height_m,
        'shorter_side_m': upper_shorter_side_m,
        'longer_side_from_threshold_m': upper_longer_side_from_threshold_m,
    },
}

map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()
source_crs = QgsCoordinateReferenceSystem(4326)
dest_crs = QgsCoordinateReferenceSystem(map_srid)
trto = QgsCoordinateTransform(source_crs, dest_crs, QgsProject.instance())
trfm = QgsCoordinateTransform(dest_crs, source_crs, QgsProject.instance())

# ---------------------------------------------------------------------------
# Runway layer
# ---------------------------------------------------------------------------
if runway_layer is None:
    raise Exception("No Runway Layer Centerline provided. Please select a Runway Layer Centerline from the UI.")

if use_runway_selected:
    selection = runway_layer.selectedFeatures()
    if not selection:
        raise Exception("No runway features selected. Please select runway features.")
else:
    selection = list(runway_layer.getFeatures())
    if not selection:
        raise Exception("No features found in Runway Layer Centerline.")

# ---------------------------------------------------------------------------
# Memory layer — Lower + Upper section, both runway ends, all in one layer
# ---------------------------------------------------------------------------
layer_name = "NewOLS_OES_StraightInApproach"
v_layer = QgsVectorLayer(f"PolygonZ?crs={map_srid}", layer_name, "memory")
v_layer_provider = v_layer.dataProvider()
v_layer_provider.addAttributes([
    QgsField("surface_type", QVariant.String),
    QgsField("component", QVariant.String),
    QgsField("height_m", QVariant.Double),
    QgsField("aerodrome_elevation_m", QVariant.Double),
    QgsField("rule_set", QVariant.String),
])
v_layer.updateFields()

_active_rule_set = globals().get('active_rule_set', None)
_params_json = build_parameters_json('New OLS OES Surface for Straight-in Instrument Approaches', {
    'aerodrome_elevation_m': round(aerodrome_elevation_m, 3),
    'direction': direction,
    'dimensions': dims,
    'rule_set': _active_rule_set,
})
add_parameters_field(v_layer)

features = []


def _add_feature(component, height_m, polygon_geometry):
    f = QgsFeature()
    f.setGeometry(polygon_geometry)
    f.setAttributes([
        "Surface for Straight-in Instrument Approaches", component, height_m,
        aerodrome_elevation_m, _active_rule_set, _params_json,
    ])
    features.append(f)


for feat in selection:
    line_pts = _normalize_polyline_points(feat.geometry())
    start_point = QgsPoint(line_pts[0].x(), line_pts[0].y())
    end_point = QgsPoint(line_pts[-1].x(), line_pts[-1].y())
    angle0 = start_point.azimuth(end_point) + 180
    if angle0 >= 360:
        angle0 -= 360
    if direction == -1:
        angle0 = (angle0 + 180) % 360
    back_angle0 = (angle0 + 180) % 360

    lower_z = aerodrome_elevation_m + dims['lower_section']['height_m']
    upper_z = aerodrome_elevation_m + dims['upper_section']['height_m']

    lower_ring_xy = _racetrack_ring_xy(
        start_point, end_point, angle0, back_angle0, dims['lower_section']['length_m'], trto, trfm)
    lower_disc_geom = _ring_polygon_2d(lower_ring_xy)
    lower_ext_pts = [
        QgsPoint(x, y, z) for x, y, z in flatten_ring_z(lower_ring_xy, lower_z)
    ]
    _add_feature('lower_section', dims['lower_section']['height_m'],
                 QgsGeometry(QgsPolygon(QgsLineString(lower_ext_pts))))

    upper_ring_xy = _rectangle_ring_xy(
        start_point, end_point, angle0, back_angle0,
        dims['upper_section']['shorter_side_m'] / 2.0,
        dims['upper_section']['longer_side_from_threshold_m'],
    )
    upper_disc_geom = _ring_polygon_2d(upper_ring_xy)
    upper_polygon_geometry = difference_flat(
        upper_disc_geom, lower_disc_geom, exterior_z=upper_z, interior_z=upper_z
    )
    _add_feature('upper_section', dims['upper_section']['height_m'], upper_polygon_geometry)

    print(
        f"NewOLS_OES_StraightInApproach: lower radius={dims['lower_section']['length_m']}m "
        f"height={dims['lower_section']['height_m']}m -> Z={lower_z}m; "
        f"upper height={dims['upper_section']['height_m']}m -> Z={upper_z}m"
    )

v_layer_provider.addFeatures(features)
v_layer.updateExtents()
print(f"NewOLS_OES_StraightInApproach: Created {len(features)} feature(s)")

register_parameters_action(v_layer)

QgsProject.instance().addMapLayers([v_layer])

symbol = QgsFillSymbol.createSimple({
    'color': '138,43,226,90',  # blueviolet, transparent
    'style': 'solid',
    'outline_color': '106,27,176,220',
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
    "New OLS OES Surface for Straight-in Instrument Approaches calculated successfully",
    level=MSG_SUCCESS,
)

_script_success = True

for _g in set(globals().keys()).difference(myglobals):
    if _g not in ('myglobals', '_script_success'):
        del globals()[_g]
