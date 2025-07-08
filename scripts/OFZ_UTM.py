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
width = 120
Z0 = 2546.5
ZE = 2548
ARPH = 2548
ZIH = 45+ARPH
print('ZIH: ',ZIH)
IHSlope = 33.3/100


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


iface.messageBar().pushMessage("QPANSOPY:", "OFZ Calculation Finished", level=Qgis.Success)


set(globals().keys()).difference(myglobals)

for g in set(globals().keys()).difference(myglobals):
    if g != 'myglobals':
        del globals()[g]