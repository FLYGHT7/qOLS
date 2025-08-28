'''
Conical Surface 
Procedure to be used in Projected Coordinate System Only
ENHANCED VERSION - Uses dynamic parameters from UI
RESTORED TO ORIGINAL WORKING CODE PATTERN
'''
myglobals = set(globals().keys())

from qgis.core import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from qgis.gui import *
from qgis.PyQt.QtCore import QVariant
from math import *

# Parameters - NOW COME FROM UI INSTEAD OF HARDCODED
# These parameters will be injected by the plugin
try:
    # Try to get parameters from plugin namespace
    # Conical surface parameters from UI
    L = globals().get('radius', 6000)  # Distance L / Radius from UI
    
    # Direction parameter
    s = globals().get('direction', 0)  # 0 for start to end, -1 for end to start
    
    # Layer parameters
    runway_layer = globals().get('runway_layer', None)
    threshold_layer = globals().get('threshold_layer', None)
    use_selected_feature = globals().get('use_selected_feature', True)
    
    print(f"Conical: Using parameters - radius: {L}m")
    print(f"Conical: Direction parameter s: {s}, Use selected: {use_selected_feature}")
    
except Exception as e:
    print(f"Conical: Error getting parameters, using defaults: {e}")
    # Fallback to defaults if parameters not provided
    L = 6000
    s = 0
    runway_layer = None
    threshold_layer = None
    use_selected_feature = True

print(f"Conical: Final values - radius: {L}m, direction: {s}")
print(f"Conical: Direction interpretation - s={s} means {'End to Start' if s == -1 else 'Start to End'}")

map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()

# Work exclusively in projected coordinate system - no transformations needed

# ENHANCED LAYER SELECTION - Use layers from UI
try:
    if runway_layer is not None:
        print(f"Conical: Using runway layer from UI: {runway_layer.name()}")
        
        if use_selected_feature:
            # Require explicit feature selection
            selection = runway_layer.selectedFeatures()
            if not selection:
                raise Exception("No runway features selected. Please select runway features.")
            print(f"Conical: Using {len(selection)} selected runway features")
        else:
            # Use all features (take first one)
            selection = list(runway_layer.getFeatures())
            if not selection:
                raise Exception("No features found in runway layer.")
            print(f"Conical: Using first feature from layer (selection disabled)")
        
        print(f"Conical: Processing {len(selection)} runway features")
        
    else:
        # No fallback - require explicit runway layer selection
        raise Exception("No runway layer provided. Please select a runway layer from the UI.")
        
except Exception as e:
    print(f"Conical: Error with runway layer: {e}")
    iface.messageBar().pushMessage("Conical Error", f"Runway layer error: {str(e)}", level=Qgis.Critical)
    raise

# Get the azimuth of the line - USING ORIGINAL CALCULATION LOGIC
for feat in selection:
    geom = feat.geometry().asPolyline()
    print(f"Conical: Geometry points count: {len(geom)}")
    
    # Use original logic - always first to last point
    start_point = QgsPoint(geom[0])
    end_point = QgsPoint(geom[-1])
    
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
#transformation - exactly as original
source_crs = QgsCoordinateReferenceSystem(4326)
dest_crs = QgsCoordinateReferenceSystem(map_srid)
#transformto
trto = QgsCoordinateTransform(source_crs, dest_crs,QgsProject.instance())
#transformfrom
trfm = QgsCoordinateTransform(dest_crs,source_crs ,QgsProject.instance())

# routine 1 circling azimuth - EXACTLY as original
dist = L #Distance in NM
print(f"Conical: dist={dist}")
bearing = angle0 - 90
angle = 90 - bearing
print(f"Conical: bearing={bearing}, angle={angle}")
bearing = math.radians(bearing)
angle = math.radians(angle)
dist_x, dist_y = \
    (dist * math.cos(angle), dist * math.sin(angle))
xfinal, yfinal = (start_point.x() + dist_x, start_point.y() + dist_y)

pro_coords = trto.transform(trfm.transform(xfinal,yfinal))

start_coords = trfm.transform(start_point.x(),start_point.y())

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
    
x2 = coord(angle0,L,90)
xc = coord(angle0,L,0)
print(f"Conical: x2={x2}")

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
    
x4 = coord2(back_angle0,L,90)
x5 = coord2(back_angle0,L,0)
x6 = coord2(back_angle0,L,-90)
print(f"Conical: x4={x4}, x5={x5}, x6={x6}")

