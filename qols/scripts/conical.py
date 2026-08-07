'''
Conical Surface 
Procedure to be used in Projected Coordinate System Only
ENHANCED VERSION - Uses dynamic parameters from UI
RESTORED TO ORIGINAL WORKING CODE PATTERN
'''
# flake8: noqa  # exec()-dispatched script; star imports intentional (see TD-03)
myglobals = set(globals().keys())

from qgis.core import *
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.gui import *
from math import sqrt, cos, sin, radians
from qgis.utils import iface


def _normalize_polyline_points(geometry: 'QgsGeometry', iface=None):
    """Return a list of QgsPoint representing a single polyline.
    Accepts LineString or MultiLineString; for MultiLineString picks the longest part.
    """
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
                dx = pts[i].x() - pts[i-1].x()
                dy = pts[i].y() - pts[i-1].y()
                total += sqrt(dx*dx + dy*dy)
            return total
        longest = max(parts, key=length_of)
        if iface and len(parts) > 1:
            iface.messageBar().pushMessage("Conical Info", "MultiLineString detected; using longest part as centerline.", level=MSG_INFO)
        return [QgsPoint(p) for p in longest]
    poly = geometry.asPolyline()
    if poly and len(poly) >= 2:
        return [QgsPoint(p) for p in poly]
    raise Exception("Line geometry cannot be converted to a polyline. Only single line or curve types are permitted.")


# Parameters - NOW COME FROM UI INSTEAD OF HARDCODED
# These parameters will be injected by the plugin
try:
    # Try to get parameters from plugin namespace
    # Conical surface parameters from UI
    L = globals().get('radius', 6000)  # Distance L / Radius from UI
    height = globals().get('height', 60.0)  # Height for 3D polygon (new parameter)
    datum_elevation = globals().get('datum_elevation', 0.0)  # Reference elevation (#125)
    inner_height = globals().get('inner_height', 0.0)  # Inner Horizontal's own height (#125)
    slope_pct = globals().get('slope', 5.0)  # Conical slope, percent (#126)
    inner_radius = globals().get('inner_radius', 0.0)  # Inner Horizontal's own radius (#126)
    contour_interval_m = int(globals().get('contour_interval_m', 0))  # #126
    runway_code = globals().get('code', 4)
    rwy_classification = globals().get('rwyClassification', 'Precision Approach CAT I')

    # Direction parameter
    s = globals().get('direction', 0)  # 0 for start to end, -1 for end to start

    # Layer parameters
    runway_layer = globals().get('runway_layer', None)
    threshold_layer = globals().get('threshold_layer', None)
    use_runway_selected = globals().get('use_runway_selected', True)

    print(f"Conical: Using parameters - radius: {L}m, height: {height}m, code: {runway_code}, class: {rwy_classification}")
    print(f"Conical: Direction parameter s: {s}, Use selected: {use_runway_selected}")

except Exception as e:
    print(f"Conical: Error getting parameters, using defaults: {e}")
    # Fallback to defaults if parameters not provided
    L = 6000
    height = 60.0
    datum_elevation = 0.0
    inner_height = 0.0
    slope_pct = 5.0
    inner_radius = 0.0
    contour_interval_m = 0
    s = 0
    runway_layer = None
    threshold_layer = None
    use_runway_selected = True
    runway_code = 4
    rwy_classification = 'Precision Approach CAT I'

print(f"Conical: Final values - radius: {L}m, height: {height}m, direction: {s}")
print(f"Conical: Direction interpretation - s={s} means {'End to Start' if s == -1 else 'Start to End'}")

# Absolute elevation of Conical's outer (top) edge above the shared datum
# (#125) — the inner edge (after #124's trim) instead sits at bottom_z,
# applied later by plugin.py::_trim_conical_to_ring. Also used directly
# here for the contour block (#126), since contours run on this script's
# own un-trimmed geometry.
bottom_z = datum_elevation + inner_height
z_top = datum_elevation + inner_height + height
print(f"Conical: Datum elevation: {datum_elevation}m, Inner Horizontal height: {inner_height}m, top Z: {z_top}m")

map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()

# Work exclusively in projected coordinate system - no transformations needed

# ENHANCED LAYER SELECTION - Use layers from UI
try:
    if runway_layer is not None:
        print(f"Conical: Using Runway Layer Centerline from UI: {runway_layer.name()}")

        if use_runway_selected:
            # Require explicit feature selection
            selection = runway_layer.selectedFeatures()
            if not selection:
                raise Exception("No runway features selected. Please select runway features.")
            print(f"Conical: Using {len(selection)} selected runway features")
        else:
            # Use all features (take first one)
            selection = list(runway_layer.getFeatures())
            if not selection:
                raise Exception("No features found in Runway Layer Centerline.")
            print(f"Conical: Using first feature from layer (selection disabled)")

        print(f"Conical: Processing {len(selection)} runway features")

    else:
        # No fallback - require explicit Runway Layer Centerline selection
        raise Exception("No Runway Layer Centerline provided. Please select a Runway Layer Centerline from the UI.")

