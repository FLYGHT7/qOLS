'''
Inner Approach Surface 4 CAT I
Procedure to be used in Projected Coordinate System Only
ENHANCED VERSION - Uses dynamic parameters from UI
ROBUST VERSION - No fallbacks, explicit layer and feature selection required
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
    code = globals().get('code', 4)
    rwyClassification = globals().get('rwyClassification', 'Precision Approach CAT I')
    widthApp = globals().get('widthApp', 280)
    Z0 = globals().get('Z0', 21.7)
    ZE = globals().get('ZE', 21.7)
    ARPH = globals().get('ARPH', 29.3)
    L1 = globals().get('L1', 3000)
    L2 = globals().get('L2', 3600)
    LH = globals().get('LH', 8400)
    
    # Direction parameter
    s = globals().get('direction', 0)  # 0 for start to end, -1 for end to start
    
    # Layer parameters
    runway_layer = globals().get('runway_layer', None)
    threshold_layer = globals().get('threshold_layer', None)
    use_selected_feature = globals().get('use_selected_feature', True)
    
    print(f"QOLS: Using parameters - code: {code}, rwyClassification: {rwyClassification}, widthApp: {widthApp}, Z0: {Z0}, ZE: {ZE}")
    print(f"QOLS: Direction parameter s: {s}, Use selected: {use_selected_feature}")
    
except Exception as e:
    print(f"QOLS: Error getting parameters, using defaults: {e}")
    # Fallback to defaults if parameters not provided
    code = 4
    rwyClassification = 'Precision Approach CAT I'
    widthApp = 280
    Z0 = 21.7
    ZE = 21.7
    ARPH = 29.3
    L1 = 3000
    L2 = 3600
    LH = 8400
    s = 0  # This will be overridden by the direction parameter below
    runway_layer = None
    threshold_layer = None
    use_selected_feature = True

# Calculate derived parameters
ZIH = 45 + ARPH

print(f"QOLS: Final values - s: {s}, ZIH: {ZIH}")
print(f"QOLS: Direction interpretation - s={s} means {'End to Start' if s == -1 else 'Start to End'}")

map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()

# ENHANCED LAYER SELECTION - Use layers from UI
try:
    if runway_layer is not None:
        print(f"QOLS: Using runway layer from UI: {runway_layer.name()}")
        
        if use_selected_feature:
            # Require explicit feature selection
            selection = runway_layer.selectedFeatures()
            if not selection:
                raise Exception("No runway features selected. Please select runway features.")
            print(f"QOLS: Using {len(selection)} selected runway features")
        else:
            # Use all features (take first one)
            selection = list(runway_layer.getFeatures())
            if not selection:
                raise Exception("No features found in runway layer.")
            print(f"QOLS: Using first feature from layer (selection disabled)")
        
        print(f"QOLS: Processing {len(selection)} runway features")
        rwy_geom = selection[0].geometry()
        rwy_length = rwy_geom.length()
        rwy_slope = (Z0-ZE)/rwy_length if rwy_length > 0 else 0
        
        print(f"QOLS: Runway length: {rwy_length}, slope: {rwy_slope}")
        
    else:
        # No fallback - require explicit runway layer selection
        raise Exception("No runway layer provided. Please select a runway layer from the UI.")

except Exception as e:
    print(f"QOLS: Error with runway layer: {e}")
    iface.messageBar().pushMessage("QOLS Error", f"Runway layer error: {str(e)}", level=Qgis.Critical)
    raise

# Calculate ZIHs
ZIHs = ((Z0-((Z0-ZE)/rwy_length)*1800))
print(f"QOLS: ZIHs calculated: {ZIHs}")

# Get the azimuth of the line - SIMPLIFIED LOGIC
for feat in selection:
    geom = feat.geometry().asPolyline()
    print(f"QOLS: Geometry points count: {len(geom)}")
    
    # Always use the same points regardless of direction
    # Direction change is handled by azimuth rotation only
    start_point = QgsPoint(geom[0])   # Always first point
    end_point = QgsPoint(geom[-1])    # Always last point
    angle0 = start_point.azimuth(end_point)
    
    print(f"QOLS: Using consistent points regardless of direction")
    print(f"QOLS: start_point = geom[0] (first point)")
    print(f"QOLS: end_point = geom[-1] (last point)")
    print(f"QOLS: Start point: {start_point.x()}, {start_point.y()}")
    print(f"QOLS: End point: {end_point.x()}, {end_point.y()}")
    print(f"QOLS: Base azimuth (angle0): {angle0}")

# Initial true azimuth data - FIXED LOGIC FOR PROPER DIRECTION CHANGE
# Always use the same points but change the azimuth by exactly 180 degrees
if s == -1:
    # For reverse direction, use the opposite direction (180 degrees from normal)
    azimuth = angle0 + 180
    if azimuth >= 360:
        azimuth -= 360
    print(f"QOLS: REVERSE direction - using angle0 + 180 = {angle0} + 180 = {azimuth}")
else:
    # For normal direction, use the forward azimuth as-is
    azimuth = angle0
    print(f"QOLS: NORMAL direction - using angle0 = {azimuth}")

print(f"QOLS: Using direction s={s}")
print(f"QOLS: Base azimuth (angle0): {angle0}")
print(f"QOLS: Final azimuth: {azimuth}")
print(f"QOLS: Expected difference between directions: 180°")
print(f"QOLS: Direction interpretation - s={s} means {'End to Start' if s == -1 else 'Start to End'}")

# ENHANCED THRESHOLD SELECTION - Use threshold layer from UI
try:
    if threshold_layer is not None:
        print(f"QOLS: Using threshold layer from UI: {threshold_layer.name()}")
        
        if use_selected_feature:
            # Require explicit feature selection
            threshold_selection = threshold_layer.selectedFeatures()
            if not threshold_selection:
                raise Exception("No threshold features selected. Please select threshold features.")
            print(f"QOLS: Using {len(threshold_selection)} selected threshold features")
        else:
            # Use all features (take first one)
            threshold_selection = list(threshold_layer.getFeatures())
            if not threshold_selection:
                raise Exception("No features found in threshold layer.")
            print(f"QOLS: Using first threshold feature from layer (selection disabled)")
        
        print(f"QOLS: Processing {len(threshold_selection)} threshold features")
        
    else:
        # No fallback - require explicit threshold layer selection  
        raise Exception("No threshold layer provided. Please select a threshold layer from the UI.")

except Exception as e:
    print(f"QOLS: Error with threshold layer: {e}")
    iface.messageBar().pushMessage("QOLS Error", f"Threshold layer error: {str(e)}", level=Qgis.Critical)
    raise

# Get x,y from threshold - ORIGINAL LOGIC RESTORED
# Always use the selected threshold feature as-is, direction change is handled by azimuth only
if len(threshold_selection) >= 1:
    # Use the first (or only) threshold feature
    selected_threshold = threshold_selection[0]
    threshold_geom = selected_threshold.geometry().asPoint()
    print(f"QOLS: Using threshold feature as-is (original logic)")
else:
    raise Exception("No threshold features found")

new_geom = QgsPoint(threshold_geom)
new_geom.addZValue(Z0)

print(f"QOLS: Threshold point: {new_geom.x()}, {new_geom.y()}, {new_geom.z()}")
print(f"QOLS: Direction change handled by azimuth rotation (180°), not threshold position")

list_pts = []

# Origin 
pt_0 = new_geom
    
# Distance prior from THR (60 m)
pt_01 = new_geom.project(60, azimuth)
pt_01.addZValue(Z0)
pt_01AL = pt_01.project(widthApp/2, azimuth+90)
pt_01AR = pt_01.project(widthApp/2, azimuth-90)

# First Section Points 
pt_05 = pt_01.project(3000, azimuth)
pt_05.setZ(Z0 + 3000*0.02)
pt_05L = pt_05.project(widthApp/2 + (3000*.15), azimuth+90)
pt_05R = pt_05.project(widthApp/2 + (3000*.15), azimuth-90)

list_pts.extend((pt_0, pt_01, pt_01AL, pt_01AR, pt_05, pt_05L, pt_05R))

# Second Section Points 
pt_06 = pt_01.project(6600, azimuth)
pt_06.setZ(Z0 + 3000*0.02 + 3600*0.025)
pt_06L = pt_06.project(widthApp/2 + (6600*.15), azimuth+90)
pt_06R = pt_06.project(widthApp/2 + (6600*.15), azimuth-90)

# Horizontal Section Points 
pt_07 = pt_01.project(15000, azimuth)
pt_07.setZ(Z0 + 3000*0.02 + 3600*0.025)
pt_07L = pt_07.project(widthApp/2 + (15000*.15), azimuth+90)
pt_07R = pt_07.project(widthApp/2 + (15000*.15), azimuth-90)

list_pts.extend((pt_06, pt_06L, pt_06R, pt_07, pt_07L, pt_07R))

print(f"QOLS: Generated {len(list_pts)} construction points")

# Creation of the Approach Surfaces
# Create memory layer
layer_name = f"RWY_ApproachSurface_{rwyClassification}_Code{code}"
v_layer = QgsVectorLayer("PolygonZ?crs="+map_srid, layer_name, "memory")
IDField = QgsField('ID', QVariant.String)
NameField = QgsField('SurfaceName', QVariant.String)
TypeField = QgsField('SurfaceType', QVariant.String)
CodeField = QgsField('Code', QVariant.Int)
v_layer.dataProvider().addAttributes([IDField, NameField, TypeField, CodeField])
v_layer.updateFields()

# Approach - First Section
SurfaceArea = [pt_05R, pt_05L, pt_01AL, pt_01AR]
pr = v_layer.dataProvider()
seg = QgsFeature()
seg.setGeometry(QgsPolygon(QgsLineString(SurfaceArea), rings=[]))
seg.setAttributes([6, 'Approach First Section', rwyClassification, code])
pr.addFeatures([seg])

# Approach - Second Section
SurfaceArea = [pt_06R, pt_06L, pt_05L, pt_05R]
pr = v_layer.dataProvider()
seg = QgsFeature()
seg.setGeometry(QgsPolygon(QgsLineString(SurfaceArea), rings=[]))
seg.setAttributes([7, 'Approach Second Section', rwyClassification, code])
pr.addFeatures([seg])

# Approach - Horizontal Section
SurfaceArea = [pt_07R, pt_07L, pt_06L, pt_06R]
pr = v_layer.dataProvider()
seg = QgsFeature()
seg.setGeometry(QgsPolygon(QgsLineString(SurfaceArea), rings=[]))
seg.setAttributes([8, 'Approach Horizontal Section', rwyClassification, code])
pr.addFeatures([seg])

# Load PolygonZ Layer to map canvas 
QgsProject.instance().addMapLayers([v_layer])

# Change style of layer 
v_layer.renderer().symbol().setColor(QColor("green"))
v_layer.renderer().symbol().setOpacity(0.4)
v_layer.triggerRepaint()

# Zoom to layer
v_layer.selectAll()
canvas = iface.mapCanvas()
canvas.zoomToSelected(v_layer)
v_layer.removeSelection()

# Clean up selections only if they weren't originally selected
# This prevents losing user selections for subsequent calculations
if not use_selected_feature:
    # Only clean up if we're not using selected features
    if runway_layer:
        runway_layer.removeSelection()
    if threshold_layer:
        threshold_layer.removeSelection()
else:
    # Keep selections for next calculation
    print("QOLS: Keeping feature selections for next calculation")

# Get canvas scale
sc = canvas.scale()
print(f"QOLS: Canvas scale: {sc}")
if sc < 20000:
    sc = 20000
canvas.zoomScale(sc)

print(f"QOLS: Approach surface calculation completed successfully")
print(f"QOLS: Created layer: {layer_name}")
print(f"QOLS: Surface type: {rwyClassification}, Code: {code}, Width: {widthApp}m")

# Success message
iface.messageBar().pushMessage("QOLS Success", f"Approach Surface ({rwyClassification}, Code {code}) calculated successfully", level=Qgis.Success)

# Clean up globals
set(globals().keys()).difference(myglobals)
for g in set(globals().keys()).difference(myglobals):
    if g != 'myglobals':
        del globals()[g]
