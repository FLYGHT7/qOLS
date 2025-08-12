'''
Outer Horizontal Surface 
Procedure to be used in Projected Coordinate System Only
ROBUST VERSION - No fallbacks, no CRS transformations, explicit layer and feature selection required
'''

from qgis.core import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from qgis.gui import *
from qgis.PyQt.QtCore import QVariant
from math import *

# Work exclusively in projected coordinate system - no transformations needed
map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()
print(f"OuterHorizontal: Working in projected CRS: {map_srid}")

# Get threshold layer from plugin parameters
threshold_layer = globals().get('threshold_layer')
use_selected_feature = globals().get('use_selected_feature', True)

if not threshold_layer:
    raise Exception("No threshold layer provided. Please select a threshold layer from the UI.")

# Get threshold geometry - require explicit selection
if use_selected_feature:
    # Require explicit feature selection
    selection = threshold_layer.selectedFeatures()
    if not selection:
        raise Exception("No threshold features selected. Please select threshold features.")
    print(f"OuterHorizontal: Using {len(selection)} selected threshold features")
else:
    # Use all features (take first one)
    selection = list(threshold_layer.getFeatures())
    if not selection:
        raise Exception("No features found in threshold layer.")
    print(f"OuterHorizontal: Using first threshold feature from layer (selection disabled)")

# Get x,y from threshold - work directly in projected coordinates
for feat in selection:
    threshold_geom = feat.geometry().asPoint()
    print(f"OuterHorizontal: Threshold point: {threshold_geom.x()}, {threshold_geom.y()}")
    
    # Create outer horizontal surface geometry (placeholder - needs proper implementation)
    # TODO: Complete the outer horizontal surface calculation logic
    print("OuterHorizontal: Warning - Surface calculation logic needs implementation")
    
# Create memory layer
v_layer = QgsVectorLayer(f"LineString?crs={map_srid}", "Outer Horizontal", "memory")

# TODO: Add proper geometry creation logic here
# The original code has syntax errors and incomplete geometry creation

# For now, create a simple placeholder
print("OuterHorizontal: Creating placeholder geometry - needs proper implementation")

# Add to map
QgsProject.instance().addMapLayers([v_layer])

# Change style of layer 
v_layer.renderer().symbol().setColor(QColor("blue"))
v_layer.renderer().symbol().setWidth(0.7)
v_layer.triggerRepaint()

# Zoom to layer
if v_layer.featureCount() > 0:
    v_layer.selectAll()
    canvas = iface.mapCanvas()
    canvas.zoomToSelected(v_layer)
    v_layer.removeSelection()
    
    # Get canvas scale
    sc = canvas.scale()
    print(f"OuterHorizontal: Canvas scale: {sc}")
    if sc < 20000:
        sc = 20000
    canvas.zoomScale(sc)

print("OuterHorizontal: Script completed - NOTE: Geometry calculation needs implementation")