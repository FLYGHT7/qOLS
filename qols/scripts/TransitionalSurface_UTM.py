'''
Inner Approach Surface 4 CAT I
Procedure to be used in Projected Coordinate System Only
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
    typeAPP = globals().get('typeAPP', 'CAT I')
    widthApp = globals().get('widthApp', 280)
    Z0 = globals().get('Z0', 2548)
    ZE = globals().get('ZE', 2546.5)
    ARPH = globals().get('ARPH', 2548)
    IHSlope = globals().get('IHSlope', 33.3/100)
    L1 = globals().get('L1', 3000)
    L2 = globals().get('L2', 3600)
    LH = globals().get('LH', 8400)
    Tslope = globals().get('Tslope', 14.3/100)
    
    # Direction parameter
    s = globals().get('direction', 0)  # 0 for start to end, -1 for end to start
    
    # Layer parameters
    runway_layer = globals().get('runway_layer', None)
    threshold_layer = globals().get('threshold_layer', None)
    use_selected_feature = globals().get('use_selected_feature', True)
    
    print(f"TransitionalSurface: Using parameters - code: {code}, widthApp: {widthApp}, Z0: {Z0}, ZE: {ZE}")
    print(f"TransitionalSurface: Direction parameter s: {s}, Use selected: {use_selected_feature}")
    
except Exception as e:
    print(f"TransitionalSurface: Error getting parameters, using defaults: {e}")
    # Fallback to defaults if parameters not provided
    code = 4
    typeAPP = 'CAT I'
    widthApp = 280
    Z0 = 2548
    ZE = 2546.5
    ARPH = 2548
    IHSlope = 33.3/100
    L1 = 3000
    L2 = 3600
    LH = 8400
    Tslope = 14.3/100
    s = 0
    runway_layer = None
    threshold_layer = None
    use_selected_feature = True

# Calculate derived parameters
ZIH = 45 + ARPH

print(f"TransitionalSurface: Final values - s: {s}, ZIH: {ZIH}")
print(f"TransitionalSurface: Direction interpretation - s={s} means {'End to Start' if s == -1 else 'Start to End'}")

map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()

# ENHANCED LAYER SELECTION - Use layers from UI
try:
    if runway_layer is not None:
        print(f"TransitionalSurface: Using runway layer from UI: {runway_layer.name()}")
        
        if use_selected_feature:
            selection = runway_layer.selectedFeatures()
            if not selection:
                print("TransitionalSurface: No features selected, using first feature from layer")
                selection = list(runway_layer.getFeatures())
                if not selection:
                    raise Exception("No features found in runway layer.")
            else:
                print(f"TransitionalSurface: Using {len(selection)} selected features")
        else:
            selection = list(runway_layer.getFeatures())
            if not selection:
                raise Exception("No features found in runway layer.")
            print(f"TransitionalSurface: Using first feature from layer (selection disabled)")
        
        print(f"TransitionalSurface: Processing {len(selection)} runway features")
        rwy_geom = selection[0].geometry()
        rwy_length = rwy_geom.length()
        rwy_slope = (Z0-ZE)/rwy_length if rwy_length > 0 else 0
        
        print(f"TransitionalSurface: Runway length: {rwy_length}, slope: {rwy_slope}")
        
    else:
        # Fallback to old method (search by name)
        print("TransitionalSurface: No runway layer provided, searching by name...")
        for layer in QgsProject.instance().mapLayers().values():
            if "xrunway" in layer.name():
                runway_layer = layer
                selection = layer.selectedFeatures()
                if not selection:
                    selection = list(layer.getFeatures())
                    if not selection:
                        raise Exception("No features found in runway layer.")
                break
        
        if not runway_layer:
            raise Exception("No runway layer found. Please select a runway layer.")
        
        rwy_geom = selection[0].geometry()
        rwy_length = rwy_geom.length()
        rwy_slope = (Z0-ZE)/rwy_length if rwy_length > 0 else 0

except Exception as e:
    print(f"TransitionalSurface: Error with runway layer: {e}")
    iface.messageBar().pushMessage("TransitionalSurface Error", f"Runway layer error: {str(e)}", level=Qgis.Critical)
    raise

# Calculate ZIHs
ZIHs = ((Z0-((Z0-ZE)/rwy_length)*1800))
print(f"TransitionalSurface: ZIHs calculated: {ZIHs}")

        
#Get the azimuth of the line - SIMPLIFIED LOGIC
for feat in selection:
    geom = feat.geometry().asPolyline()
    print(f"TransitionalSurface: Geometry points count: {len(geom)}")
    
    # Always use the same points regardless of direction
    # Direction change is handled by azimuth rotation only
    start_point = QgsPoint(geom[0])   # Always first point
    end_point = QgsPoint(geom[-1])    # Always last point
    angle0 = start_point.azimuth(end_point)
    
    print(f"TransitionalSurface: Using consistent points regardless of direction")
    print(f"TransitionalSurface: Start point: {start_point.x()}, {start_point.y()}")
    print(f"TransitionalSurface: End point: {end_point.x()}, {end_point.y()}")
    print(f"TransitionalSurface: Base azimuth (angle0): {angle0}")

# Initial true azimuth data - FIXED LOGIC FOR PROPER DIRECTION CHANGE
if s == -1:
    azimuth = angle0 + 180
    if azimuth >= 360:
        azimuth -= 360
    print(f"TransitionalSurface: REVERSE direction - using angle0 + 180 = {angle0} + 180 = {azimuth}")
else:
    azimuth = angle0
    print(f"TransitionalSurface: NORMAL direction - using angle0 = {azimuth}")

bazimuth = azimuth + 180
print(f"TransitionalSurface: Final azimuth: {azimuth}, bazimuth: {bazimuth}")

# Store start_point for later use (needed for runway end calculations)
runway_start_point = start_point

# ENHANCED THRESHOLD SELECTION - Use threshold layer from UI
try:
    if threshold_layer is not None:
        print(f"TransitionalSurface: Using threshold layer from UI: {threshold_layer.name()}")
        
        if use_selected_feature:
            threshold_selection = threshold_layer.selectedFeatures()
            if not threshold_selection:
                print("TransitionalSurface: No threshold features selected, using first feature from layer")
                threshold_selection = list(threshold_layer.getFeatures())
                if not threshold_selection:
                    raise Exception("No features found in threshold layer.")
            else:
                print(f"TransitionalSurface: Using {len(threshold_selection)} selected threshold features")
        else:
            threshold_selection = list(threshold_layer.getFeatures())
            if not threshold_selection:
                raise Exception("No features found in threshold layer.")
            print(f"TransitionalSurface: Using first threshold feature from layer (selection disabled)")
        
        print(f"TransitionalSurface: Processing {len(threshold_selection)} threshold features")
        
    else:
        # Fallback to active layer
        print("TransitionalSurface: No threshold layer provided, using active layer...")
        threshold_layer = iface.activeLayer()
        if threshold_layer is None:
            raise Exception("No threshold layer found. Please select a threshold layer.")
        
        threshold_selection = threshold_layer.selectedFeatures()
        if not threshold_selection:
            threshold_selection = list(threshold_layer.getFeatures())
            if not threshold_selection:
                raise Exception("No features found in threshold layer.")
            print("TransitionalSurface: Using first threshold feature (no selection)")
        else:
            print(f"TransitionalSurface: Using {len(threshold_selection)} selected threshold features")

except Exception as e:
    print(f"TransitionalSurface: Error with threshold layer: {e}")
    iface.messageBar().pushMessage("TransitionalSurface Error", f"Threshold layer error: {str(e)}", level=Qgis.Critical)
    raise

# Get x,y from threshold - Always use first threshold feature
if len(threshold_selection) >= 1:
    selected_threshold = threshold_selection[0]
    threshold_geom = selected_threshold.geometry().asPoint()
    print(f"TransitionalSurface: Using threshold feature as-is")
else:
    raise Exception("No threshold features found")

new_geom = QgsPoint(threshold_geom)
new_geom.addZValue(Z0)

print(f"TransitionalSurface: Threshold point: {new_geom.x()}, {new_geom.y()}, {new_geom.z()}")
print(f"TransitionalSurface: Direction change handled by azimuth rotation (180°), not threshold position")

list_pts = []

# Origin 
pt_0= new_geom
    
# Distance prior from THR (60 m)
pt_01= new_geom.project(60,azimuth)
pt_01.addZValue(Z0)
#print (pt_01)
pt_01AL = pt_01.project(widthApp/2,azimuth+90)
pt_01AR = pt_01.project(widthApp/2,azimuth-90)
pt_01TL = pt_01.project(widthApp/2+(ZIH-Z0)/Tslope,azimuth+90)
pt_01TL.setZ(ZIH)
pt_01TR = pt_01.project(widthApp/2+(ZIH-Z0)/Tslope,azimuth-90)
pt_01TR.setZ(ZIH)

# Point in Approach First Section where Inner Horizontal Height Reached
dIH = (ZIH - Z0)/(2/100)
pt_08= pt_01.project(dIH,azimuth)
pt_08.setZ(Z0+dIH*0.02) # Could be ZO directly but for checking this is left
pt_08L = pt_08.project(widthApp/2+(dIH*.15),azimuth+90)
pt_08R = pt_08.project(widthApp/2+(dIH*.15),azimuth-90)

# Point in runway end
pt_02T = runway_start_point.project(60,bazimuth)
pt_02T.addZValue(ZE)
pt_02L = pt_02T.project(widthApp/2,bazimuth-90)
pt_02R = pt_02T.project(widthApp/2,bazimuth+90)
pt_02TL = pt_02T.project(widthApp/2+(ZIH-ZE)/Tslope,bazimuth-90)
pt_02TL.setZ(ZIH)
pt_02TR = pt_02T.project(widthApp/2+(ZIH-ZE)/Tslope,bazimuth+90)
pt_02TR.setZ(ZIH)

list_pts.extend((pt_0,pt_01,pt_01AL,pt_01AR,pt_01TL,pt_01TR,pt_08,pt_08L,pt_08R,runway_start_point,pt_02T,pt_02L,pt_02R,pt_02TL,pt_02TR))

# # Create Point memory layer
# p_layer = QgsVectorLayer("Point?crs="+map_srid, "Transitional Surface Construction Points", "memory")
# ur = p_layer.dataProvider()
# myField = QgsField( 'id', QVariant.String)
# p_layer.dataProvider().addAttributes([myField])
# myField = QgsField( 'PointName', QVariant.String)
# p_layer.dataProvider().addAttributes([myField])
# p_layer.updateFields()

# # Point Layer for Verification Purposes Only, this Code is to be commented at the end
# for p in list_pts:
#     segu = QgsFeature()
#     segu.setGeometry(QgsGeometry.fromPoint(p))
#     ur.addFeatures( [ segu ] )
# QgsProject.instance().addMapLayers([p_layer])

# Creation of the Transitional Surfaces
#Create memory layer
v_layer = QgsVectorLayer("PolygonZ?crs="+map_srid, "RWY_Transition Surface", "memory")
IDField = QgsField( 'ID', QVariant.String)
NameField = QgsField( 'SurfaceName', QVariant.String)
v_layer.dataProvider().addAttributes([IDField])
v_layer.dataProvider().addAttributes([NameField])
v_layer.updateFields()

# Left Transition Surface
SurfaceArea = [pt_08L,pt_01TL,pt_02TL,pt_02L,pt_01AL]
pr = v_layer.dataProvider()
seg = QgsFeature()
seg.setGeometry(QgsPolygon(QgsLineString(SurfaceArea), rings=[]))
seg.setAttributes([10,'Left Transitional Surface'])
pr.addFeatures( [ seg ] )

# Right Transition Surface
SurfaceArea = [pt_08R,pt_01TR,pt_02TR,pt_02R,pt_01AR]
pr = v_layer.dataProvider()
seg = QgsFeature()
seg.setGeometry(QgsPolygon(QgsLineString(SurfaceArea), rings=[]))
seg.setAttributes([11,'Right Transitional Surface'])
pr.addFeatures( [ seg ] )

QgsProject.instance().addMapLayers([v_layer])

# Change style of layer 
v_layer.renderer().symbol().setColor(QColor("magenta"))
v_layer.renderer().symbol().setOpacity(0.4)
v_layer.triggerRepaint()

# Zoom to layer
v_layer.selectAll()
canvas = iface.mapCanvas()
canvas.zoomToSelected(v_layer)
v_layer.removeSelection()
# Clean up selections
if 'runway_layer' in locals() and runway_layer:
    runway_layer.removeSelection()
if 'threshold_layer' in locals() and threshold_layer:
    threshold_layer.removeSelection()
#get canvas scale
sc = canvas.scale()
print (sc)
if sc < 20000:
   sc=20000
else:
    sc=sc
print (sc)
canvas.zoomScale(sc)


iface.messageBar().pushMessage("QPANSOPY:", "Transitional Surface Calculation Finished", level=Qgis.Success)


set(globals().keys()).difference(myglobals)

for g in set(globals().keys()).difference(myglobals):
    if g != 'myglobals':
        del globals()[g]