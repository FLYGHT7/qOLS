'''
Take Off Climb Surface
Considering 15° course changes in night IMC or VMC conditions
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
    widthApp = globals().get('widthApp', 150)
    widthDep = globals().get('widthDep', 180)
    maxWidthDep = globals().get('maxWidthDep', 1800)
    CWYLength = globals().get('CWYLength', 0)
    Z0 = globals().get('Z0', 2548)
    ZE = globals().get('ZE', 2546.5)
    ARPH = globals().get('ARPH', 2548)
    IHSlope = globals().get('IHSlope', 33.3/100)
    L1 = globals().get('L1', 3000)
    L2 = globals().get('L2', 3600)
    LH = globals().get('LH', 8400)
    
    # Direction parameter
    s = globals().get('direction', 0)  # 0 for start to end, -1 for end to start
    
    # Layer parameters
    runway_layer = globals().get('runway_layer', None)
    threshold_layer = globals().get('threshold_layer', None)
    use_selected_feature = globals().get('use_selected_feature', True)
    
    print(f"TakeOffSurface: Using parameters - code: {code}, widthDep: {widthDep}, Z0: {Z0}, ZE: {ZE}")
    print(f"TakeOffSurface: Direction parameter s: {s}, Use selected: {use_selected_feature}")
    
except Exception as e:
    print(f"TakeOffSurface: Error getting parameters, using defaults: {e}")
    # Fallback to defaults if parameters not provided
    code = 4
    typeAPP = 'CAT I'
    widthApp = 150
    widthDep = 180
    maxWidthDep = 1800
    CWYLength = 0
    Z0 = 2548
    ZE = 2546.5
    ARPH = 2548
    IHSlope = 33.3/100
    L1 = 3000
    L2 = 3600
    LH = 8400
    s = 0
    runway_layer = None
    threshold_layer = None
    use_selected_feature = True

# Calculate derived parameters
ZIH = 45 + ARPH

print(f"TakeOffSurface: Final values - s: {s}, ZIH: {ZIH}")
print(f"TakeOffSurface: Direction interpretation - s={s} means {'End to Start' if s == -1 else 'Start to End'}")

map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()

# ENHANCED LAYER SELECTION - Use layers from UI but with ORIGINAL LOGIC
try:
    if runway_layer is not None:
        print(f"TakeOffSurface: Using runway layer from UI: {runway_layer.name()}")
        
        if use_selected_feature:
            # Require explicit feature selection
            selection = runway_layer.selectedFeatures()
            if not selection:
                raise Exception("No runway features selected. Please select runway features.")
            print(f"TakeOffSurface: Using {len(selection)} selected runway features")
        else:
            selection = list(runway_layer.getFeatures())
            if not selection:
                raise Exception("No features found in runway layer.")
            print(f"TakeOffSurface: Using first feature from layer (selection disabled)")
        
        # ORIGINAL CALCULATION LOGIC - Keep exact calculation from working script
        rwy_geom = selection[0].geometry()
        rwy_length = rwy_geom.length()
        rwy_slope = (Z0-ZE)/rwy_length if rwy_length > 0 else 0
        
        print(f"TakeOffSurface: Runway length: {rwy_length}, slope: {rwy_slope}")
        
    else:
        # Fallback to original method - search by name pattern
        print("TakeOffSurface: No runway layer from UI, using original layer search")
        layer_found = False
        for layer in QgsProject.instance().mapLayers().values():
            if "runway" in layer.name().lower():
                runway_layer = layer
                selection = layer.selectedFeatures()
                if selection:
                    rwy_geom = selection[0].geometry()
                    rwy_length = rwy_geom.length()
                    rwy_slope = (Z0-ZE)/rwy_length
                    print(f"TakeOffSurface: Found runway layer: {layer.name()}")
                    print(f"TakeOffSurface: Runway length: {rwy_length}")
                    layer_found = True
                    break
        
        if not layer_found:
            raise Exception("No runway layer found. Please select a runway layer or ensure a runway layer exists.")

except Exception as e:
    print(f"TakeOffSurface: Error with runway layer: {e}")
    iface.messageBar().pushMessage("TakeOffSurface Error", f"Runway layer error: {str(e)}", level=Qgis.Critical)
    raise

# Calculate ZIHs - EXACTLY as original
ZIHs = ((Z0-((Z0-ZE)/rwy_length)*1800))
print(f"TakeOffSurface: ZIHs calculated: {ZIHs}")

        
#Get the azimuth of the line - EXACTLY as original
for feat in selection:
    geom = feat.geometry().asPolyline()
    print(f"TakeOffSurface: Geometry points count: {len(geom)}")
    
    # ORIGINAL LOGIC - Use direction to determine point selection
    start_point = QgsPoint(geom[-1-s])  # Original formula
    end_point = QgsPoint(geom[s])       # Original formula
    angle0 = start_point.azimuth(end_point)
    back_angle0 = angle0 + 180
    
    print(f"TakeOffSurface: Using original point selection logic")
    print(f"TakeOffSurface: s={s}, start_point index: {-1-s}, end_point index: {s}")
    print(f"TakeOffSurface: Start point: {start_point.x()}, {start_point.y()}")
    print(f"TakeOffSurface: End point: {end_point.x()}, {end_point.y()}")
    print(f"TakeOffSurface: angle0: {angle0}")

# ORIGINAL AZIMUTH CALCULATION - Exactly as original
if s == -1:
    s2 = 180
else:
    s2 = 0

azimuth = angle0 + s2
bazimuth = azimuth + 180

print(f"TakeOffSurface: Original calculation - s2: {s2}")
print(f"TakeOffSurface: Final azimuth: {azimuth}, bazimuth: {bazimuth}")

# ENHANCED THRESHOLD SELECTION - Use threshold layer from UI OR original method
try:
    if threshold_layer is not None:
        print(f"TakeOffSurface: Using threshold layer from UI: {threshold_layer.name()}")
        
        if use_selected_feature:
            # Require explicit feature selection
            threshold_selection = threshold_layer.selectedFeatures()
            if not threshold_selection:
                raise Exception("No threshold features selected. Please select threshold features.")
            print(f"TakeOffSurface: Using {len(threshold_selection)} selected threshold features")
        else:
            threshold_selection = list(threshold_layer.getFeatures())
            if not threshold_selection:
                raise Exception("No features found in threshold layer.")
            print(f"TakeOffSurface: Using first threshold feature from layer (selection disabled)")
        
        print(f"TakeOffSurface: Processing {len(threshold_selection)} threshold features")
        
    else:
        # ORIGINAL METHOD - Gets the THR definition from active layer
        print("TakeOffSurface: No threshold layer from UI, using original active layer method")
        layer = iface.activeLayer()
        threshold_selection = layer.selectedFeatures()
        if not threshold_selection:
            raise Exception("No features selected in active layer for threshold.")
        print(f"TakeOffSurface: Using active layer: {layer.name()}")

except Exception as e:
    print(f"TakeOffSurface: Error with threshold layer: {e}")
    iface.messageBar().pushMessage("TakeOffSurface Error", f"Threshold layer error: {str(e)}", level=Qgis.Critical)
    raise

# Get x,y from threshold - EXACTLY as original
for feat in threshold_selection:
    new_geom = QgsPoint(feat.geometry().asPoint())
    new_geom.addZValue(Z0)
    break  # Use first feature

print(f"TakeOffSurface: Threshold point: {new_geom.x()}, {new_geom.y()}, {new_geom.z()}")
print(f"TakeOffSurface: Using original threshold selection logic")

list_pts = []

# Origin 
pt_0D= new_geom
    
# Distance for surface start 

if CWYLength<=60:
    dD = 60
else:
    dD = CWYLength

pt_01D = new_geom.project(dD,bazimuth)
pt_01D.setZ(ZE)
#print (pt_01)
pt_01DL = pt_01D.project(widthDep/2,bazimuth+90)
pt_01DR = pt_01D.project(widthDep/2,bazimuth-90)

# Distance to reach maximum width

pt_02D = pt_01D.project(((maxWidthDep/2-widthDep/2)/0.125),bazimuth)
pt_02D.setZ(ZE+((maxWidthDep/2-widthDep/2)/0.125)*0.02)
pt_02DL = pt_02D.project(maxWidthDep/2,bazimuth+90)
pt_02DR = pt_02D.project(maxWidthDep/2,bazimuth-90)

# Distance to end of TakeOff Climb SurfaceAboutToBeDestroyed
pt_03D = pt_01D.project(15000,bazimuth)
pt_03D.setZ(ZE+15000*0.02)
pt_03DL = pt_03D.project(maxWidthDep/2,bazimuth+90)
pt_03DR = pt_03D.project(maxWidthDep/2,bazimuth-90)

list_pts.extend((pt_0D,pt_01D,pt_01DL,pt_01DR,pt_02D,pt_02DL,pt_02DR,pt_03D,pt_03DL,pt_03DR))

# # Create Point memory layer
# p_layer = QgsVectorLayer("Point?crs="+map_srid, "TakeOff Climb Surface Layer Construction Points", "memory")
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

# Creation of the Take Off Climb Surfaces
#Create memory layer
v_layer = QgsVectorLayer("PolygonZ?crs="+map_srid, "RWY_TakeOffClimbSurface", "memory")
IDField = QgsField( 'ID', QVariant.String)
NameField = QgsField( 'SurfaceName', QVariant.String)
v_layer.dataProvider().addAttributes([IDField])
v_layer.dataProvider().addAttributes([NameField])
v_layer.updateFields()

# Take Off Climb Surface Creation
SurfaceArea = [pt_03DR,pt_03DL,pt_02DL,pt_01DL,pt_01DR,pt_02DR]
pr = v_layer.dataProvider()
seg = QgsFeature()
seg.setGeometry(QgsPolygon(QgsLineString(SurfaceArea), rings=[]))
seg.setAttributes([13,'TakeOff Climb Surface'])
pr.addFeatures( [ seg ] )

#Load PolygonZ Layer to map canvas 
QgsProject.instance().addMapLayers([v_layer])

# Change style of layer 
v_layer.renderer().symbol().setColor(QColor("orange"))
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

iface.messageBar().pushMessage("QPANSOPY:", "TakeOff Climb Surface Calculation Finished", level=Qgis.Success)

set(globals().keys()).difference(myglobals)

for g in set(globals().keys()).difference(myglobals):
    if g != 'myglobals':
        del globals()[g]