except Exception as e:
    print(f"Conical: Error with Runway Layer Centerline: {e}")
    iface.messageBar().pushMessage("Conical Error", f"Runway Layer Centerline error: {str(e)}", level=MSG_CRITICAL)
    raise

# Get the azimuth of the line - USING ORIGINAL CALCULATION LOGIC
for feat in selection:
    line_pts = _normalize_polyline_points(feat.geometry(), iface)
    print(f"Conical: Geometry points count (normalized): {len(line_pts)}")

    # Use original logic - always first to last point
    start_point = QgsPoint(line_pts[0].x(), line_pts[0].y())
    end_point = QgsPoint(line_pts[-1].x(), line_pts[-1].y())

    # Apply direction logic BEFORE calculating azimuth (like original)
    if s == -1:
        # Reverse direction: swap start and end points (matches original behavior)
        start_point, end_point = end_point, start_point
        print(f"Conical: REVERSE direction applied - swapped start/end points")

    # Original azimuth calculation
    angle0 = start_point.azimuth(end_point) + 180
    back_angle0 = angle0 + 180

    print(f"Conical: Using original calculation logic")
    print(f"Conical: Start point: {start_point.x()}, {start_point.y()}")
    print(f"Conical: End point: {end_point.x()}, {end_point.y()}")
    print(f"Conical: angle0: {angle0}, back_angle0: {back_angle0}")

# ORIGINAL CALCULATION LOGIC - Keep exactly as in working script
# transformation - exactly as original
source_crs = QgsCoordinateReferenceSystem(4326)
dest_crs = QgsCoordinateReferenceSystem(map_srid)
# transformto
trto = QgsCoordinateTransform(source_crs, dest_crs,QgsProject.instance())
# transformfrom
trfm = QgsCoordinateTransform(dest_crs,source_crs ,QgsProject.instance())

# Original coord function - EXACTLY as original


def coord(angle0,dist1,off):
    dist=dist1
    bearing = angle0+off
    angle = 90 - bearing
    bearing = math.radians(bearing)
    angle = math.radians(angle)
    dist_x, dist_y = \
        (dist * math.cos(angle), dist * math.sin(angle))
    xfinal, yfinal = (start_point.x() + dist_x, start_point.y() + dist_y)

    pro_coords = trto.transform(trfm.transform(xfinal,yfinal))
    return pro_coords


# Original coord2 function - EXACTLY as original


def coord2(angle0,dist1,off):
    dist=dist1
    bearing = angle0+off
    angle = 90 - bearing
    bearing = math.radians(bearing)
    angle = math.radians(angle)
    dist_x, dist_y = \
        (dist * math.cos(angle), dist * math.sin(angle))
    xfinal, yfinal = (end_point.x() + dist_x, end_point.y() + dist_y)

    pro_coords2 = trto.transform(trfm.transform(xfinal,yfinal))
    return pro_coords2


def _build_ring_points(radius):
    """Build the closed (x, y) racetrack boundary at the given radius —
    same circular-arc construction as the base Conical polygon, reused
    at intermediate radii for contour rings (#126)."""
    pro_coords = coord(angle0, radius, -90)
    x2 = coord(angle0, radius, 90)
    xc = coord(angle0, radius, 0)
    x4 = coord2(back_angle0, radius, 90)
    x5 = coord2(back_angle0, radius, 0)
    x6 = coord2(back_angle0, radius, -90)

    points = []

    # First arc: pro_coords → xc → x2
    cString1 = QgsCircularString()
    cString1.setPoints([QgsPoint(pro_coords[0], pro_coords[1]),
                        QgsPoint(xc[0], xc[1]),
                        QgsPoint(x2[0], x2[1])])
    geom1 = QgsGeometry(cString1)
    segmented1 = geom1.convertToType(QgsWkbTypes.LineGeometry, True)
    if segmented1 and segmented1.wkbType() == QgsWkbTypes.LineString:
        for point in segmented1.asPolyline():
            points.append((point.x(), point.y()))
    elif segmented1 and segmented1.wkbType() == QgsWkbTypes.MultiLineString:
        for part in segmented1.asMultiPolyline():
            for point in part:
                points.append((point.x(), point.y()))
    else:
        points.extend([(pro_coords[0], pro_coords[1]), (xc[0], xc[1]), (x2[0], x2[1])])

    # Line: x2 → x6 (connect arc endpoints)
    points.append((x6[0], x6[1]))

    # Second arc: x6 → x5 → x4 (REVERSED)
    cString2 = QgsCircularString()
    cString2.setPoints([QgsPoint(x6[0], x6[1]),
                        QgsPoint(x5[0], x5[1]),
                        QgsPoint(x4[0], x4[1])])
    geom2 = QgsGeometry(cString2)
    segmented2 = geom2.convertToType(QgsWkbTypes.LineGeometry, True)
    if segmented2 and segmented2.wkbType() == QgsWkbTypes.LineString:
        for i, point in enumerate(segmented2.asPolyline()):
            if i == 0:  # Same as x6, already added
                continue
            points.append((point.x(), point.y()))
    elif segmented2 and segmented2.wkbType() == QgsWkbTypes.MultiLineString:
        for part_idx, part in enumerate(segmented2.asMultiPolyline()):
            for point_idx, point in enumerate(part):
                if part_idx == 0 and point_idx == 0:
                    continue
                points.append((point.x(), point.y()))
    else:
        points.extend([(x5[0], x5[1]), (x4[0], x4[1])])

    # Line: x4 → pro_coords (close polygon)
    points.append((pro_coords[0], pro_coords[1]))

    return points


