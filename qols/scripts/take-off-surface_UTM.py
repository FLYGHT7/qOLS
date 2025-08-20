'''
Take Off Climb Surface - HYBRID VERSION  
Based on original working script with UI parameter integration
Considering 15° course changes in night IMC or VMC conditions
Procedure to be used in Projected Coordinate System Only
'''
myglobals = set(globals().keys())

from qgis.core import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from qgis.gui import *
from qgis.PyQt.QtCore import QVariant
from qgis.utils import iface
from math import *

# UI Parameters - Get from plugin or use ORIGINAL defaults
print("TakeOffSurface: Script started - checking for UI parameters...")
print(f"TakeOffSurface: Available globals keys: {list(globals().keys())}")

try:
    # Get parameters from plugin
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
    s = globals().get('s', 0)
    
    # Layer parameters from UI
    runway_layer = globals().get('runway_layer')
    threshold_layer = globals().get('threshold_layer')
    
    print(f"TakeOffSurface: Using UI parameters - code={code}, s={s}")
    print(f"TakeOffSurface: Z0={Z0}, ZE={ZE}, widthDep={widthDep}, maxWidthDep={maxWidthDep}")
    print(f"TakeOffSurface: runway_layer={runway_layer}, threshold_layer={threshold_layer}")
    
except Exception as e:
    print(f"TakeOffSurface: Error getting UI parameters: {e}")
    import traceback
    print(f"TakeOffSurface: Traceback: {traceback.format_exc()}")
    # Fallback to ORIGINAL defaults - Exactly as original
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

# ORIGINAL calculations - Exactly as original
ZIH = 45 + ARPH

#s use 0 for start, -1 for end - EXACTLY as original
if s == -1:
    s2 = 180
else:
    s2 = 0

print(f"TakeOffSurface: Getting map CRS...")
try:
    map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()
    print(f"TakeOffSurface: Map SRID: {map_srid}")
except Exception as e:
    print(f"TakeOffSurface: Error getting map CRS: {e}")
    import traceback
    print(f"TakeOffSurface: CRS Traceback: {traceback.format_exc()}")
    raise

# RUNWAY LAYER SELECTION - Hybrid approach
try:
    if runway_layer:
        # Use layer from UI
        print(f"TakeOffSurface: Using runway layer from UI: {runway_layer.name()}")
        layer = runway_layer
        selection = layer.selectedFeatures()
        if not selection:
            # No selection, use all features
            selection = list(layer.getFeatures())
            if not selection:
                raise Exception("No features found in runway layer.")
            print(f"TakeOffSurface: No selection, using first feature from layer")
            selection = [selection[0]]
    else:
        # ORIGINAL METHOD - Gets the runway layer based on name and selected feature
        print("TakeOffSurface: No runway layer from UI, searching by name")
        for layer in QgsProject.instance().mapLayers().values():
            if "runway" in layer.name():
                layer = layer
                selection = layer.selectedFeatures()
                if not selection:
                    selection = list(layer.getFeatures())
                    if selection:
                        selection = [selection[0]]
                break
        else:
            raise Exception("No runway layer found")
    
    print(f"TakeOffSurface: Using runway layer: {layer.name()}")
    
    # ORIGINAL runway calculations
    rwy_geom = selection[0].geometry()
    rwy_length = rwy_geom.length()
    rwy_slope = (Z0-ZE)/rwy_length
    print(f"TakeOffSurface: rwy_length={rwy_length}")
    
except Exception as e:
    print(f"TakeOffSurface: Error with runway layer: {e}")
    iface.messageBar().pushMessage("TakeOffSurface Error", f"Runway layer error: {str(e)}", level=Qgis.Critical)
    raise

# ORIGINAL ZIHs calculation
ZIHs = ((Z0-((Z0-ZE)/rwy_length)*1800))

# Get the azimuth of the line - EXACTLY as original
for feat in selection:
    geom = feat.geometry().asPolyline()
    start_point = QgsPoint(geom[-1-s])
    end_point = QgsPoint(geom[s])
    angle0 = start_point.azimuth(end_point)
    back_angle0 = angle0 + 180

# initial true azimuth data - EXACTLY as original
azimuth = angle0 + s2
bazimuth = azimuth + 180

