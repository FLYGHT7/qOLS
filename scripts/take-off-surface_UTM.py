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

# Parameters (use injected values when provided; fall back to defaults)
code = globals().get('code', 4)
typeAPP = globals().get('rwyClassification', globals().get('typeAPP', 'CAT I'))
widthApp = globals().get('widthApp', 150)
widthDep = globals().get('widthDep', 180)
maxWidthDep = globals().get('maxWidthDep', 1800)
CWYLength = globals().get('CWYLength', 0)
Z0 = globals().get('Z0', 2548)
ZE = globals().get('ZE', 2546.5)
ARPH = globals().get('ARPH', 2548)
ZIH = 45+ARPH
# Additional exposed parameters
divergencePct = globals().get('divergencePct', 12.5)  # percent
startDistance = globals().get('startDistance', 60.0)  # meters
surfaceLength = globals().get('surfaceLength', 15000.0)  # meters
slopePct = globals().get('slopePct', 2.0)  # percent

# s use 0 for start, -1 for end
s = globals().get('s', 0)
if s == -1:
    s2 = 180
else:
    s2= 0
#print (s2)

map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()

# Select line
# Gets the runway layer based on name and selected feature
for layer in QgsProject.instance().mapLayers().values():
    if "runway" in layer.name():
        layer = layer
        selection = layer.selectedFeatures()
        rwy_geom = selection[0].geometry()
        rwy_length = rwy_geom.length()
        rwy_slope = (Z0-ZE)/rwy_length
        print (rwy_length)
        #print (layer.name())

ZIHs = ((Z0-((Z0-ZE)/rwy_length)*1800))
#print (ZIHs)

        
#Get the azimuth of the line 
for feat in selection:
    geom = feat.geometry().asPolyline()
    start_point = QgsPoint(geom[-1-s])
    end_point = QgsPoint(geom[s])
    angle0=start_point.azimuth(end_point)
    back_angle0 = angle0+180
#print (angle0)

#initial true azimuth data
azimuth =angle0+s2
bazimuth = azimuth+180

# Gets the THR definition 
layer = iface.activeLayer()
#layer.selectByExpression("designator='24'")
selection = layer.selectedFeatures()
# Gets x,y
for feat in selection:
    new_geom = QgsPoint(feat.geometry().asPoint())
    new_geom.addZValue(Z0)

list_pts = []

# Origin 
pt_0D= new_geom
    
# Distance for surface start: use max(CWYLength, startDistance)
if CWYLength <= startDistance:
    dD = startDistance
else:
    dD = CWYLength

pt_01D = new_geom.project(dD,bazimuth)
pt_01D.setZ(ZE)
#print (pt_01)
pt_01DL = pt_01D.project(widthDep/2,bazimuth+90)
pt_01DR = pt_01D.project(widthDep/2,bazimuth-90)

# Distance to reach maximum width: based on divergence percentage
divergence_rate = divergencePct/100.0  # convert to decimal per unit length per side
pt_02D = pt_01D.project(((maxWidthDep/2 - widthDep/2) / divergence_rate), bazimuth)
pt_02D.setZ(ZE + ((maxWidthDep/2 - widthDep/2) / divergence_rate) * (slopePct/100.0))
pt_02DL = pt_02D.project(maxWidthDep/2,bazimuth+90)
pt_02DR = pt_02D.project(maxWidthDep/2,bazimuth-90)

# Distance to end of TakeOff Climb Surface
pt_03D = pt_01D.project(surfaceLength, bazimuth)
pt_03D.setZ(ZE + surfaceLength * (slopePct/100.0))
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
layer.removeSelection()
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