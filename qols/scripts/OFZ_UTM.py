'''
Inner Approach Surface 4 CAT I - Obstacle Free Zone
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
try:
    # Try to get parameters from plugin namespace
    code = globals().get('code', 4)
    rwyClassification = globals().get('rwyClassification', 'Precision Approach CAT I')
    width = globals().get('width', 120)
    Z0 = globals().get('Z0', 2546.5)
    ZE = globals().get('ZE', 2548)
    ARPH = globals().get('ARPH', 2548)
    IHSlope = globals().get('IHSlope', 33.3/100)
    
    # Direction parameter
    s = globals().get('direction', 0)  # 0 for start to end, -1 for end to start
    
    # Layer parameters
    runway_layer = globals().get('runway_layer', None)
    threshold_layer = globals().get('threshold_layer', None)
    use_selected_feature = globals().get('use_selected_feature', True)
    
    print(f"OFZ: Using parameters - code: {code}, width: {width}, Z0: {Z0}, ZE: {ZE}")
    print(f"OFZ: Direction parameter s: {s}, Use selected: {use_selected_feature}")
    
except Exception as e:
    print(f"OFZ: Error getting parameters, using defaults: {e}")
    # Fallback to defaults if parameters not provided
    code = 4
    rwyClassification = 'Precision Approach CAT I'
    width = 120
    Z0 = 2546.5
    ZE = 2548
    ARPH = 2548
    IHSlope = 33.3/100
    s = 0
    runway_layer = None
    threshold_layer = None
    use_selected_feature = True

# Calculate derived parameters
ZIH = 45+ARPH
print(f"OFZ: ZIH: {ZIH}")

print(f"OFZ: Final values - s: {s}, ZIH: {ZIH}")
print(f"OFZ: Direction interpretation - s={s} means {'End to Start' if s == -1 else 'Start to End'}")

map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()

# ENHANCED LAYER SELECTION - Use layers from UI
try:
    if runway_layer is not None:
        print(f"OFZ: Using runway layer from UI: {runway_layer.name()}")
        
        if use_selected_feature:
            # Require explicit feature selection
            selection = runway_layer.selectedFeatures()
            if not selection:
                raise Exception("No runway features selected. Please select runway features.")
            print(f"OFZ: Using {len(selection)} selected runway features")
        else:
            selection = list(runway_layer.getFeatures())
            if not selection:
                raise Exception("No features found in runway layer.")
            print(f"OFZ: Using first feature from layer (selection disabled)")
        
        print(f"OFZ: Processing {len(selection)} runway features")
        rwy_geom = selection[0].geometry()
        rwy_length = rwy_geom.length()
        rwy_slope = (Z0-ZE)/rwy_length if rwy_length > 0 else 0
        
        print(f"OFZ: Runway length: {rwy_length}, slope: {rwy_slope}")
        
    else:
        # No fallback - require explicit runway layer selection
        raise Exception("No runway layer provided. Please select a runway layer from the UI.")

except Exception as e:
    print(f"OFZ: Error with runway layer: {e}")
    iface.messageBar().pushMessage("OFZ Error", f"Runway layer error: {str(e)}", level=Qgis.Critical)
    raise

# Calculate ZIHs
ZIHs = ((Z0-((Z0-ZE)/rwy_length)*1800))
print(f"OFZ: ZIHs calculated: {ZIHs}")

# Get the azimuth of the line - SIMPLIFIED LOGIC
for feat in selection:
    geom = feat.geometry().asPolyline()
    print(f"OFZ: Geometry points count: {len(geom)}")
    
    # Always use the same points regardless of direction
    start_point = QgsPoint(geom[0])   # Always first point
    end_point = QgsPoint(geom[-1])    # Always last point
    angle0 = start_point.azimuth(end_point)
    
    print(f"OFZ: Using consistent points regardless of direction")
    print(f"OFZ: Start point: {start_point.x()}, {start_point.y()}")
    print(f"OFZ: End point: {end_point.x()}, {end_point.y()}")
    print(f"OFZ: Base azimuth (angle0): {angle0}")

# Initial true azimuth data - FIXED LOGIC FOR PROPER DIRECTION CHANGE
if s == -1:
    azimuth = angle0 + 180
    if azimuth >= 360:
        azimuth -= 360
    print(f"OFZ: REVERSE direction - using angle0 + 180 = {angle0} + 180 = {azimuth}")
else:
    azimuth = angle0
    print(f"OFZ: NORMAL direction - using angle0 = {azimuth}")

print(f"OFZ: Final azimuth: {azimuth}")

# ENHANCED THRESHOLD SELECTION - Use threshold layer from UI
try:
    if threshold_layer is not None:
        print(f"OFZ: Using threshold layer from UI: {threshold_layer.name()}")
        
        if use_selected_feature:
            # Require explicit feature selection
            threshold_selection = threshold_layer.selectedFeatures()
            if not threshold_selection:
                raise Exception("No threshold features selected. Please select threshold features.")
            print(f"OFZ: Using {len(threshold_selection)} selected threshold features")
        else:
            threshold_selection = list(threshold_layer.getFeatures())
            if not threshold_selection:
                raise Exception("No features found in threshold layer.")
            print(f"OFZ: Using first threshold feature from layer (selection disabled)")
        
        print(f"OFZ: Processing {len(threshold_selection)} threshold features")
        
    else:
        # No fallback - require explicit threshold layer selection
        raise Exception("No threshold layer provided. Please select a threshold layer from the UI.")

except Exception as e:
    print(f"OFZ: Error with threshold layer: {e}")
    iface.messageBar().pushMessage("OFZ Error", f"Threshold layer error: {str(e)}", level=Qgis.Critical)
    raise

# Get x,y from threshold
if len(threshold_selection) >= 1:
    selected_threshold = threshold_selection[0]
    threshold_geom = selected_threshold.geometry().asPoint()
    print(f"OFZ: Using threshold feature as-is")
else:
    raise Exception("No threshold features found")

new_geom = QgsPoint(threshold_geom)
new_geom.addZValue(Z0)

print(f"OFZ: Threshold point: {new_geom.x()}, {new_geom.y()}, {new_geom.z()}")
print(f"OFZ: Direction change handled by azimuth rotation (180°), not threshold position")

list_pts = []

# Origin 
pt_0= new_geom
print (pt_0)
pt_0L = new_geom.project(width/2,azimuth+90)
pt_0R = new_geom.project(width/2,azimuth-90)
    
# Distance prior from THR (60 m)
pt_01= new_geom.project(60,azimuth)
pt_01L = pt_01.project(width/2,azimuth+90)
pt_01R = pt_01.project(width/2,azimuth-90)

# Inner Approach Length Point 
pt_02= pt_01.project(900,azimuth)
pt_02.setZ(Z0+18)
pt_02L = pt_02.project(width/2,azimuth+90)
pt_02R = pt_02.project(width/2,azimuth-90)

list_pts.extend((pt_0,pt_0L,pt_0R,pt_01,pt_01L,pt_01R,pt_02,pt_02L,pt_02R))

# Balked Landing start Distance from THR
pt_03= pt_0.project(1800,azimuth-180)
pt_03.setZ(ZIHs)
pt_03L = pt_03.project(width/2,azimuth+90)
pt_03R = pt_03.project(width/2,azimuth-90)

# Inner Approach Side at Start
pt_I0L = pt_0L.project((ZIH-Z0)/IHSlope,azimuth+90)
pt_I0L.setZ(ZIH)
pt_I0R = pt_0R.project((ZIH-Z0)/IHSlope,azimuth-90)
pt_I0R.setZ(ZIH)
pt_I01L = pt_01L.project((ZIH-Z0)/IHSlope,azimuth+90)
pt_I01L.setZ(ZIH)
pt_I01R = pt_01R.project((ZIH-Z0)/IHSlope,azimuth-90)
pt_I01R.setZ(ZIH)
#pt_I0R

list_pts.extend ((pt_03,pt_03L,pt_03R,pt_I0L,pt_I0R,pt_I01L,pt_I01R))

# Inner Approach Side at End 
pt_I02L = pt_02L.project((ZIH-(Z0+900*0.02))/IHSlope,azimuth+90)
pt_I02L.setZ(ZIH)
pt_I02R = pt_02R.project((ZIH-(Z0+900*0.02))/IHSlope,azimuth-90)
pt_I02R.setZ(ZIH)

# Balked Landing Side at Start
pt_I03L = pt_03L.project((ZIH-(Z0-((Z0-ZE)/rwy_length)*1800))/IHSlope,azimuth+90)
pt_I03L.setZ(ZIH)
pt_I03R = pt_03R.project((ZIH-(Z0-((Z0-ZE)/rwy_length)*1800))/IHSlope,azimuth-90)
pt_I03R.setZ(ZIH)

# Balked Landing at End
pt_04= pt_03.project((ZIH-(Z0-((Z0-ZE)/rwy_length)*1800))/(3.33/100),azimuth-180)
pt_04.setZ(ZIH)
pt_04L= pt_04.project(((ZIH-(Z0-((Z0-ZE)/rwy_length)*1800))/(3.33/100))*.10+60,azimuth+90)
pt_04R= pt_04.project(((ZIH-(Z0-((Z0-ZE)/rwy_length)*1800))/(3.33/100))*.10+60,azimuth-90)


list_pts.extend ((pt_I02L,pt_I02R,pt_I03L,pt_I03R,pt_04,pt_04L,pt_04R))

# Create Point memory layer
p_layer = QgsVectorLayer("Point?crs="+map_srid, "Points", "memory")
ur = p_layer.dataProvider()
myField = QgsField( 'id', QVariant.String)
p_layer.dataProvider().addAttributes([myField])
myField = QgsField( 'PointName', QVariant.String)
p_layer.dataProvider().addAttributes([myField])
p_layer.updateFields()

# Point Layer for Verification Purposes Only, this Code is to be commented at the end
# for p in list_pts:
#     segu = QgsFeature()
#     segu.setGeometry(QgsGeometry.fromPointXY(p))
#     ur.addFeatures( [ segu ] )
# QgsProject.instance().addMapLayers([p_layer])

# Creation of the Balked Landing Surfaces 
#Create memory layer
v_layer = QgsVectorLayer("PolygonZ?crs="+map_srid, "RWY_ObstacleFreeZone", "memory")
IDField = QgsField( 'ID', QVariant.String)
NameField = QgsField( 'SurfaceName', QVariant.String)
v_layer.dataProvider().addAttributes([IDField])
v_layer.dataProvider().addAttributes([NameField])
v_layer.updateFields()

# Runway Inner Strip Surface Polygon
SurfaceArea = [pt_03,pt_03L,pt_0L,pt_01L,pt_01,pt_01R,pt_0R,pt_03R]
pr = v_layer.dataProvider()
seg = QgsFeature()
seg.setGeometry(QgsPolygon(QgsLineString(SurfaceArea), rings=[]))
seg.setAttributes([1,'Runway Inner Strip'])
pr.addFeatures( [ seg ] )

# Inner Approach Surface Polygon
SurfaceArea = [pt_01,pt_01L,pt_02L,pt_02,pt_02R,pt_01R]
pr = v_layer.dataProvider()
seg = QgsFeature()
seg.setGeometry(QgsPolygon(QgsLineString(SurfaceArea), rings=[]))
seg.setAttributes([2,'Inner Approach Surface'])
pr.addFeatures( [ seg ] )

# Balked Landing Surface Polygon
SurfaceArea = [pt_04,pt_04L,pt_03L,pt_03,pt_03R,pt_04R]
pr = v_layer.dataProvider()
seg = QgsFeature()
seg.setGeometry(QgsPolygon(QgsLineString(SurfaceArea), rings=[]))
seg.setAttributes([3,'Balked Landing Surface'])
pr.addFeatures( [ seg ] )

# Inner Transitional Right Surface Polygon
SurfaceArea = [pt_04R,pt_03R,pt_0R,pt_01R,pt_02R,pt_I02R,pt_I01R,pt_I0R,pt_I03R]
pr = v_layer.dataProvider()
seg = QgsFeature()
seg.setGeometry(QgsPolygon(QgsLineString(SurfaceArea), rings=[]))
seg.setAttributes([4,'Inner Transitional Surface - Right Side'])
pr.addFeatures( [ seg ] )

# Inner Transitional Left Surface Polygon
SurfaceArea = [pt_04L,pt_03L,pt_0L,pt_01L,pt_02L,pt_I02L,pt_I01L,pt_I0L,pt_I03L]
pr = v_layer.dataProvider()
seg = QgsFeature()
seg.setGeometry(QgsPolygon(QgsLineString(SurfaceArea), rings=[]))
seg.setAttributes([5,'Inner Transitional Surface - Left Side'])
pr.addFeatures( [ seg ] )

QgsProject.instance().addMapLayers([v_layer])

# Change style of layer 
v_layer.renderer().symbol().setColor(QColor("blue"))
v_layer.renderer().symbol().setOpacity(0.4)
v_layer.triggerRepaint()

# Zoom to layer
v_layer.selectAll()
canvas = iface.mapCanvas()
canvas.zoomToSelected(v_layer)
v_layer.removeSelection()
try:
    layer.removeSelection()
except:
    pass
    
#get canvas scale
sc = canvas.scale()
print (sc)
if sc < 20000:
   sc=20000
else:
    sc=sc
print (sc)
canvas.zoomScale(sc)

iface.messageBar().pushMessage("QPANSOPY:", "OFZ Calculation Finished", level=Qgis.Success)

print("OFZ: Script completed successfully")


set(globals().keys()).difference(myglobals)

for g in set(globals().keys()).difference(myglobals):
    if g != 'myglobals':
        del globals()[g]