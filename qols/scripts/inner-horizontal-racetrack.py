'''
Inner Horizontal Racetrack Surface - PolygonZ Implementation
Issue #12: Convert from LineString to 3D Polygon (PolygonZ)
Procedure to be used in Projected Coordinate System Only
ENHANCED VERSION - Creates unified 3D polygon instead of separate lines
'''
myglobals = set(globals().keys())
from qgis.core import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from qgis.gui import *
from qgis.PyQt.QtCore import QVariant
from math import *

# Parameters - FROM UI
try:
    # Inner horizontal surface parameters from UI
    L = globals().get('radius', 4000)  # Distance L / Radius from UI
    height = globals().get('height', 45.0)  # Height for 3D polygon (new parameter)
    
    # Direction parameter
    s = globals().get('direction', 0)  # 0 for start to end, -1 for end to start
    
    # Layer parameters
    runway_layer = globals().get('runway_layer', None)
    threshold_layer = globals().get('threshold_layer', None)
    use_selected_feature = globals().get('use_selected_feature', True)
    
    print(f"InnerHorizontal: Using parameters - radius: {L}m, height: {height}m")
    print(f"InnerHorizontal: Direction parameter s: {s}, Use selected: {use_selected_feature}")
    
except Exception as e:
    print(f"InnerHorizontal: Error getting parameters, using defaults: {e}")
    # Fallback to defaults if parameters not provided
    L = 4000
    height = 45.0
    s = 0
    runway_layer = None
    threshold_layer = None
    use_selected_feature = True

print(f"InnerHorizontal: Final values - radius: {L}m, height: {height}m, direction: {s}")

map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()

# ENHANCED LAYER SELECTION - Use layers from UI
try:
    if runway_layer is not None:
        print(f"InnerHorizontal: Using runway layer from UI: {runway_layer.name()}")
        
        if use_selected_feature:
            selection = runway_layer.selectedFeatures()
            if not selection:
                raise Exception("No runway features selected. Please select runway features.")
            print(f"InnerHorizontal: Using {len(selection)} selected runway features")
        else:
            selection = list(runway_layer.getFeatures())
            if not selection:
                raise Exception("No features found in runway layer.")
            print(f"InnerHorizontal: Using first feature from layer")
        
        print(f"InnerHorizontal: Processing {len(selection)} runway features")
        
    else:
        raise Exception("No runway layer provided. Please select a runway layer from the UI.")
        
except Exception as e:
    print(f"InnerHorizontal: Error with runway layer: {e}")
    iface.messageBar().pushMessage("InnerHorizontal Error", f"Runway layer error: {str(e)}", level=Qgis.Critical)
    raise

# Create memory layer for 3D polygon (PolygonZ)
v_layer = QgsVectorLayer(f"PolygonZ?crs={map_srid}", "Inner Horizontal Surface", "memory")
v_layer_provider = v_layer.dataProvider()

# Add attributes for the polygon
v_layer_provider.addAttributes([
    QgsField("surface_type", QVariant.String),
    QgsField("radius_m", QVariant.Double),
    QgsField("height_m", QVariant.Double),
    QgsField("runway_start_x", QVariant.Double),
    QgsField("runway_start_y", QVariant.Double),
    QgsField("runway_end_x", QVariant.Double),
    QgsField("runway_end_y", QVariant.Double),
    QgsField("azimuth", QVariant.Double)
])
v_layer.updateFields()

features_created = 0

