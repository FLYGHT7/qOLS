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
    runway_code = globals().get('code', 4)
    rwy_classification = globals().get('rwyClassification', 'Precision Approach CAT I')
    
    # Direction parameter
    s = globals().get('direction', 0)  # 0 for start to end, -1 for end to start
    
    # Layer parameters
    runway_layer = globals().get('runway_layer', None)
    threshold_layer = globals().get('threshold_layer', None)
    use_selected_feature = globals().get('use_selected_feature', True)
    
    print(f"InnerHorizontal: Using parameters - radius: {L}m, height: {height}m, code: {runway_code}, class: {rwy_classification}")
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
    runway_code = 4
    rwy_classification = 'Precision Approach CAT I'

print(f"InnerHorizontal: Final values - radius: {L}m, height: {height}m, direction: {s}")

map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()

# Work exclusively in projected coordinate system - coordinate transformations
source_crs = QgsCoordinateReferenceSystem(4326)
dest_crs = QgsCoordinateReferenceSystem(map_srid)
# transformto
trto = QgsCoordinateTransform(source_crs, dest_crs, QgsProject.instance())
# transformfrom
trfm = QgsCoordinateTransform(dest_crs, source_crs, QgsProject.instance())

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
layer_name = f"InnerHorizontal_{rwy_classification}_Code{runway_code}"
v_layer = QgsVectorLayer(f"PolygonZ?crs={map_srid}", layer_name, "memory")
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
    QgsField("azimuth", QVariant.Double),
    QgsField("RWYType", QVariant.String),
    QgsField("Code", QVariant.Int)
])
v_layer.updateFields()

features_created = 0