print(f"Conical: Using original coordinate calculation methods - trigonometry + transformations")

# Create memory layer for 3D polygon (PolygonZ) instead of separate LineStrings
layer_name = f"Conical_{rwy_classification}_Code{runway_code}"
v_layer = QgsVectorLayer(f"PolygonZ?crs={map_srid}", layer_name, "memory")
v_layer_provider = v_layer.dataProvider()

# Add attributes for the polygon
v_layer_provider.addAttributes([
    QgsField("surface_type", QVariant.String),
    QgsField("radius_m", QVariant.Double),
    QgsField("height_m", QVariant.Double),
    QgsField("datum_elevation_m", QVariant.Double),
    QgsField("inner_height_m", QVariant.Double),
    QgsField("rule_set", QVariant.String),
    QgsField("runway_start_x", QVariant.Double),
    QgsField("runway_start_y", QVariant.Double),
    QgsField("runway_end_x", QVariant.Double),
    QgsField("runway_end_y", QVariant.Double),
    QgsField("azimuth", QVariant.Double),
    QgsField("RWYType", QVariant.String),
    QgsField("Code", QVariant.Int)
])
v_layer.updateFields()

# Store the full input parameter set as HTML-inspectable JSON (#118)
from qols.parameters_inspector import build_parameters_json, add_parameters_field, register_parameters_action

_active_rule_set = globals().get('active_rule_set', None)
_params_json = build_parameters_json('Conical Surface', {
    'radius_m': L,
    'height_m': height,
    'datum_elevation_m': datum_elevation,
    'inner_height_m': inner_height,
    'rule_set': _active_rule_set,
    'azimuth': angle0,
    'rwy_classification': rwy_classification,
    'runway_code': int(runway_code),
})
add_parameters_field(v_layer)

print(f"Conical: Creating unified 3D surface with radius {L}m at height {height}m")

print(f"Conical: Using QGIS CircularString interpolation to generate polygon points")
print(f"Conical: CORRECTED sequence to avoid line crossings:")
print(f"Conical: 1. Arc 1: pro_coords → xc → x2")
print(f"Conical: 2. Line: x2 → x6 (connect arc endpoints)")
print(f"Conical: 3. Arc 2: x6 → x5 → x4 (REVERSED)")
print(f"Conical: 4. Line: x4 → pro_coords (close polygon)")

polygon_points = [QgsPoint(x, y, z_top) for x, y in _build_ring_points(L)]

print(f"Conical: Created surface with proper circular arcs using QGIS interpolation")
print(f"Conical: Total points in polygon: {len(polygon_points)}")
print(f"Conical: Point sequence: pro_coords → arc1 → x2 → x6 → arc2 → x4 → pro_coords")
print(f"Conical: This avoids crossing diagonal lines")

# Create 3D polygon geometry using WKT for proper PolygonZ
# Convert points to WKT format with Z coordinates
wkt_points = []
for pt in polygon_points:
    wkt_points.append(f"{pt.x()} {pt.y()} {pt.z()}")

# Create WKT string for PolygonZ
wkt_polygon = f"POLYGONZ(({', '.join(wkt_points)}))"
polygon_geometry = QgsGeometry.fromWkt(wkt_polygon)

print(f"Conical: Created true 3D PolygonZ geometry with Z coordinates")

# Create feature
feature = QgsFeature()
feature.setGeometry(polygon_geometry)
feature.setAttributes([
    "Conical",
    L,
    height,
    datum_elevation,
    inner_height,
    _active_rule_set,
    start_point.x(),
    start_point.y(),
    end_point.x(),
    end_point.y(),
    angle0,
    rwy_classification,
    int(runway_code),
    _params_json,
])

