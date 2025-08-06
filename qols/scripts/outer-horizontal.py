'''
Outer Horizontal Surface 
'''

from qgis.core import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from qgis.gui import *
from qgis.PyQt.QtCore import QVariant
from math import *


# from qgis.PyQt.QtWidgets import QDockWidget
# consoleWidget = iface.mainWindow().findChild( QDockWidget, 'PythonConsole' )
# consoleWidget.console.shellOut.clearConsole()


#map_srid
map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()
print (map_srid)

#transformation
source_crs = QgsCoordinateReferenceSystem(4326)
dest_crs = QgsCoordinateReferenceSystem(map_srid)
#transformto
trto = QgsCoordinateTransform(source_crs, dest_crs,QgsProject.instance())
#transformfrom
trfm = QgsCoordinateTransform(dest_crs,source_crs ,QgsProject.instance())


# Get threshold layer from plugin parameters
threshold_layer = globals().get('threshold_layer')
use_selected_feature = globals().get('use_selected_feature', True)

# Get threshold geometry
if threshold_layer:
    if use_selected_feature:
        selection = threshold_layer.selectedFeatures()
        if not selection:
            print("No threshold features selected")
            raise Exception("No threshold features selected")
    else:
        selection = list(threshold_layer.getFeatures())
        if not selection:
            print("No threshold features found")
            raise Exception("No threshold features found")
else:
    print("No threshold layer provided")
    raise Exception("No threshold layer provided")

# Gets x,y from threshold
for feat in selection:
    der_geom = feat.geometry().asPoint()
    print (der_geom)
    new_geom = trto.transform(der_geom)
    print (new_geom)
    
v_layer = QgsVectorLayer("LineString", "Outer Horizontal", "memory")

# 

line = QgsGeometry.fromwkt([line_start,line_end])
pr = v_layer.dataProvider()
# create a new feature
seg = QgsFeature()
# add the geometry to the feature, 
seg.setGeometry(QgsGeometry.fromPolyline([line_start, line2_end]))
# ...it was here that you can add attributes, after having defined....
# add the geometry to the layer
pr.addFeatures( [ seg ] )
# update extent of the layer (not necessary)
v_layer.updateExtents()
# show the line  
QgsProject.instance().addMapLayers([v_layer])


# Change style of layer 
v_layer.renderer().symbol().setColor(QColor("blue"))
v_layer.renderer().symbol().setWidth(0.7)
v_layer.triggerRepaint()

# Zoom to layer
v_layer.selectAll()
canvas = iface.mapCanvas()
canvas.zoomToSelected(v_layer)
v_layer.removeSelection()

#get canvas scale
sc = canvas.scale()
print (sc)
if sc < 20000:
   sc=20000
else:
    sc=sc
print (sc)

canvas.zoomScale(sc)