# Process each runway feature
for feat in selection:
    geom = feat.geometry().asPolyline()
    print(f"InnerHorizontal: Geometry points count: {len(geom)}")
    
    # Get runway endpoints
    start_point = QgsPoint(geom[0])   # Always first point
    end_point = QgsPoint(geom[-1])    # Always last point
    angle0 = start_point.azimuth(end_point)
    
    print(f"InnerHorizontal: Start point: {start_point.x()}, {start_point.y()}")
    print(f"InnerHorizontal: End point: {end_point.x()}, {end_point.y()}")
    print(f"InnerHorizontal: Base azimuth (angle0): {angle0}")

    # Calculate azimuth - corrected logic to match original
    base_azimuth = angle0 + 180
    if base_azimuth >= 360:
        base_azimuth -= 360

    # Apply direction change
    if s == -1:
        azimuth = base_azimuth + 180
        if azimuth >= 360:
            azimuth -= 360
        print(f"InnerHorizontal: REVERSE direction - final azimuth: {azimuth}")
    else:
        azimuth = base_azimuth
        print(f"InnerHorizontal: NORMAL direction - final azimuth: {azimuth}")

    # Set angle0 for calculations (same as original code)
    angle0 = azimuth
    
    back_angle0 = azimuth + 180
    if back_angle0 >= 360:
        back_angle0 -= 360

    # Calculate racetrack points using QgsPoint.project() - SAME AS ORIGINAL
    print(f"InnerHorizontal: Creating racetrack polygon with radius {L}m at height {height}m")
    
    # Start end projections using angle0 (same as original)
    x1_point = start_point.project(L, angle0 - 90)  # Left side start
    x2_point = start_point.project(L, angle0 + 90)  # Right side start
    xc_point = start_point.project(L, angle0)       # center point
    
    # End projections using back_angle0 (same as original)
    x4_point = end_point.project(L, back_angle0 + 90)   # Right side end
    x5_point = end_point.project(L, back_angle0)        # center point
    x6_point = end_point.project(L, back_angle0 - 90)   # Left side end

    print(f"InnerHorizontal: Calculated racetrack boundary points (including center points xc and x5)")

    # Create racetrack polygon using circular arcs at ends
    # We'll approximate the circular ends with multiple points for smooth curves
    
    polygon_points = []
    
    # Start with left side straight line
    polygon_points.append(QgsPoint(x1_point.x(), x1_point.y(), height))
    
    # Add circular arc at start (from x1 to x2 via center start_point)
    # Create multiple points along the arc for smooth curve
    num_arc_points = 18  # 10-degree intervals for 180-degree arc
    for i in range(1, num_arc_points):
        angle_offset = (i * 180.0 / num_arc_points) - 90  # -90 to +90 degrees
        arc_point = start_point.project(L, angle0 + angle_offset)
        polygon_points.append(QgsPoint(arc_point.x(), arc_point.y(), height))
    
    # Add right side point at start
    polygon_points.append(QgsPoint(x2_point.x(), x2_point.y(), height))
    
    # Add right side straight line to end
    polygon_points.append(QgsPoint(x4_point.x(), x4_point.y(), height))
    
    # Add circular arc at end (from x4 to x6 via center end_point)
    for i in range(1, num_arc_points):
        angle_offset = (i * 180.0 / num_arc_points) + 90  # +90 to +270 degrees (or -90)
        arc_point = end_point.project(L, back_angle0 + angle_offset)
        polygon_points.append(QgsPoint(arc_point.x(), arc_point.y(), height))
    
    # Add left side point at end
    polygon_points.append(QgsPoint(x6_point.x(), x6_point.y(), height))
    
    # Close the polygon by returning to start
    polygon_points.append(QgsPoint(x1_point.x(), x1_point.y(), height))
    
    print(f"InnerHorizontal: Created racetrack polygon with {len(polygon_points)} points")

    # Create 3D polygon geometry
    polygon_geometry = QgsGeometry.fromPolygonXY([polygon_points])
    
    # Create feature
    feature = QgsFeature()
    feature.setGeometry(polygon_geometry)
    feature.setAttributes([
        "Inner Horizontal",
        L,
        height,
        start_point.x(),
        start_point.y(),
        end_point.x(),
        end_point.y(),
        azimuth
    ])
    
    # Add feature to layer
    v_layer_provider.addFeatures([feature])
    features_created += 1
    
    print(f"InnerHorizontal: Created 3D racetrack polygon at height {height}m")

v_layer.updateExtents()
print(f"InnerHorizontal: Created {features_created} inner horizontal surface(s)")

# Add to map
QgsProject.instance().addMapLayers([v_layer])

# Style the layer for 3D polygon
symbol = QgsFillSymbol.createSimple({
    'color': '255,0,255,100',  # Magenta with transparency
    'style': 'solid',
    'outline_color': '255,0,255,255',
    'outline_style': 'solid',
    'outline_width': '0.7'
})
v_layer.renderer().setSymbol(symbol)
v_layer.triggerRepaint()

# Zoom to layer
if features_created > 0:
    v_layer.selectAll()
    canvas = iface.mapCanvas()
    canvas.zoomToSelected(v_layer)
    v_layer.removeSelection()
    
    # Set appropriate scale
    sc = canvas.scale()
    print(f"InnerHorizontal: Canvas scale: {sc}")
    if sc < 30000:
        sc = 30000
    canvas.zoomScale(sc)

# Clean up selections
if not use_selected_feature:
    if runway_layer:
        runway_layer.removeSelection()
else:
    print("InnerHorizontal: Keeping feature selections for next calculation")

print(f"InnerHorizontal: Inner Horizontal 3D surface calculation completed successfully")
print(f"InnerHorizontal: Radius: {L}m, Height: {height}m")

# Success message
iface.messageBar().pushMessage("QOLS Success", f"Inner Horizontal 3D Surface (R={L}m, H={height}m) calculated successfully", level=Qgis.Success)

# Clean up globals
for g in set(globals().keys()).difference(myglobals):
    if g != 'myglobals':
        del globals()[g]