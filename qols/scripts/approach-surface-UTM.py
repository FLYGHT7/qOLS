'''
Inner Approach Surface — supports RWY Classification and Code propagation to attributes
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

"""Parameter extraction
Prefers pythonic, UI-aligned names with backward-compatible fallbacks to legacy keys.
"""
try:
    # New pythonic names (preferred), with fallbacks to legacy keys
    runway_code = globals().get('runway_code', globals().get('code', 4))
    rwy_classification = globals().get('rwy_classification', globals().get('rwyClassification', 'Precision Approach CAT I'))
    approach_width_m = globals().get('approach_width_m', globals().get('widthApp', 280))
    start_elevation_m = globals().get('start_elevation_m', globals().get('Z0', 21.7))
    end_elevation_m = globals().get('end_elevation_m', globals().get('ZE', 21.7))
    arp_elevation_m = globals().get('arp_elevation_m', globals().get('ARPH', 29.3))
    first_section_length_m = globals().get('first_section_length_m', globals().get('L1', 3000))
    second_section_length_m = globals().get('second_section_length_m', globals().get('L2', 3600))
    horizontal_section_length_m = globals().get('horizontal_section_length_m', globals().get('LH', 8400))

    # Direction parameter: 0 for start→end, -1 for end→start
    direction = globals().get('direction', globals().get('s', 0))

    # Layer parameters
    runway_layer = globals().get('runway_layer', None)
    threshold_layer = globals().get('threshold_layer', None)
    use_selected_feature = globals().get('use_selected_feature', True)

    print(
        f"QOLS: Using parameters - runway_code: {runway_code}, rwy_classification: {rwy_classification}, "
        f"approach_width_m: {approach_width_m}, start_elevation_m: {start_elevation_m}, end_elevation_m: {end_elevation_m}"
    )
    print(f"QOLS: Direction: {direction}, Use selected features: {use_selected_feature}")

except Exception as e:
    print(f"QOLS: Error getting parameters, using defaults: {e}")
    # Sensible defaults
    runway_code = 4
    rwy_classification = 'Precision Approach CAT I'
    approach_width_m = 280
    start_elevation_m = 21.7
    end_elevation_m = 21.7
    arp_elevation_m = 29.3
    first_section_length_m = 3000
    second_section_length_m = 3600
    horizontal_section_length_m = 8400
    direction = 0
    runway_layer = None
    threshold_layer = None
    use_selected_feature = True

# Calculate derived parameters
zih_elevation_m = 45 + arp_elevation_m

print(f"QOLS: Final derived - zih_elevation_m: {zih_elevation_m}")
print(f"QOLS: Direction interpretation - direction={direction} means {'End to Start' if direction == -1 else 'Start to End'}")

map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()

# ENHANCED LAYER SELECTION - Use layers from UI
try:
    if runway_layer is not None:
        print(f"QOLS: Using runway layer from UI: {runway_layer.name()}")
        
        if use_selected_feature:
            # Require explicit feature selection
            selection = runway_layer.selectedFeatures()
            if not selection:
                raise Exception("No runway features selected. Please select runway features.")
            print(f"QOLS: Using {len(selection)} selected runway features")
        else:
            # Use all features (take first one)
            selection = list(runway_layer.getFeatures())
            if not selection:
                raise Exception("No features found in runway layer.")
            print(f"QOLS: Using first feature from layer (selection disabled)")
        
        print(f"QOLS: Processing {len(selection)} runway features")
        rwy_geom = selection[0].geometry()
        rwy_length = rwy_geom.length()
        rwy_slope = (start_elevation_m - end_elevation_m) / rwy_length if rwy_length > 0 else 0
        print(f"QOLS: Runway length: {rwy_length}, slope: {rwy_slope}")

    else:
        # No fallback - require explicit runway layer selection
        raise Exception("No runway layer provided. Please select a runway layer from the UI.")

except Exception as e:
    print(f"QOLS: Error with runway layer: {e}")
    iface.messageBar().pushMessage("QOLS Error", f"Runway layer error: {str(e)}", level=Qgis.Critical)
    raise

# Calculate ZIH at start (legacy name ZIHs)
zih_at_start_m = (start_elevation_m - ((start_elevation_m - end_elevation_m) / rwy_length) * 1800)
print(f"QOLS: ZIH at start (m): {zih_at_start_m}")

# Get the azimuth of the line - SIMPLIFIED LOGIC
for feat in selection:
    geom = feat.geometry().asPolyline()
    print(f"QOLS: Geometry points count: {len(geom)}")
    
    # Always use the same points regardless of direction
    # Direction change is handled by azimuth rotation only
    start_point = QgsPoint(geom[0])   # Always first point
    end_point = QgsPoint(geom[-1])    # Always last point
    base_azimuth_deg = start_point.azimuth(end_point)
    
    print(f"QOLS: Using consistent points regardless of direction")
    print(f"QOLS: start_point = geom[0] (first point)")
    print(f"QOLS: end_point = geom[-1] (last point)")
    print(f"QOLS: Start point: {start_point.x()}, {start_point.y()}")
    print(f"QOLS: End point: {end_point.x()}, {end_point.y()}")
    print(f"QOLS: Base azimuth (deg): {base_azimuth_deg}")

# Defer final azimuth until we know which threshold end is selected
print(f"QOLS: Base azimuth (start→end) will be adjusted based on selected threshold end and UI direction toggle")

# ENHANCED THRESHOLD SELECTION - Use threshold layer from UI
try:
    if threshold_layer is not None:
        print(f"QOLS: Using threshold layer from UI: {threshold_layer.name()}")
        
        if use_selected_feature:
            # Require explicit feature selection
            threshold_selection = threshold_layer.selectedFeatures()
            if not threshold_selection:
                raise Exception("No threshold features selected. Please select threshold features.")
            print(f"QOLS: Using {len(threshold_selection)} selected threshold features")
        else:
            # Use all features (take first one)
            threshold_selection = list(threshold_layer.getFeatures())
            if not threshold_selection:
                raise Exception("No features found in threshold layer.")
            print(f"QOLS: Using first threshold feature from layer (selection disabled)")
        
        print(f"QOLS: Processing {len(threshold_selection)} threshold features")
        
    else:
        # No fallback - require explicit threshold layer selection  
        raise Exception("No threshold layer provided. Please select a threshold layer from the UI.")

except Exception as e:
    print(f"QOLS: Error with threshold layer: {e}")
    iface.messageBar().pushMessage("QOLS Error", f"Threshold layer error: {str(e)}", level=Qgis.Critical)
    raise

# Get x,y from threshold - ORIGINAL LOGIC RESTORED
# Always use the selected threshold feature as-is, direction change is handled by azimuth only
if len(threshold_selection) >= 1:
    # Use the first (or only) threshold feature
    selected_threshold = threshold_selection[0]
    threshold_geom = selected_threshold.geometry().asPoint()
    print(f"QOLS: Using threshold feature as-is (original logic)")
else:
    raise Exception("No threshold features found")

new_geom = QgsPoint(threshold_geom)
new_geom.addZValue(start_elevation_m)

# Determine which runway end the selected threshold corresponds to
dist_to_start = hypot(new_geom.x() - start_point.x(), new_geom.y() - start_point.y())
dist_to_end = hypot(new_geom.x() - end_point.x(), new_geom.y() - end_point.y())
selected_end = 'start' if dist_to_start <= dist_to_end else 'end'

# Compute outward azimuth from the selected threshold end
outward_azimuth = base_azimuth_deg if selected_end == 'start' else (base_azimuth_deg + 180) % 360

# Apply UI direction toggle: 0 = Start→End, -1 = End→Start (flip 180)
azimuth = (outward_azimuth + (180 if direction == -1 else 0)) % 360

print(f"QOLS: Threshold point: {new_geom.x()}, {new_geom.y()}, {new_geom.z()}")
print(f"QOLS: Selected threshold end: {selected_end} (dist_start={dist_to_start:.2f}, dist_end={dist_to_end:.2f})")
print(f"QOLS: Base azimuth (start→end): {base_azimuth_deg:.6f}°")
print(f"QOLS: Outward azimuth from selected end: {outward_azimuth:.6f}°")
print(f"QOLS: UI direction toggle: {'End to Start' if direction == -1 else 'Start to End'}")
print(f"QOLS: Final azimuth used for projection: {azimuth:.6f}°")

construction_points = []

"""Dynamic section geometry
This block replaces previous hardcoded distances (3000, 6600, 15000) with UI-provided
first_section_length_m (L1), second_section_length_m (L2), horizontal_section_length_m (LH).
Additional dynamic parameters (with safe defaults if the UI does not yet expose them):
 - first_section_slope (default 0.02)
 - second_section_slope (default 0.025)
 - divergence_ratio (default 0.15) -> lateral growth per metre (both sides)
 - threshold_offset_m (default 60) -> distance from THR to section origin
Sections are omitted if their length is 0. Horizontal section starts after second (or first if second omitted).
"""

first_section_slope = globals().get('first_section_slope', globals().get('slope1', 0.02))
second_section_slope = globals().get('second_section_slope', globals().get('slope2', 0.025))
divergence_ratio = globals().get('divergence_ratio', globals().get('divergence', 0.15))
threshold_offset_m = globals().get('threshold_offset_m', globals().get('thr_offset', 60))

print(f"QOLS: Dynamic Approach Params -> L1={first_section_length_m} L2={second_section_length_m} LH={horizontal_section_length_m} slope1={first_section_slope} slope2={second_section_slope} div={divergence_ratio} thr_off={threshold_offset_m}")

# Guard against negative lengths
first_section_length_m = max(0, float(first_section_length_m))
second_section_length_m = max(0, float(second_section_length_m))
horizontal_section_length_m = max(0, float(horizontal_section_length_m))

# Origin (threshold point with elevation)
pt_0 = new_geom

# Point after threshold offset
pt_01 = new_geom.project(threshold_offset_m, azimuth)
pt_01.addZValue(start_elevation_m)
pt_01AL = pt_01.project(approach_width_m / 2, azimuth + 90)
pt_01AR = pt_01.project(approach_width_m / 2, azimuth - 90)

construction_points.extend((pt_0, pt_01, pt_01AL, pt_01AR))

features_to_create = []  # (id, name, [farRight, farLeft, nearLeft, nearRight])
next_id = 6

def lateral_offset(distance_from_offset: float) -> float:
    """Compute half-width at a given distance from pt_01 considering divergence."""
    return (approach_width_m / 2) + (distance_from_offset * divergence_ratio)

# --- First Section (always created if L1 > 0) ---
if first_section_length_m > 0:
    dist_first_end = first_section_length_m
    height_first_end = start_elevation_m + first_section_length_m * first_section_slope
    pt_05 = pt_01.project(dist_first_end, azimuth)
    pt_05.setZ(height_first_end)
    half_w_first_end = lateral_offset(dist_first_end)
    pt_05L = pt_05.project(half_w_first_end, azimuth + 90)
    pt_05R = pt_05.project(half_w_first_end, azimuth - 90)
    construction_points.extend((pt_05, pt_05L, pt_05R))
    features_to_create.append((next_id, 'Approach First Section', [pt_05R, pt_05L, pt_01AL, pt_01AR]))
    next_id += 1
else:
    # If L1 = 0 treat pt_05 as the origin of later sections
    dist_first_end = 0
    height_first_end = start_elevation_m
    pt_05 = pt_01  # reuse
    pt_05L = pt_01AL
    pt_05R = pt_01AR

# --- Second Section (optional) ---
if second_section_length_m > 0:
    dist_second_end = dist_first_end + second_section_length_m
    height_second_end = height_first_end + second_section_length_m * second_section_slope
    pt_06 = pt_01.project(dist_second_end, azimuth)
    pt_06.setZ(height_second_end)
    half_w_second_end = lateral_offset(dist_second_end)
    pt_06L = pt_06.project(half_w_second_end, azimuth + 90)
    pt_06R = pt_06.project(half_w_second_end, azimuth - 90)
    construction_points.extend((pt_06, pt_06L, pt_06R))
    features_to_create.append((next_id, 'Approach Second Section', [pt_06R, pt_06L, pt_05L, pt_05R]))
    next_id += 1
else:
    # If omitted, second section end coincides with first section end for horizontal start
    dist_second_end = dist_first_end
    height_second_end = height_first_end
    pt_06 = pt_05
    pt_06L = pt_05L
    pt_06R = pt_05R

# --- Horizontal Section (optional; only if second section exists) ---
if second_section_length_m > 0 and horizontal_section_length_m > 0:
    dist_horizontal_end = dist_second_end + horizontal_section_length_m
    pt_07 = pt_01.project(dist_horizontal_end, azimuth)
    pt_07.setZ(height_second_end)  # constant height
    half_w_horizontal_end = lateral_offset(dist_horizontal_end)
    pt_07L = pt_07.project(half_w_horizontal_end, azimuth + 90)
    pt_07R = pt_07.project(half_w_horizontal_end, azimuth - 90)
    construction_points.extend((pt_07, pt_07L, pt_07R))
    features_to_create.append((next_id, 'Approach Horizontal Section', [pt_07R, pt_07L, pt_06L, pt_06R]))
    next_id += 1

print(f"QOLS: Generated {len(construction_points)} construction points; sections created: {len(features_to_create)}")

# Creation of the Approach Surfaces
# Create memory layer
layer_name = f"RWY_ApproachSurface_{rwy_classification}_Code{runway_code}"
approach_layer = QgsVectorLayer("PolygonZ?crs="+map_srid, layer_name, "memory")
id_field = QgsField('ID', QVariant.String)
name_field = QgsField('SurfaceName', QVariant.String)
type_field = QgsField('SurfaceType', QVariant.String)
code_field = QgsField('Code', QVariant.Int)
rule_field = QgsField('rule_set', QVariant.String)
approach_layer.dataProvider().addAttributes([id_field, name_field, type_field, code_field, rule_field])
approach_layer.updateFields()

provider = approach_layer.dataProvider()
for fid, name, surface_area in features_to_create:
    feature = QgsFeature()
    feature.setGeometry(QgsPolygon(QgsLineString(surface_area), rings=[]))
    feature.setAttributes([fid, name, rwy_classification, runway_code, globals().get('active_rule_set', None)])
    provider.addFeatures([feature])

# Load PolygonZ Layer to map canvas 
QgsProject.instance().addMapLayers([approach_layer])

# Change style of layer 
approach_layer.renderer().symbol().setColor(QColor("green"))
approach_layer.renderer().symbol().setOpacity(0.4)
approach_layer.triggerRepaint()

# Zoom to layer
approach_layer.selectAll()
canvas = iface.mapCanvas()
canvas.zoomToSelected(approach_layer)
approach_layer.removeSelection()

# Clean up selections only if they weren't originally selected
# This prevents losing user selections for subsequent calculations
if not use_selected_feature:
    # Only clean up if we're not using selected features
    if runway_layer:
        runway_layer.removeSelection()
    if threshold_layer:
        threshold_layer.removeSelection()
else:
    # Keep selections for next calculation
    print("QOLS: Keeping feature selections for next calculation")

# Get canvas scale
sc = canvas.scale()
print(f"QOLS: Canvas scale: {sc}")
if sc < 20000:
    sc = 20000
canvas.zoomScale(sc)

print(f"QOLS: Approach surface calculation completed successfully")
print(f"QOLS: Created layer: {layer_name}")
print(f"QOLS: Surface type: {rwy_classification}, Code: {runway_code}, Width: {approach_width_m}m")

# Success message
iface.messageBar().pushMessage("QOLS Success", f"Approach Surface ({rwy_classification}, Code {runway_code}) calculated successfully", level=Qgis.Success)

# Clean up globals
set(globals().keys()).difference(myglobals)
for g in set(globals().keys()).difference(myglobals):
    if g != 'myglobals':
        del globals()[g]
