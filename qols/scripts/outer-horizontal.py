'''
Outer Horizontal Surface 
DOC 9137 Part 6 Implementation - 15,000m circle centered on ARP
For Aerodrome Code 3 or 4 only
Procedure to be used in Projected Coordinate System Only
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

# Get parameters from plugin
code = globals().get('code', 3)
radius = globals().get('radius', 15000.0)
height = globals().get('height', 45.0)

print(f"OuterHorizontal: Code={code}, Radius={radius}m, Height={height}m")

# Validate code number (DOC 9137 Part 6 - only for code 3 or 4)
if code not in [3, 4]:
    print(f"OuterHorizontal: WARNING - Code {code} not standard for outer horizontal (DOC 9137 requires code 3 or 4)")

# Get ARP (Aerodrome Reference Point) from threshold layer
threshold_layer = globals().get('threshold_layer')
use_selected_feature = globals().get('use_selected_feature', True)

if not threshold_layer:
    raise Exception("No threshold layer provided. Please select a threshold layer from the UI.")

# Get ARP coordinates - require explicit selection
if use_selected_feature:
    selection = threshold_layer.selectedFeatures()
    if not selection:
        raise Exception("No ARP (threshold) features selected. Please select ARP feature.")
    print(f"OuterHorizontal: Using {len(selection)} selected ARP features")
else:
    selection = list(threshold_layer.getFeatures())
    if not selection:
        raise Exception("No features found in threshold layer.")
    print(f"OuterHorizontal: Using first ARP feature from layer")

# Create memory layer for outer horizontal surface
v_layer = QgsVectorLayer(f"Polygon?crs={map_srid}", "Outer Horizontal Surface", "memory")
v_layer_provider = v_layer.dataProvider()

# Add attributes
v_layer_provider.addAttributes([
    QgsField("surface_type", QVariant.String),
    QgsField("code", QVariant.Int),
    QgsField("radius_m", QVariant.Double),
    QgsField("height_m", QVariant.Double),
    QgsField("arp_x", QVariant.Double),
    QgsField("arp_y", QVariant.Double)
])
v_layer.updateFields()

# Process each ARP point
features_created = 0
for feat in selection:
    arp_point = feat.geometry().asPoint()
    arp_x, arp_y = arp_point.x(), arp_point.y()
    print(f"OuterHorizontal: Creating circle at ARP: {arp_x}, {arp_y}")
    
    # Create circle geometry - 15,000m radius from ARP
    circle_points = []
    num_points = 72  # 5-degree intervals for smooth circle
    
    for i in range(num_points):
        angle = (i * 360.0 / num_points) * pi / 180.0  # Convert to radians
        x = arp_x + radius * cos(angle)
        y = arp_y + radius * sin(angle)
        circle_points.append(QgsPointXY(x, y))
    
    # Close the polygon
    circle_points.append(circle_points[0])
    
    # Create polygon geometry
    polygon = QgsGeometry.fromPolygonXY([circle_points])
    
    # Create feature
    feature = QgsFeature()
    feature.setGeometry(polygon)
    feature.setAttributes([
        "Outer Horizontal",
        code,
        radius,
        height,
        arp_x,
        arp_y
    ])
    
    # Add feature to layer
    v_layer_provider.addFeatures([feature])
    features_created += 1
    
    print(f"OuterHorizontal: Created circle with radius {radius}m at ARP ({arp_x:.2f}, {arp_y:.2f})")

v_layer.updateExtents()
print(f"OuterHorizontal: Created {features_created} outer horizontal surface(s)")

# Add to map
QgsProject.instance().addMapLayers([v_layer])

# Style the layer
symbol = QgsFillSymbol.createSimple({
    'color': '0,100,255,100',  # Blue with transparency
    'style': 'solid',
    'outline_color': '0,100,255,255',
    'outline_style': 'solid',
    'outline_width': '0.5'
})
v_layer.renderer().setSymbol(symbol)
v_layer.triggerRepaint()

# Zoom to layer
if features_created > 0:
    v_layer.selectAll()
    canvas = iface.mapCanvas()
    canvas.zoomToSelected(v_layer)
    v_layer.removeSelection()
    
    # Set appropriate scale for large circle
    sc = canvas.scale()
    print(f"OuterHorizontal: Canvas scale: {sc}")
    if sc < 50000:  # Adjusted for 15km radius
        sc = 50000
    canvas.zoomScale(sc)

print(f"OuterHorizontal: Completed - {features_created} outer horizontal surface(s) created per DOC 9137 Part 6")