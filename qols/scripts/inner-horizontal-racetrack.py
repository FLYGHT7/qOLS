from qgis.core import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from qgis.gui import *
from qgis.PyQt.QtCore import QVariant
from math import *

#initial true azimuth data
#azimuth = 67.077524
#back_azimuth = azimuth+180
# distance to the Splay End default being 10 NM
L = 4000
o1=0 #right
o2=0  #left
map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()
#print (map_srid)

#transformation
source_crs = QgsCoordinateReferenceSystem(4326)
#dest_crs = QgsCoordinateReferenceSystem(32616)
dest_crs = QgsCoordinateReferenceSystem(map_srid)
#transformto
trto = QgsCoordinateTransform(source_crs, dest_crs,QgsProject.instance())
#transformfrom
trfm = QgsCoordinateTransform(dest_crs,source_crs ,QgsProject.instance())


# Select line
# Gets the active layer 
layer = iface.activeLayer()
selection = layer.selectedFeatures()
# Gets x,y
for feat in selection:
    geom = feat.geometry().asPolyline()
    start_point = QgsPoint(geom[0])
    end_point = QgsPoint(geom[-1])
    angle0=start_point.azimuth(end_point)+180
    back_angle0 = angle0+180
print (angle0)
    


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

#get canvas scale
sc = canvas.scale()
#print (sc)
if sc < 30000:
   sc=30000
else:
    sc=sc
#print (sc)

canvas.zoomScale(sc)