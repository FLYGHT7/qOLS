"""
New OLS Concept — OES Horizontal Surface
ICAO Annex 14 Table 4-10 (Dimensions of horizontal surface), keyed by
Aeroplane Design Group (ADG). Selecting a higher ADG retains every lower
tier's ring too (see qols/surfaces/new_ols_horizontal.py), so 1-3
concentric racetrack rings — each at its own height above the aerodrome
elevation — are drawn into a single output layer.

Geometry construction mirrors qols/scripts/inner-horizontal-racetrack.py
exactly (same coord()/coord2() trig closures, same 2-arc/2-line closed
racetrack), just repeated once per ring instead of once total.

Procedure to be used in Projected Coordinate System Only.
"""
myglobals = set(globals().keys())

from qgis.core import *
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.gui import *
import math
from math import sqrt
from qols.parameters_inspector import build_parameters_json, add_parameters_field, register_parameters_action
from qols.surfaces.new_ols_horizontal import get_horizontal_surface_rings

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


def _racetrack_ring(start_point, end_point, angle0, back_angle0, radius, z_absolute, trto, trfm):
    """Builds one closed racetrack ring (list of WKT 'x y z' strings) at
    the given radius/Z, using the same coord()/coord2() trig + circular-arc
    interpolation as inner-horizontal-racetrack.py."""

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

    polygon_points = []

    def _append_arc(p1, p2, p3, skip_first):
        cstring = QgsCircularString()
        cstring.setPoints([QgsPoint(p1[0], p1[1]), QgsPoint(p2[0], p2[1]), QgsPoint(p3[0], p3[1])])
        segmented = QgsGeometry(cstring).convertToType(QgsWkbTypes.LineGeometry, True)
        pts = []
        if segmented:
            if segmented.wkbType() == QgsWkbTypes.LineString:
                pts = list(segmented.asPolyline())
            elif segmented.wkbType() == QgsWkbTypes.MultiLineString:
                for part in segmented.asMultiPolyline():
                    pts.extend(part)
        if not pts:
            pts = [QgsPointXY(p1[0], p1[1]), QgsPointXY(p2[0], p2[1]), QgsPointXY(p3[0], p3[1])]
        for i, pt in enumerate(pts):
            if skip_first and i == 0:
                continue
            polygon_points.append(QgsPoint(pt.x(), pt.y(), z_absolute))

    _append_arc(pro_coords, xc, x2, skip_first=False)
    polygon_points.append(QgsPoint(x6[0], x6[1], z_absolute))
    _append_arc(x6, x5, x4, skip_first=True)
    polygon_points.append(QgsPoint(pro_coords[0], pro_coords[1], z_absolute))

    return [f"{pt.x()} {pt.y()} {pt.z()}" for pt in polygon_points]


# ---------------------------------------------------------------------------
# Parameter extraction
# ---------------------------------------------------------------------------
try:
    adg = globals().get('adg', 'IIC')
    aerodrome_elevation_m = globals().get('aerodrome_elevation_m', 0.0)
    direction = globals().get('direction', 0)
    runway_layer = globals().get('runway_layer', None)
    use_runway_selected = globals().get('use_runway_selected', True)
except Exception as e:
    print(f"NewOLS_OES_Horizontal: Error getting parameters, using defaults: {e}")
    adg = 'IIC'
    aerodrome_elevation_m = 0.0
    direction = 0
    runway_layer = None
    use_runway_selected = True

rings = get_horizontal_surface_rings(adg)
print(f"NewOLS_OES_Horizontal: ADG={adg} -> {len(rings)} ring(s): {rings}")

map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()
source_crs = QgsCoordinateReferenceSystem(4326)
dest_crs = QgsCoordinateReferenceSystem(map_srid)
trto = QgsCoordinateTransform(source_crs, dest_crs, QgsProject.instance())
trfm = QgsCoordinateTransform(dest_crs, source_crs, QgsProject.instance())

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
# Memory layer — all rings for all runway features go into this one layer
# ---------------------------------------------------------------------------
layer_name = "NewOLS_OES_Horizontal"
v_layer = QgsVectorLayer(f"PolygonZ?crs={map_srid}", layer_name, "memory")
v_layer_provider = v_layer.dataProvider()
v_layer_provider.addAttributes([
    QgsField("surface_type", QVariant.String),
    QgsField("adg", QVariant.String),
    QgsField("radius_m", QVariant.Double),
    QgsField("height_m", QVariant.Double),
    QgsField("aerodrome_elevation_m", QVariant.Double),
    QgsField("rule_set", QVariant.String),
])
v_layer.updateFields()

_active_rule_set = globals().get('active_rule_set', None)
_params_json = build_parameters_json('New OLS OES Horizontal Surface', {
    'adg': adg,
    'aerodrome_elevation_m': round(aerodrome_elevation_m, 3),
    'rings': rings,
    'rule_set': _active_rule_set,
})
add_parameters_field(v_layer)

features = []
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

    # Draw largest ring first (bottom of the layer's render order) down to
    # smallest last (on top) — every smaller/nearer ring's own fill+outline
    # then stays visible on top of the larger ones instead of being covered
    # by them, matching Figure 4-4's clearly bounded concentric zones.
    for ring in reversed(rings):
        radius_m = ring['radius_m']
        height_m = ring['height_m']
        z_absolute = aerodrome_elevation_m + height_m

        wkt_points = _racetrack_ring(start_point, end_point, angle0, back_angle0, radius_m, z_absolute, trto, trfm)
        polygon_geometry = QgsGeometry.fromWkt(f"POLYGONZ(({', '.join(wkt_points)}))")

        feature = QgsFeature()
        feature.setGeometry(polygon_geometry)
        feature.setAttributes([
            "New OLS OES Horizontal",
            adg,
            radius_m,
            height_m,
            aerodrome_elevation_m,
            _active_rule_set,
            _params_json,
        ])
        features.append(feature)
        print(f"NewOLS_OES_Horizontal: Ring radius={radius_m}m height={height_m}m -> Z={z_absolute}m")

v_layer_provider.addFeatures(features)
v_layer.updateExtents()
print(f"NewOLS_OES_Horizontal: Created {len(features)} ring feature(s)")

register_parameters_action(v_layer)

QgsProject.instance().addMapLayers([v_layer])

symbol = QgsFillSymbol.createSimple({
    'color': '32,178,170,90',  # Light sea green / teal, transparent
    'style': 'solid',
    'outline_color': '32,178,170,220',
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
    f"New OLS OES Horizontal Surface (ADG {adg}, {len(rings)} ring(s)) calculated successfully",
    level=MSG_SUCCESS,
)

_script_success = True

for _g in set(globals().keys()).difference(myglobals):
    if _g not in ('myglobals', '_script_success'):
        del globals()[_g]