# Add feature to layer
v_layer_provider.addFeatures([feature])

v_layer.updateExtents()
print(f"Conical: Created conical 3D surface")

register_parameters_action(v_layer)

# Add to map
QgsProject.instance().addMapLayers([v_layer])

# Style the layer for 3D polygon (orange like original)
symbol = QgsFillSymbol.createSimple({
    'color': '255,165,0,100',  # Orange with transparency
    'style': 'solid',
    'outline_color': '255,165,0,255',
    'outline_style': 'solid',
    'outline_width': '0.7'
})
v_layer.renderer().setSymbol(symbol)
v_layer.triggerRepaint()

print(f"Conical: Applied orange style to conical 3D surface")

# Zoom to layer
v_layer.selectAll()
canvas = iface.mapCanvas()
canvas.zoomToSelected(v_layer)
v_layer.removeSelection()

# Clean up selections only if they weren't originally selected
if not use_runway_selected:
    # Only clean up if we're not using selected features
    if runway_layer:
        runway_layer.removeSelection()
else:
    # Keep selections for next calculation
    print("Conical: Keeping feature selections for next calculation")

# get canvas scale
sc = canvas.scale()
print(f"Conical: Canvas scale: {sc}")
if sc < 30000:
   sc=30000
canvas.zoomScale(sc)

print(f"Conical: Conical 3D surface calculation completed successfully")
print(f"Conical: Radius: {L}m, Height: {height}m")

# Success message
iface.messageBar().pushMessage("QOLS Success", f"Conical 3D Surface (R={L}m, H={height}m) calculated successfully", level=MSG_SUCCESS)

# -----------------------------------------------------------------------
# Contour layer (#126 — stepped elevation rings for Conical Surface)
#
# Unlike Approach/Take-off/Transitional, Conical's elevation varies
# purely with radial distance from the runway spine, not along its
# length — a real iso-elevation contour is the racetrack boundary curve
# traced at the radius where the cone reaches that elevation: a full
# closed ring, not a chord across the surface.
# -----------------------------------------------------------------------
if contour_interval_m > 0 and slope_pct > 0:
    import importlib.util as _ilu
    import os as _os
    import sys as _sys
    _utils_path = _os.path.join(_os.path.dirname(__file__), '_contour_utils.py')
    _cu_spec = _ilu.spec_from_file_location('_contour_utils', _utils_path)
    _cu = _ilu.module_from_spec(_cu_spec)
    _sys.modules['_contour_utils'] = _cu
    _cu_spec.loader.exec_module(_cu)

    _slope_decimal = slope_pct / 100.0
    _elevs = _cu.contour_elevations(bottom_z, z_top, contour_interval_m)
    # Exclude the outer edge itself - it's the surface's own already-drawn
    # boundary (same exclusion Transitional applies to its plateau ZIH).
    _elevs = [e for e in _elevs if e < z_top - 1e-6]

    _cfeats = []
    for _i, _elev in enumerate(_elevs):
        _radius = _cu.conical_contour_radius(_elev, bottom_z, inner_radius, _slope_decimal)
        _ring_xy = _build_ring_points(_radius)
        _ring_pts = [QgsPoint(x, y, _elev) for x, y in _ring_xy]
        _ring_pts.append(_ring_pts[0])  # close the ring
        _cfeat = QgsFeature()
        _cfeat.setGeometry(QgsGeometry(QgsLineString(_ring_pts)))
        _cfeat.setAttributes([_i + 1, _elev])
        _cfeats.append(_cfeat)

    if _cfeats:
        _clayer = QgsVectorLayer(
            "LineStringZ?crs=" + map_srid, "RWY_ConicalSurface_Contours", "memory")
        _clayer.dataProvider().addAttributes([
            QgsField('ID', QVariant.Int),
            QgsField('surface_elevation', QVariant.Double),
        ])
        _clayer.updateFields()
        _clayer.dataProvider().addFeatures(_cfeats)

        # Conical's rings sit much closer together than Approach's/
        # Transitional's chords, so the default 10pt label is hard to
        # read (#126 feedback) — bump it up for this layer only.
        _cu.apply_contour_style(_clayer, __file__, label_font_size=16)
        QgsProject.instance().addMapLayers([_clayer])
        _clayer.triggerRepaint()
        print(f"Conical: Contour layer added - {len(_cfeats)} rings at "
              f"{contour_interval_m} m interval")
    else:
        print(f"Conical: No contour lines - no elevation levels in range "
              f"for interval {contour_interval_m} m")

# Clean up globals
for g in set(globals().keys()).difference(myglobals):
    if g not in ('myglobals', '_script_success'):
        del globals()[g]
