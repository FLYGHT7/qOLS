'''
Inner Horizontal Racetrack Surface
Procedure to be used in Projected Coordinate System Only
ENHANCED VERSION - Uses dynamic parameters from UI
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
    # Inner horizontal surface parameters from UI
    L = globals().get('radius', 4000)  # Distance L / Radius from UI
    o1 = globals().get('offset_right', 0)  # Offset Right 
    o2 = globals().get('offset_left', 0)   # Offset Left
    
    # Direction parameter
    s = globals().get('direction', 0)  # 0 for start to end, -1 for end to start
    
    # Layer parameters
    runway_layer = globals().get('runway_layer', None)
    threshold_layer = globals().get('threshold_layer', None)
    use_selected_feature = globals().get('use_selected_feature', True)
    
    print(f"InnerHorizontal: Using parameters - radius: {L}m, offset_right: {o1}, offset_left: {o2}")
    print(f"InnerHorizontal: Direction parameter s: {s}, Use selected: {use_selected_feature}")
    
except Exception as e:
    print(f"InnerHorizontal: Error getting parameters, using defaults: {e}")
    # Fallback to defaults if parameters not provided
    L = 4000
    o1 = 0  # right offset
    o2 = 0  # left offset
    s = 0
    runway_layer = None
    threshold_layer = None
    use_selected_feature = True

print(f"InnerHorizontal: Final values - radius: {L}m, offset_right: {o1}, offset_left: {o2}, direction: {s}")
print(f"InnerHorizontal: Direction interpretation - s={s} means {'End to Start' if s == -1 else 'Start to End'}")

map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()

#transformation
source_crs = QgsCoordinateReferenceSystem(4326)
dest_crs = QgsCoordinateReferenceSystem(map_srid)
#transformto
trto = QgsCoordinateTransform(source_crs, dest_crs,QgsProject.instance())
#transformfrom
trfm = QgsCoordinateTransform(dest_crs,source_crs ,QgsProject.instance())

# ENHANCED LAYER SELECTION - Use layers from UI
try:
    if runway_layer is not None:
        print(f"InnerHorizontal: Using runway layer from UI: {runway_layer.name()}")
        
        if use_selected_feature:
            # Try to use selected features first
            selection = runway_layer.selectedFeatures()
            if not selection:
                print("InnerHorizontal: No features selected, using first feature from layer")
                # If no selection, use first feature
                selection = list(runway_layer.getFeatures())
                if not selection:
                    raise Exception("No features found in runway layer.")
            else:
                print(f"InnerHorizontal: Using {len(selection)} selected features")
        else:
            # Use all features (take first one)
            selection = list(runway_layer.getFeatures())
            if not selection:
                raise Exception("No features found in runway layer.")
            print(f"InnerHorizontal: Using first feature from layer (selection disabled)")
        
        print(f"InnerHorizontal: Processing {len(selection)} runway features")
        
    else:
        # Fallback to old method (search by name or active layer)
        print("InnerHorizontal: No runway layer provided, using active layer...")
        layer = iface.activeLayer()
        if layer is None:
            raise Exception("No active layer found. Please select a runway layer.")
        
        selection = layer.selectedFeatures()
        if not selection:
            # Use first feature if no selection
            selection = list(layer.getFeatures())
            if not selection:
                raise Exception("No features found in active layer.")
        
except Exception as e:
    print(f"InnerHorizontal: Error with runway layer: {e}")
    iface.messageBar().pushMessage("InnerHorizontal Error", f"Runway layer error: {str(e)}", level=Qgis.Critical)
    raise

# Get the azimuth of the line - CORRECTED LOGIC TO MATCH ORIGINAL
for feat in selection:
    geom = feat.geometry().asPolyline()
    print(f"InnerHorizontal: Geometry points count: {len(geom)}")
    
    # Always use the same points regardless of direction
    # Direction change is handled by azimuth rotation only
    start_point = QgsPoint(geom[0])   # Always first point
    end_point = QgsPoint(geom[-1])    # Always last point
    angle0 = start_point.azimuth(end_point)
    
    print(f"InnerHorizontal: Using consistent points regardless of direction")
    print(f"InnerHorizontal: Start point: {start_point.x()}, {start_point.y()}")
    print(f"InnerHorizontal: End point: {end_point.x()}, {end_point.y()}")
    print(f"InnerHorizontal: Base azimuth (angle0): {angle0}")

# Initial true azimuth data - CORRECTED TO MATCH ORIGINAL SCRIPT
# Original script always adds +180, so we need to match that behavior
base_azimuth = angle0 + 180  # This matches the original script behavior
if base_azimuth >= 360:
    base_azimuth -= 360

# Now apply direction change on top of the corrected base
if s == -1:
    # For reverse direction, add another 180 degrees
    azimuth = base_azimuth + 180
    if azimuth >= 360:
        azimuth -= 360
    print(f"InnerHorizontal: REVERSE direction - using (angle0 + 180) + 180 = {angle0} + 360 = {azimuth}")
else:
    # For normal direction, use the base azimuth (which already has +180)
    azimuth = base_azimuth
    print(f"InnerHorizontal: NORMAL direction - using angle0 + 180 = {angle0} + 180 = {azimuth}")

back_angle0 = azimuth + 180
if back_angle0 >= 360:
    back_angle0 -= 360

print(f"InnerHorizontal: Final azimuth: {azimuth}, back_angle0: {back_angle0}")

# Use corrected azimuth for calculations
angle0 = azimuth
    


# routine 1 circling azimuth
dist = L #Distance in NM
print (dist)
bearing =  angle0-90
angle =     90 - bearing
print (bearing,angle)
bearing = math.radians(bearing)
angle =   math.radians(angle)
dist_x, dist_y = \
    (dist * math.cos(angle), dist * math.sin(angle))
#print (dist_x, dist_y)
xfinal, yfinal = (start_point.x() + dist_x, start_point.y() + dist_y)
#print (xfinal, yfinal)

#pro_coords = trfm.transform(xfinal,yfinal)
pro_coords = trto.transform(trfm.transform(xfinal,yfinal))
#print (pro_coords)

start_coords = trfm.transform(start_point.x(),start_point.y())


def coord (angle0,dist1,off):
    dist=dist1
    #print (angle0)
    bearing =  angle0+off
    angle =     90 - bearing
    #print (bearing,angle)
    bearing = math.radians(bearing)
    angle =   math.radians(angle)
    dist_x, dist_y = \
        (dist * math.cos(angle), dist * math.sin(angle))
    #print (dist_x, dist_y)
    xfinal, yfinal = (start_point.x() + dist_x, start_point.y() + dist_y)
    #print (xfinal, yfinal)
    
    #pro_coords = trfm.transform(xfinal,yfinal)
    pro_coords = trto.transform(trfm.transform(xfinal,yfinal))
    return pro_coords
    
x2 = coord(angle0,L,90)
xc = coord(angle0,L,0)
print (x2)

def coord2 (angle0,dist1,off):
    dist=dist1
    #print (angle0)
    bearing =  angle0+off
    angle =     90 - bearing
    #print (bearing,angle)
    bearing = math.radians(bearing)
    angle =   math.radians(angle)
    dist_x, dist_y = \
        (dist * math.cos(angle), dist * math.sin(angle))
    #print (dist_x, dist_y)
    xfinal, yfinal = (end_point.x() + dist_x, end_point.y() + dist_y)
    #print (xfinal, yfinal)
    
    #pro_coords2 = trfm.transform(xfinal,yfinal)
    pro_coords2 = trto.transform(trfm.transform(xfinal,yfinal))
    return pro_coords2
    
x4 = coord2(back_angle0,L,90)
x5 = coord2(back_angle0,L,0)
x6 = coord2(back_angle0,L,-90)
print (x4,x5,x6)


#Create memory layer
# create a new memory layer
line_start = QgsPoint(pro_coords[0],pro_coords[1])
line_end = QgsPoint(x4[0],x4[1])
line = QgsGeometry.fromPolyline([line_start,line_end])
v_layer = QgsVectorLayer("Linestring?crs="+map_srid, "Inner Horizontal", "memory")
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
v_layer.renderer().symbol().setColor(QColor("magenta"))
v_layer.renderer().symbol().setWidth(0.7)
v_layer.triggerRepaint()

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
    print("InnerHorizontal: Keeping feature selections for next calculation")

#get canvas scale
sc = canvas.scale()
print(f"InnerHorizontal: Canvas scale: {sc}")
if sc < 30000:
   sc=30000
canvas.zoomScale(sc)

print(f"InnerHorizontal: Inner Horizontal surface calculation completed successfully")
print(f"InnerHorizontal: Radius: {L}m, Offset Right: {o1}, Offset Left: {o2}")

# Success message
iface.messageBar().pushMessage("QOLS Success", f"Inner Horizontal Surface (R={L}m, Offsets: R={o1}, L={o2}) calculated successfully", level=Qgis.Success)

# Clean up globals
set(globals().keys()).difference(myglobals)
for g in set(globals().keys()).difference(myglobals):
    if g != 'myglobals':
        del globals()[g]