# Process each runway feature
for feat in selection:
    geom = feat.geometry().asPolyline()
    print(f"InnerHorizontal: Geometry points count: {len(geom)}")
    
    # Get runway endpoints - convert QgsPointXY to QgsPoint
    start_point_xy = geom[0]
    end_point_xy = geom[-1]
    start_point = QgsPoint(start_point_xy.x(), start_point_xy.y())   # Always first point
    end_point = QgsPoint(end_point_xy.x(), end_point_xy.y())       # Always last point
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

    # Calculate racetrack points using ORIGINAL LOGIC - SAME AS CONICAL SURFACE
    print(f"InnerHorizontal: Creating racetrack polygon with radius {L}m at height {height}m")
    print(f"InnerHorizontal: Using same successful approach as conical surface")
    
    # Use ORIGINAL coordinate calculation methods from working script
    # Distance and bearing calculations (same as original inner horizontal)
    dist = L
    
    # Original coord function - same as conical surface pattern
    def coord(angle0, dist1, off):
        dist = dist1
        bearing = angle0 + off
        angle = 90 - bearing
        bearing = math.radians(bearing)
        angle = math.radians(angle)
        dist_x, dist_y = (dist * math.cos(angle), dist * math.sin(angle))
        xfinal, yfinal = (start_point.x() + dist_x, start_point.y() + dist_y)
        
        # Transform coordinates (same pattern as conical)
        pro_coords = trto.transform(trfm.transform(xfinal, yfinal))
        return pro_coords
    
    # Original coord2 function - same as conical surface pattern  
    def coord2(angle0, dist1, off):
        dist = dist1
        bearing = angle0 + off
        angle = 90 - bearing
        bearing = math.radians(bearing)
        angle = math.radians(angle)
        dist_x, dist_y = (dist * math.cos(angle), dist * math.sin(angle))
        xfinal, yfinal = (end_point.x() + dist_x, end_point.y() + dist_y)
        
        # Transform coordinates (same pattern as conical)
        pro_coords2 = trto.transform(trfm.transform(xfinal, yfinal))
        return pro_coords2
    
    # Calculate 6 key points exactly like conical surface
    pro_coords = coord(angle0, L, -90)  # Starting point left
    x2 = coord(angle0, L, 90)           # Starting point right  
    xc = coord(angle0, L, 0)            # Starting center point
    
    x4 = coord2(back_angle0, L, 90)     # Ending point right
    x5 = coord2(back_angle0, L, 0)      # Ending center point
    x6 = coord2(back_angle0, L, -90)    # Ending point left
    
    print(f"InnerHorizontal: Calculated 6 points using original trigonometry + transformations")
    print(f"InnerHorizontal: pro_coords: {pro_coords}, x2: {x2}, x4: {x4}, x6: {x6}")

    # SOLUTION: Use QGIS CircularString interpolation - SAME AS CONICAL SURFACE SUCCESS
    print(f"InnerHorizontal: Using QGIS CircularString interpolation for exact arcs")
    print(f"InnerHorizontal: CORRECTED sequence to avoid line crossings:")
    print(f"InnerHorizontal: 1. Arc 1: pro_coords → xc → x2")
    print(f"InnerHorizontal: 2. Line: x2 → x6 (connect arc endpoints)")
    print(f"InnerHorizontal: 3. Arc 2: x6 → x5 → x4 (REVERSED)")
    print(f"InnerHorizontal: 4. Line: x4 → pro_coords (close polygon)")
    
    polygon_points = []

    # First arc: Create CircularString and extract points  
    # This is exactly how the conical surface creates the first arc: [pro_coords, xc, x2]
    cString1 = QgsCircularString()
    cString1.setPoints([QgsPoint(pro_coords[0], pro_coords[1]), 
                        QgsPoint(xc[0], xc[1]), 
                        QgsPoint(x2[0], x2[1])])

    # Convert to regular geometry and extract points with high resolution
    geom1 = QgsGeometry(cString1)
    # Convert to segmented curve with many points for smooth polygon
    segmented1 = geom1.convertToType(QgsWkbTypes.LineGeometry, True)
    if segmented1:
        # Handle both LineString and MultiLineString cases
        if segmented1.wkbType() == QgsWkbTypes.LineString:
            polyline1 = segmented1.asPolyline()
            print(f"InnerHorizontal: Arc 1 interpolated to {len(polyline1)} points (LineString)")
            
            # Add arc points with height
            for point in polyline1:
                polygon_points.append(QgsPoint(point.x(), point.y(), height))
        elif segmented1.wkbType() == QgsWkbTypes.MultiLineString:
            multiline1 = segmented1.asMultiPolyline()
            print(f"InnerHorizontal: Arc 1 interpolated to {len(multiline1)} parts (MultiLineString)")
            
            # Add points from all parts
            for part in multiline1:
                for point in part:
                    polygon_points.append(QgsPoint(point.x(), point.y(), height))
        else:
            print(f"InnerHorizontal: Warning - Unexpected geometry type: {segmented1.wkbType()}")
            # Fallback to original points
            polygon_points.extend([
                QgsPoint(pro_coords[0], pro_coords[1], height),
                QgsPoint(xc[0], xc[1], height),
                QgsPoint(x2[0], x2[1], height)
            ])
    else:
        print("InnerHorizontal: Warning - Could not interpolate first arc, using original points")
        polygon_points.extend([
            QgsPoint(pro_coords[0], pro_coords[1], height),
            QgsPoint(xc[0], xc[1], height),
            QgsPoint(x2[0], x2[1], height)
        ])

    # Add straight line from x2 to x6 (connect arc endpoints, not diagonals)
    polygon_points.append(QgsPoint(x6[0], x6[1], height))

    # Second arc: Create CircularString and extract points  
    # This is exactly how the conical surface creates the second arc: [x6, x5, x4] (REVERSED)
    cString2 = QgsCircularString()
    cString2.setPoints([QgsPoint(x6[0], x6[1]), 
                        QgsPoint(x5[0], x5[1]), 
                        QgsPoint(x4[0], x4[1])])

    # Convert to regular geometry and extract points with high resolution
    geom2 = QgsGeometry(cString2)
    # Convert to segmented curve with many points for smooth polygon
    segmented2 = geom2.convertToType(QgsWkbTypes.LineGeometry, True)
    if segmented2:
        # Handle both LineString and MultiLineString cases
        if segmented2.wkbType() == QgsWkbTypes.LineString:
            polyline2 = segmented2.asPolyline()
            print(f"InnerHorizontal: Arc 2 interpolated to {len(polyline2)} points (LineString)")
            
            # Add arc points with height (skip first point to avoid duplication with x6)
            for i, point in enumerate(polyline2):
                if i == 0:  # Skip first point as it's the same as x6 we just added
                    continue
                polygon_points.append(QgsPoint(point.x(), point.y(), height))
        elif segmented2.wkbType() == QgsWkbTypes.MultiLineString:
            multiline2 = segmented2.asMultiPolyline()
            print(f"InnerHorizontal: Arc 2 interpolated to {len(multiline2)} parts (MultiLineString)")
            
            # Add points from all parts (skip first point of first part to avoid duplication with x6)
            for part_idx, part in enumerate(multiline2):
                for point_idx, point in enumerate(part):
                    if part_idx == 0 and point_idx == 0:  # Skip first point of first part (x6)
                        continue
                    polygon_points.append(QgsPoint(point.x(), point.y(), height))
        else:
            print(f"InnerHorizontal: Warning - Unexpected geometry type: {segmented2.wkbType()}")
            # Fallback to original points (reversed order: x5, x4)
            polygon_points.extend([
                QgsPoint(x5[0], x5[1], height),
                QgsPoint(x4[0], x4[1], height)
            ])
    else:
        print("InnerHorizontal: Warning - Could not interpolate second arc, using original points")
        polygon_points.extend([
            QgsPoint(x5[0], x5[1], height),
            QgsPoint(x4[0], x4[1], height)
        ])

    # Add straight line back to start (closing the polygon)
    polygon_points.append(QgsPoint(pro_coords[0], pro_coords[1], height))
    
    print(f"InnerHorizontal: Created racetrack surface with proper circular arcs using QGIS interpolation")
    print(f"InnerHorizontal: Total points in polygon: {len(polygon_points)}")
    print(f"InnerHorizontal: Point sequence: pro_coords → arc1 → x2 → x6 → arc2 → x4 → pro_coords")
    print(f"InnerHorizontal: This avoids crossing diagonal lines - SAME FIX AS CONICAL SURFACE")

    # Create 3D polygon geometry using WKT for proper PolygonZ
    # Convert points to WKT format with Z coordinates
    wkt_points = []
    for pt in polygon_points:
        wkt_points.append(f"{pt.x()} {pt.y()} {pt.z()}")
    
    # Create WKT string for PolygonZ
    wkt_polygon = f"POLYGONZ(({', '.join(wkt_points)}))"
    polygon_geometry = QgsGeometry.fromWkt(wkt_polygon)
    
    print(f"InnerHorizontal: Created true 3D PolygonZ geometry with Z coordinates")
    
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
        azimuth,
        rwy_classification,
        int(runway_code)
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