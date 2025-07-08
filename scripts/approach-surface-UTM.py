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
code = 4
typeAPP = 'CAT I'
widthApp = 280
Z0 = 21.7
ZE = 21.7
ARPH = 29.3
ZIH = 45+ARPH
#print('ZIH: ',ZIH)
IHSlope = 33.3/100
L1 =3000
L2 = 3600
LH = 8400

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

# First Section Points 
pt_05= pt_01.project(3000,azimuth)
pt_05.setZ(Z0+3000*0.02)
pt_05L = pt_05.project(widthApp/2+(3000*.15),azimuth+90)
pt_05R = pt_05.project(widthApp/2+(3000*.15),azimuth-90)

list_pts.extend((pt_0,pt_01,pt_01AL,pt_01AR,pt_05,pt_05L,pt_05R))

# Second Section Points 
pt_06= pt_01.project(6600,azimuth)
pt_06.setZ(Z0+3000*0.02+3600*0.025)
pt_06L = pt_06.project(widthApp/2+(6600*.15),azimuth+90)
pt_06R = pt_06.project(widthApp/2+(6600*.15),azimuth-90)

# Horizontal Section Points 
pt_07= pt_01.project(15000,azimuth)
pt_07.setZ(Z0+3000*0.02+3600*0.025)
pt_07L = pt_07.project(widthApp/2+(15000*.15),azimuth+90)
pt_07R = pt_07.project(widthApp/2+(15000*.15),azimuth-90)

list_pts.extend((pt_06,pt_06L,pt_06R,pt_07,pt_07L,pt_07R))

# # Create Point memory layer
# p_layer = QgsVectorLayer("Point?crs="+map_srid, "Approach Layer Construction Points", "memory")
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

# Creation of the Approach Surfaces
#Create memory layer
v_layer = QgsVectorLayer("PolygonZ?crs="+map_srid, "RWY_ApproachSurface", "memory")
IDField = QgsField( 'ID', QVariant.String)
NameField = QgsField( 'SurfaceName', QVariant.String)
v_layer.dataProvider().addAttributes([IDField])
v_layer.dataProvider().addAttributes([NameField])
v_layer.updateFields()

# Approach - First Section
SurfaceArea = [pt_05R,pt_05L,pt_01AL,pt_01AR]
pr = v_layer.dataProvider()
seg = QgsFeature()
seg.setGeometry(QgsPolygon(QgsLineString(SurfaceArea), rings=[]))
seg.setAttributes([6,'Approach First Section'])
pr.addFeatures( [ seg ] )

# Approach - Second Section
SurfaceArea = [pt_06R,pt_06L,pt_05L,pt_05R]
pr = v_layer.dataProvider()
seg = QgsFeature()
seg.setGeometry(QgsPolygon(QgsLineString(SurfaceArea), rings=[]))
seg.setAttributes([7,'Approach Second Section'])
pr.addFeatures( [ seg ] )

# Approach - Horizontal Section
SurfaceArea = [pt_07R,pt_07L,pt_06L,pt_06R]
pr = v_layer.dataProvider()
seg = QgsFeature()
seg.setGeometry(QgsPolygon(QgsLineString(SurfaceArea), rings=[]))
seg.setAttributes([8,'Approach Horizontal Section'])
pr.addFeatures( [ seg ] )

#Load PolygonZ Layer to map canvas 
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

iface.messageBar().pushMessage("QPANSOPY:", "Approach Surface Calculation Finished", level=Qgis.Success)

set(globals().keys()).difference(myglobals)

for g in set(globals().keys()).difference(myglobals):
    if g != 'myglobals':
        del globals()[g]