print(f"Conical: Using original coordinate calculation methods - trigonometry + transformations")

# Create memory layer
# create a new memory layer
line_start = QgsPoint(pro_coords[0],pro_coords[1])
line_end = QgsPoint(x4[0],x4[1])
line = QgsGeometry.fromPolyline([line_start,line_end])
v_layer = QgsVectorLayer("Linestring?crs="+map_srid, "Conical", "memory")
pr = v_layer.dataProvider()
# create a new feature
seg = QgsFeature()
# add the geometry to the feature, 
seg.setGeometry(QgsGeometry.fromPolyline([line_start, line_end]))
# ...it was here that you can add attributes, after having defined....
# add the geometry to the layer
pr.addFeatures( [ seg ] )
# update extent of the layer (not necessary)
v_layer.updateExtents()
# show the line  
QgsProject.instance().addMapLayers([v_layer])

# Join outer VOR splay 
line_start = QgsPoint(x6[0],x6[1])
line_end = QgsPoint(x2[0],x2[1])
line = QgsGeometry.fromPolyline([line_start,line_end])
pr = v_layer.dataProvider()
# create a new feature
seg = QgsFeature()
# add the geometry to the feature, 
seg.setGeometry(QgsGeometry.fromPolyline([line_start, line_end]))
# ...it was here that you can add attributes, after having defined....
# add the geometry to the layer
pr.addFeatures( [ seg ] )
# update extent of the layer (not necessary)
v_layer.updateExtents()
# show the line  
QgsProject.instance().addMapLayers([v_layer])

# Circular String
pr = v_layer.dataProvider()
cString = QgsCircularString()
#cString.fromTwoPointsAndCenter((QgsPoint(pro_coords[0],pro_coords[1]),QgsPoint(x2[0],x2[1]),QgsPoint(xc[0],xc[1]))
#construct 
cString.setPoints([QgsPoint(pro_coords[0],pro_coords[1]),QgsPoint(xc[0],xc[1]),QgsPoint(x2[0],x2[1])])
# create a new feature
geom_cString=QgsGeometry(cString)
seg = QgsFeature()
# add the geometry to the feature, 
seg.setGeometry(geom_cString)
# ...it was here that you can add attributes, after having defined....
# add the geometry to the layer
pr.addFeatures( [ seg ] )
# update extent of the layer (not necessary)
v_layer.updateExtents()
# show the line  
QgsProject.instance().addMapLayers([v_layer])

# Circular String
pr = v_layer.dataProvider()
cString = QgsCircularString()
cString.setPoints([QgsPoint(x4[0],x4[1]),QgsPoint(x5[0],x5[1]),QgsPoint(x6[0],x6[1])])
# create a new feature
geom_cString=QgsGeometry(cString)
seg = QgsFeature()
# add the geometry to the feature, 
seg.setGeometry(geom_cString)
# ...it was here that you can add attributes, after having defined....
# add the geometry to the layer
pr.addFeatures( [ seg ] )
# update extent of the layer (not necessary)
v_layer.updateExtents()
# show the line  
QgsProject.instance().addMapLayers([v_layer])

# Change style of layer 
v_layer.renderer().symbol().setColor(QColor("orange"))
v_layer.renderer().symbol().setWidth(0.7)
v_layer.triggerRepaint()

print(f"Conical: Applied orange style to conical surface")

# Zoom to layer
v_layer.selectAll()
canvas = iface.mapCanvas()
canvas.zoomToSelected(v_layer)
v_layer.removeSelection()

# Clean up selections only if they weren't originally selected
if not use_selected_feature:
    # Only clean up if we're not using selected features
    if runway_layer:
        runway_layer.removeSelection()
else:
    # Keep selections for next calculation
    print("Conical: Keeping feature selections for next calculation")

#get canvas scale
sc = canvas.scale()
print(f"Conical: Canvas scale: {sc}")
if sc < 30000:
   sc=30000
canvas.zoomScale(sc)

print(f"Conical: Conical surface calculation completed successfully")
print(f"Conical: Radius: {L}m")

# Success message
iface.messageBar().pushMessage("QOLS Success", f"Conical Surface (R={L}m) calculated successfully", level=Qgis.Success)

# Clean up globals
set(globals().keys()).difference(myglobals)
for g in set(globals().keys()).difference(myglobals):
    if g != 'myglobals':
        del globals()[g]