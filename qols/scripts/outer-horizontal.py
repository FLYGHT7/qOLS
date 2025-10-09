'''
Outer Horizontal Surface 
DOC 9137 Part 6 Implementation - 15,000m circle centered on ARP
For Aerodrome Code 3 or 4 only
Procedure to be used in Projected Coordinate System Only

Note: Plugin integration uses 'threshold_layer' parameter name for compatibility
with existing UI, but this script uses ARP (Aerodrome Reference Point) terminology
for clarity and DOC 9137 compliance.
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
# Note: Plugin parameter is still named 'threshold_layer' for compatibility,
# but we use descriptive variable name for better code documentation
aerodrome_reference_point_layer = globals().get('threshold_layer')
use_threshold_selected = globals().get('use_threshold_selected', False)

if not aerodrome_reference_point_layer:
    raise Exception("No ARP (Aerodrome Reference Point) layer provided. Please select a threshold layer from the UI.")

# Get ARP coordinates - use selection or all features based on UI setting
if use_threshold_selected:
    selection = aerodrome_reference_point_layer.selectedFeatures()
    if not selection:
        raise Exception("No ARP (Aerodrome Reference Point) features selected. Please select ARP feature.")
    print(f"OuterHorizontal: Using {len(selection)} selected ARP features")
else:
    selection = list(aerodrome_reference_point_layer.getFeatures())
    if not selection:
        raise Exception("No features found in ARP (Aerodrome Reference Point) layer.")
    print(f"OuterHorizontal: Using all {len(selection)} ARP features from layer")

# Create memory layer for outer horizontal surface
v_layer = QgsVectorLayer(f"Polygon?crs={map_srid}", "Outer Horizontal Surface", "memory")
v_layer_provider = v_layer.dataProvider()

# Add attributes
v_layer_provider.addAttributes([
    QgsField("surface_type", QVariant.String),
    QgsField("code", QVariant.Int),
    QgsField("radius_m", QVariant.Double),
    QgsField("height_m", QVariant.Double),
    QgsField("rule_set", QVariant.String),
    QgsField("arp_x", QVariant.Double),
    QgsField("arp_y", QVariant.Double)
])
v_layer.updateFields()

# Process each ARP point
features_created = 0
for feat in selection:
    arp_point = feat.geometry().asPoint()
    arp_x, arp_y = arp_point.x(), arp_point.y()
    print(f"OuterHorizontal: Creating 15,000m circle at ARP: {arp_x}, {arp_y}")
    
    # Create circular polygon using PyQGIS native QgsCircle (as requested by client)
    # Fix: Convert QgsPointXY to QgsPoint for QgsCircle compatibility
    center_point = QgsPoint(arp_x, arp_y)
    
    # Use PyQGIS native QgsCircle for precise geometry generation (DOC 9137 compliance)
    qgs_circle = QgsCircle(center_point, radius)
    
    # Convert circle to polygon with configurable precision
    # Note: Consider making this configurable in plugin settings for different precision needs
    num_segments = 360  # Increased from 72 as per client feedback
    polygon_geometry = qgs_circle.toPolygon(num_segments)
    
    # Convert to QgsGeometry
    circle_geometry = QgsGeometry(polygon_geometry)
    
    # Create feature with proper geometry reference
    feature = QgsFeature()
    feature.setGeometry(circle_geometry)
    feature.setAttributes([
        "Outer Horizontal",
        code,
        radius,
        height,
        globals().get('active_rule_set', None),
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