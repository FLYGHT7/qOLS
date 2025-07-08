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

# Parameters 
# Parameters 
code = 4
typeAPP = 'CAT I'
widthApp = 280
Z0 = 2548
ZE = 2546.5
ARPH = 2548
ZIH = 45+ARPH
#print('ZIH: ',ZIH)
IHSlope = 33.3/100
L1 =3000
L2 = 3600
LH = 8400
Tslope =14.3/100

#s use 0 for start, -1 for end
s = 0
if s == -1:
    s2 = 180
else:
    s2= 0
#print (s2)

map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()

# Select line
# Gets the runway layer based on name and selected feature
for layer in QgsProject.instance().mapLayers().values():
    if "xrunway" in layer.name():
        layer = layer
        selection = layer.selectedFeatures()
        rwy_geom = selection[0].geometry()
        rwy_length = rwy_geom.length()
        rwy_slope = (Z0-ZE)/rwy_length
        print (rwy_length)
        #print (layer.name())

ZIHs = ((Z0-((Z0-ZE)/rwy_length)*1800))
print (ZIHs)

        
#Get the azimuth of the line 
for feat in selection:
    geom = feat.geometry().asPolyline()
    #start and end points inverted, leave like this for now
    #calculations have been made with this assumption
    start_point = QgsPoint(geom[-1-s])
    end_point = QgsPoint(geom[s])
    angle0=start_point.azimuth(end_point)
    back_angle0 = angle0+180
#print (angle0)

#initial true azimuth data
azimuth =angle0+s2
bazimuth = azimuth +180

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
pt_02T = start_point.project(60,bazimuth)
pt_02T.addZValue(ZE)
pt_02L = pt_02T.project(widthApp/2,bazimuth-90)
pt_02R = pt_02T.project(widthApp/2,bazimuth+90)
pt_02TL = pt_02T.project(widthApp/2+(ZIH-ZE)/Tslope,bazimuth-90)
pt_02TL.setZ(ZIH)
pt_02TR = pt_02T.project(widthApp/2+(ZIH-ZE)/Tslope,bazimuth+90)
pt_02TR.setZ(ZIH)

list_pts.extend((pt_0,pt_01,pt_01AL,pt_01AR,pt_01TL,pt_01TR,pt_08,pt_08L,pt_08R,start_point,pt_02T,pt_02L,pt_02R,pt_02TL,pt_02TR))

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


iface.messageBar().pushMessage("QPANSOPY:", "Transitional Surface Calculation Finished", level=Qgis.Success)


set(globals().keys()).difference(myglobals)

for g in set(globals().keys()).difference(myglobals):
    if g != 'myglobals':
        del globals()[g]