# THRESHOLD LAYER SELECTION - Hybrid approach  
try:
    if threshold_layer:
        # Use layer from UI
        print(f"TakeOffSurface: Using threshold layer from UI: {threshold_layer.name()}")
        threshold_selection = threshold_layer.selectedFeatures()
        if not threshold_selection:
            # No selection, use all features
            threshold_selection = list(threshold_layer.getFeatures())
            if not threshold_selection:
                raise Exception("No features found in threshold layer.")
            print(f"TakeOffSurface: No selection, using first feature from threshold layer")
            threshold_selection = [threshold_selection[0]]
    else:
        # ORIGINAL METHOD - Gets the THR definition from active layer
        print("TakeOffSurface: No threshold layer from UI, using active layer")
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

list_pts = []

# Origin - EXACTLY as original
pt_0D = new_geom

# Distance for surface start - EXACTLY as original
if CWYLength <= 60:
    dD = 60
else:
    dD = CWYLength

# ORIGINAL surface calculation - Point by point exactly as original
pt_01D = new_geom.project(dD, bazimuth)
pt_01D.setZ(ZE)
pt_01DL = pt_01D.project(widthDep/2, bazimuth+90)
pt_01DR = pt_01D.project(widthDep/2, bazimuth-90)

# Distance to reach maximum width - EXACTLY as original
pt_02D = pt_01D.project(((maxWidthDep/2-widthDep/2)/0.125), bazimuth)
pt_02D.setZ(ZE+((maxWidthDep/2-widthDep/2)/0.125)*0.02)
pt_02DL = pt_02D.project(maxWidthDep/2, bazimuth+90)
pt_02DR = pt_02D.project(maxWidthDep/2, bazimuth-90)

# Distance to end of TakeOff Climb Surface - EXACTLY as original
pt_03D = pt_01D.project(15000, bazimuth)
pt_03D.setZ(ZE+15000*0.02)
pt_03DL = pt_03D.project(maxWidthDep/2, bazimuth+90)
pt_03DR = pt_03D.project(maxWidthDep/2, bazimuth-90)

list_pts.extend((pt_0D,pt_01D,pt_01DL,pt_01DR,pt_02D,pt_02DL,pt_02DR,pt_03D,pt_03DL,pt_03DR))

# Creation of the Take Off Climb Surfaces - EXACTLY as original
#Create memory layer
v_layer = QgsVectorLayer("PolygonZ?crs="+map_srid, "RWY_TakeOffClimbSurface", "memory")
IDField = QgsField( 'ID', QVariant.String)
NameField = QgsField( 'SurfaceName', QVariant.String)
v_layer.dataProvider().addAttributes([IDField])
v_layer.dataProvider().addAttributes([NameField])
v_layer.updateFields()

# Take Off Climb Surface Creation - EXACTLY as original
SurfaceArea = [pt_03DR,pt_03DL,pt_02DL,pt_01DL,pt_01DR,pt_02DR]
pr = v_layer.dataProvider()
seg = QgsFeature()
seg.setGeometry(QgsPolygon(QgsLineString(SurfaceArea), rings=[]))
seg.setAttributes([13,'TakeOff Climb Surface'])
pr.addFeatures( [ seg ] )

#Load PolygonZ Layer to map canvas - EXACTLY as original
QgsProject.instance().addMapLayers([v_layer])

# Change style of layer - EXACTLY as original
v_layer.renderer().symbol().setColor(QColor("orange"))
v_layer.renderer().symbol().setOpacity(0.4)
v_layer.triggerRepaint()

# Zoom to layer - EXACTLY as original
v_layer.selectAll()
canvas = iface.mapCanvas()
canvas.zoomToSelected(v_layer)
v_layer.removeSelection()
layer.removeSelection()

#get canvas scale - EXACTLY as original
sc = canvas.scale()
print(sc)
if sc < 20000:
   sc = 20000
else:
    sc = sc
print(sc)
canvas.zoomScale(sc)

print("TakeOffSurface: Surface creation completed successfully")
iface.messageBar().pushMessage("QPANSOPY:", "TakeOff Climb Surface Calculation Finished", level=Qgis.Success)

# Cleanup globals - match original pattern
newglobals = set(globals().keys())
for var in (newglobals - myglobals):
    if var not in ['iface']:
        try:
            del globals()[var]
        except:
            pass

print(f"TakeOffSurface: Globals cleanup completed")
