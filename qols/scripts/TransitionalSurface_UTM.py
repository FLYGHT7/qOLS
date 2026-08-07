'''
Transitional Surface 
Procedure to be used in Projected Coordinate System Only
ENHANCED VERSION - Uses dynamic parameters from UI
'''
# flake8: noqa  # exec()-dispatched script; star imports intentional (see TD-03)
myglobals = set(globals().keys())

from qgis.core import *
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from qgis.gui import *
from math import sqrt


def _normalize_polyline_points(geometry: 'QgsGeometry', iface=None):
    """Return a list of QgsPoint representing a single polyline.
    Accepts LineString or MultiLineString; for MultiLineString picks the longest part.
    """
    if geometry is None or geometry.isEmpty():
        raise Exception("Empty geometry provided for runway centerline.")
    if geometry.isMultipart():
        parts = geometry.asMultiPolyline()
        if not parts:
            raise Exception("Empty MultiLineString geometry.")

        def length_of(pts):
            if not pts or len(pts) < 2:
                return 0.0
            total = 0.0
            for i in range(1, len(pts)):
                dx = pts[i].x() - pts[i-1].x()
                dy = pts[i].y() - pts[i-1].y()
                total += sqrt(dx*dx + dy*dy)
            return total
        longest = max(parts, key=length_of)
        if iface and len(parts) > 1:
            iface.messageBar().pushMessage("Transitional Info", "MultiLineString detected; using longest part as centerline.", level=MSG_INFO)
        return [QgsPoint(p) for p in longest]
    poly = geometry.asPolyline()
    if poly and len(poly) >= 2:
        return [QgsPoint(p) for p in poly]
    raise Exception("Line geometry cannot be converted to a polyline. Only single line or curve types are permitted.")


# Parameters - NOW COME FROM UI INSTEAD OF HARDCODED
# These parameters will be injected by the plugin
try:
    # Try to get parameters from plugin namespace
    code = globals().get('code', 4)
    rwyClassification = globals().get('rwyClassification', 'Precision Approach CAT I')
    widthApp = globals().get('widthApp', 280)
    Z0 = globals().get('Z0', 2548)
    ZE = globals().get('ZE', 2546.5)
    ARPH = globals().get('ARPH', 2548)
    L1 = globals().get('L1', 3000)
    L2 = globals().get('L2', 3600)
    LH = globals().get('LH', 8400)
    Tslope = globals().get('Tslope', 14.3/100)
    s = globals().get('s', 0)  # CRITICAL: Get runway direction from UI button
    merge_transitional = globals().get('merge_transitional', False)  # #121
    contour_interval_m = int(globals().get('contour_interval_m', 0))  # #122

    # Layer parameters
    runway_layer = globals().get('runway_layer', None)
    threshold_layer = globals().get('threshold_layer', None)
    use_runway_selected = globals().get('use_runway_selected', True)
    use_threshold_selected = globals().get('use_threshold_selected', True)

    print(f"TransitionalSurface: Using parameters - code: {code}, widthApp: {widthApp}, Z0: {Z0}, ZE: {ZE}")
    print(f"TransitionalSurface: CRITICAL - Runway direction parameter s: {s}, Use selected runway: {use_runway_selected}, Use selected threshold: {use_threshold_selected}")

except Exception as e:
    print(f"TransitionalSurface: Error getting parameters, using defaults: {e}")
    # Fallback to defaults if parameters not provided
    code = 4
    rwyClassification = 'Precision Approach CAT I'
    widthApp = 280
    Z0 = 2548
    ZE = 2546.5
    ARPH = 2548
    L1 = 3000
    L2 = 3600
    LH = 8400
    Tslope = 14.3/100
    s = 0
    merge_transitional = False
    contour_interval_m = 0
    runway_layer = None
    threshold_layer = None
    use_runway_selected = True
    use_threshold_selected = True

# Calculate derived parameters
ZIH = 45 + ARPH

# Calculate s2 based on direction
if s == -1:
    s2 = 180
else:
    s2 = 0

print(f"TransitionalSurface: Final values - s: {s}, s2: {s2}, ZIH: {ZIH}")
print(f"TransitionalSurface: Direction interpretation - s={s} means {'End to Start' if s == -1 else 'Start to End'}")

map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()

# ENHANCED LAYER SELECTION - Use layers from UI
try:
    if runway_layer is not None:
        print(f"TransitionalSurface: Using Runway Layer Centerline from UI: {runway_layer.name()}")

        if use_runway_selected:
            # Require explicit feature selection
            selection = runway_layer.selectedFeatures()
            if not selection:
                raise Exception("No runway features selected. Please select runway features.")
            print(f"TransitionalSurface: Using {len(selection)} selected runway features")
        else:
            selection = list(runway_layer.getFeatures())
            if not selection:
                raise Exception("No features found in Runway Layer Centerline.")
            print(f"TransitionalSurface: Using first feature from layer (selection disabled)")

        print(f"TransitionalSurface: Processing {len(selection)} runway features")
        rwy_geom = selection[0].geometry()
        rwy_length = rwy_geom.length()
        rwy_slope = (Z0-ZE)/rwy_length if rwy_length > 0 else 0

        print(f"TransitionalSurface: Runway length: {rwy_length}, slope: {rwy_slope}")

    else:
        # No fallback - require explicit Runway Layer Centerline selection
        raise Exception("No Runway Layer Centerline provided. Please select a Runway Layer Centerline from the UI.")

except Exception as e:
    print(f"TransitionalSurface: Error with Runway Layer Centerline: {e}")
    iface.messageBar().pushMessage("TransitionalSurface Error", f"Runway Layer Centerline error: {str(e)}", level=MSG_CRITICAL)
    raise

# Calculate ZIHs
ZIHs = ((Z0-((Z0-ZE)/rwy_length)*1800))
print(f"TransitionalSurface: ZIHs calculated: {ZIHs}")


# Get the azimuth of the line - ORIGINAL SIMPLE LOGIC
for feat in selection:
    line_pts = _normalize_polyline_points(feat.geometry(), iface)
    print(f"TransitionalSurface: Geometry points count (normalized): {len(line_pts)}")

    # ORIGINAL LOGIC - SIMPLE AND WORKING
    start_point = line_pts[-1-s]
    end_point = line_pts[s]
    angle0 = start_point.azimuth(end_point)

    print(f"TransitionalSurface: start_point index: {-1-s}, end_point index: {s}")
    print(f"TransitionalSurface: start_point: {start_point.x()}, {start_point.y()}")
    print(f"TransitionalSurface: end_point: {end_point.x()}, {end_point.y()}")
    print(f"TransitionalSurface: angle0: {angle0}")
    break

# ENHANCED THRESHOLD SELECTION - Use threshold layer from UI
try:
    if threshold_layer is not None:
        print(f"TransitionalSurface: Using threshold layer from UI: {threshold_layer.name()}")

        if use_threshold_selected:
            # Require explicit feature selection
            threshold_selection = threshold_layer.selectedFeatures()
            if not threshold_selection:
                raise Exception("No threshold features selected. Please select threshold features.")
            print(f"TransitionalSurface: Using {len(threshold_selection)} selected threshold features")
        else:
            threshold_selection = list(threshold_layer.getFeatures())
            if not threshold_selection:
                raise Exception("No features found in threshold layer.")
            print(f"TransitionalSurface: Using first threshold feature from layer (selection disabled)")

        print(f"TransitionalSurface: Processing {len(threshold_selection)} threshold features")

    else:
        # No fallback - require explicit threshold layer selection
        raise Exception("No threshold layer provided. Please select a threshold layer from the UI.")

except Exception as e:
    print(f"TransitionalSurface: Error with threshold layer: {e}")
    iface.messageBar().pushMessage("TransitionalSurface Error", f"Threshold layer error: {str(e)}", level=MSG_CRITICAL)
    raise

# Get x,y from threshold - ENHANCED LOGIC FOR AUTO-DIRECTION
if len(threshold_selection) >= 1:
    selected_threshold = threshold_selection[0]
    threshold_geom = selected_threshold.geometry().asPoint()
    print(f"TransitionalSurface: Using selected threshold at: {threshold_geom.x()}, {threshold_geom.y()}")
else:
    raise Exception("No threshold features found")

new_geom = QgsPoint(threshold_geom)
new_geom.addZValue(Z0)

print(f"TransitionalSurface: Threshold point: {new_geom.x()}, {new_geom.y()}, {new_geom.z()}")

# RUNWAY DIRECTION LOGIC - Literally use runway from different direction
# s = 0: Normal runway direction (geom[-1] to geom[0])
# s = -1: Inverted runway direction (geom[0] to geom[-1])
# This is like looking at the runway from the opposite end

print(f"TransitionalSurface: Runway direction parameter s={s}")
print(f"TransitionalSurface: s=0 means normal direction, s=-1 means inverted direction")

# Use original runway point selection logic - this LITERALLY inverts the runway
start_point = line_pts[-1-s]
end_point = line_pts[s]
angle0 = start_point.azimuth(end_point)

print(f"TransitionalSurface: Start point index: {-1-s}, End point index: {s}")
print(f"TransitionalSurface: Start point: {start_point.x()}, {start_point.y()}")
print(f"TransitionalSurface: End point: {end_point.x()}, {end_point.y()}")
print(f"TransitionalSurface: Runway azimuth: {angle0}")

# Calculate azimuth - NO additional rotation needed, runway inversion handles it
azimuth = angle0  # Use the azimuth directly from inverted runway
bazimuth = azimuth + 180

print(f"TransitionalSurface: Final azimuth: {azimuth}")
print(f"TransitionalSurface: Final back azimuth: {bazimuth}")

# Normalize azimuths to 0-360 degree range (CRITICAL for correct calculations)
while azimuth < 0:
    azimuth += 360
while azimuth >= 360:
    azimuth -= 360

while bazimuth < 0:
    bazimuth += 360
while bazimuth >= 360:
    bazimuth -= 360

print(f"TransitionalSurface: Raw azimuth: {angle0 + s2}, normalized: {azimuth}")
print(f"TransitionalSurface: Raw bazimuth: {azimuth + 180}, normalized: {bazimuth}")
print(f"TransitionalSurface: Final azimuth: {azimuth}, bazimuth: {bazimuth}")

list_pts = []

# Origin
pt_0= new_geom

# Distance prior from THR (60 m)
pt_01= new_geom.project(60,azimuth)
pt_01.addZValue(Z0)
# print (pt_01)
pt_01AL = pt_01.project(widthApp/2,azimuth+90)
pt_01AR = pt_01.project(widthApp/2,azimuth-90)
pt_01TL = pt_01.project(widthApp/2+(ZIH-Z0)/Tslope,azimuth+90)
pt_01TL.setZ(ZIH)
pt_01TR = pt_01.project(widthApp/2+(ZIH-Z0)/Tslope,azimuth-90)
pt_01TR.setZ(ZIH)

# Point in Approach First Section where Inner Horizontal Height Reached
dIH = (ZIH - Z0)/(2/100)
pt_08= pt_01.project(dIH,azimuth)
pt_08.setZ(Z0+dIH*0.02)  # Could be ZO directly but for checking this is left
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
# Create memory layer (always fresh - #121 individual layer is untouched
# by merging; see the separate "Merged Transitional Surface" block below)

# Store the full input parameter set as HTML-inspectable JSON (#118)
from qols.parameters_inspector import build_parameters_json, add_parameters_field, register_parameters_action

_active_rule_set = globals().get('active_rule_set', None)
_params_json = build_parameters_json('Transitional Surface', {
    'code': code,
    'rwy_classification': rwyClassification,
    'widthApp': widthApp,
    'Z0': Z0,
    'ZE': ZE,
    'ARPH': ARPH,
    'Tslope': Tslope,
    'direction': s,
    'rule_set': _active_rule_set,
})

new_left_geom = QgsGeometry(QgsPolygon(QgsLineString([pt_08L,pt_01TL,pt_02TL,pt_02L,pt_01AL]), rings=[]))
new_right_geom = QgsGeometry(QgsPolygon(QgsLineString([pt_08R,pt_01TR,pt_02TR,pt_02R,pt_01AR]), rings=[]))

v_layer = QgsVectorLayer("PolygonZ?crs="+map_srid, "RWY_Transition Surface", "memory")
IDField = QgsField( 'ID', QVariant.String)
NameField = QgsField( 'SurfaceName', QVariant.String)
RuleField = QgsField( 'rule_set', QVariant.String)
v_layer.dataProvider().addAttributes([IDField])
v_layer.dataProvider().addAttributes([NameField])
v_layer.dataProvider().addAttributes([RuleField])
v_layer.updateFields()
add_parameters_field(v_layer)

# Left Transition Surface
pr = v_layer.dataProvider()
seg = QgsFeature()
seg.setGeometry(new_left_geom)
seg.setAttributes([10,'Left Transitional Surface', _active_rule_set, _params_json])
pr.addFeatures( [ seg ] )

# Right Transition Surface
seg = QgsFeature()
seg.setGeometry(new_right_geom)
seg.setAttributes([11,'Right Transitional Surface', _active_rule_set, _params_json])
pr.addFeatures( [ seg ] )

register_parameters_action(v_layer)
QgsProject.instance().addMapLayers([v_layer])

# -----------------------------------------------------------------------
# Merged Transitional Surface (#121) - a SEPARATE layer, maintained only
# when requested. Dissolves purely by spatial overlap (never by matching
# "Left"/"Right" names - a direction flip can swap which physical side
# ends up called which, so name-based pairing glues the wrong sides
# together). The individual layer above is never touched by this.
# -----------------------------------------------------------------------
if merge_transitional:
    from qols.geometry_merge import dissolve_geometries_preserving_z

    merged_matches = QgsProject.instance().mapLayersByName('Merged Transitional Surface')
    print(f"TransitionalSurface: merge_transitional=True, found {len(merged_matches)} "
          f"existing 'Merged Transitional Surface' layer(s)")
    merged_layer = None
    skip_merge = False
    if len(merged_matches) == 1:
        merged_layer = merged_matches[0]
    elif len(merged_matches) > 1:
        skip_merge = True
        iface.messageBar().pushMessage(
            "TransitionalSurface Warning",
            "Multiple 'Merged Transitional Surface' layers found; cannot tell which to "
            "accumulate into. Keep only one such layer for merging to work.",
            level=MSG_WARNING)

    if not skip_merge:
        existing_geoms = [f.geometry() for f in merged_layer.getFeatures()] if merged_layer else []
        print(f"TransitionalSurface: {len(existing_geoms)} existing merged geometrie(s) "
              f"carried into this dissolve")
        # dissolve_geometries_preserving_z needs >= 2 geometries; this run's
        # own Left+Right (which never overlap each other) always supplies
        # that, so the first click (no existing_geoms yet) still works -
        # it just dissolves this run's own two geometries against
        # themselves, trivially recovering their own original Z.
        dissolved_parts = dissolve_geometries_preserving_z(
            existing_geoms + [new_left_geom, new_right_geom]
        )
    else:
        dissolved_parts = []

    if dissolved_parts:
        if merged_layer is None:
            merged_layer = QgsVectorLayer(
                "MultiPolygonZ?crs=" + map_srid, "Merged Transitional Surface", "memory")
            merged_layer.dataProvider().addAttributes([
                QgsField('ID', QVariant.Int),
                QgsField('SurfaceName', QVariant.String),
                QgsField('rule_set', QVariant.String),
            ])
            merged_layer.updateFields()
            add_parameters_field(merged_layer)
            register_parameters_action(merged_layer)
            QgsProject.instance().addMapLayers([merged_layer])
            # #121: this is the first run contributing to the merge - remind
            # the user the checkbox must stay checked for every OTHER run
            # they still want folded in, not just this one.
            iface.messageBar().pushMessage(
                "Merged Transitional Surface",
                "Layer created. Keep 'Create/update Merged Transitional Surface layer' "
                "checked on every run (direction/params) you want included - it's not "
                "enough to check it only on the last one.",
                level=MSG_INFO, duration=8)

        mpr = merged_layer.dataProvider()
        mpr.deleteFeatures([f.id() for f in merged_layer.getFeatures()])
        merged_feats = []
        for _i, _part in enumerate(dissolved_parts):
            _feat = QgsFeature(merged_layer.fields())
            _feat.setGeometry(_part)
            _feat.setAttributes([_i + 1, 'Transitional Surfaces', _active_rule_set, _params_json])
            merged_feats.append(_feat)
        mpr.addFeatures(merged_feats)
        merged_layer.updateExtents()

        merged_layer.renderer().symbol().setColor(QColor("magenta"))
        merged_layer.renderer().symbol().setOpacity(0.4)
        merged_layer.triggerRepaint()

# Change style of layer
v_layer.renderer().symbol().setColor(QColor("magenta"))
v_layer.renderer().symbol().setOpacity(0.4)
v_layer.triggerRepaint()

# Zoom to layer
v_layer.selectAll()
canvas = iface.mapCanvas()
canvas.zoomToSelected(v_layer)
v_layer.removeSelection()
# Clean up selections only if they weren't originally selected
# This prevents losing user selections for subsequent calculations
if not use_runway_selected and 'runway_layer' in locals() and runway_layer:
    runway_layer.removeSelection()
if not use_threshold_selected and 'threshold_layer' in locals() and threshold_layer:
    threshold_layer.removeSelection()
# get canvas scale
sc = canvas.scale()
print (sc)
if sc < 20000:
   sc=20000
else:
    sc=sc
print (sc)
canvas.zoomScale(sc)


iface.messageBar().pushMessage("QPANSOPY:", "Transitional Surface Calculation Finished", level=MSG_SUCCESS)

# -----------------------------------------------------------------------
# Contour layer (#122 — stepped elevation bands for Transitional Surface)
# Independent of merge_transitional: always computed fresh from this
# run's own pentagon vertices, exactly like Approach/Take-off recompute
# their own contours every run.
# -----------------------------------------------------------------------
if contour_interval_m > 0:
    import importlib.util as _ilu
    import os as _os
    import sys as _sys
    _utils_path = _os.path.join(_os.path.dirname(__file__), '_contour_utils.py')
    _cu_spec = _ilu.spec_from_file_location('_contour_utils', _utils_path)
    _cu = _ilu.module_from_spec(_cu_spec)
    _sys.modules['_contour_utils'] = _cu
    _cu_spec.loader.exec_module(_cu)

    _z_bottom = min(Z0, ZE)
    _elevs = _cu.contour_elevations(_z_bottom, ZIH, contour_interval_m)
    # Exclude the plateau level itself - it's the flat 3-vertex boundary
    # (pt_08*/pt_01T*/pt_02T*), not a straight chord between two points.
    _elevs = [e for e in _elevs if e < ZIH - 1e-6]

    _verts_left = [(p.x(), p.y(), p.z()) for p in (pt_08L, pt_01TL, pt_02TL, pt_02L, pt_01AL)]
    _verts_right = [(p.x(), p.y(), p.z()) for p in (pt_08R, pt_01TR, pt_02TR, pt_02R, pt_01AR)]

    _specs_left = _cu.contour_specs_for_polygon_slice(_verts_left, _elevs)
    _specs_right = _cu.contour_specs_for_polygon_slice(_verts_right, _elevs)
    _all_specs = _specs_left + _specs_right

    if _all_specs:
        _clayer = QgsVectorLayer(
            "LineStringZ?crs=" + map_srid, "RWY_TransitionalSurface_Contours", "memory")
        _clayer.dataProvider().addAttributes([
            QgsField('ID', QVariant.Int),
            QgsField('surface_elevation', QVariant.Double),
        ])
        _clayer.updateFields()

        _cfeats = []
        for _i, (_elev, (_x1, _y1), (_x2, _y2)) in enumerate(_all_specs):
            _p1 = QgsPoint(_x1, _y1, _elev)
            _p2 = QgsPoint(_x2, _y2, _elev)
            _cfeat = QgsFeature()
            _cfeat.setGeometry(QgsGeometry(QgsLineString([_p1, _p2])))
            _cfeat.setAttributes([_i + 1, _elev])
            _cfeats.append(_cfeat)
        _clayer.dataProvider().addFeatures(_cfeats)

        _cu.apply_contour_style(_clayer, __file__)
        QgsProject.instance().addMapLayers([_clayer])
        _clayer.triggerRepaint()
        print(f"TransitionalSurface: Contour layer added - {len(_cfeats)} lines at "
              f"{contour_interval_m} m interval")
    else:
        print(f"TransitionalSurface: No contour lines - no elevation levels in range "
              f"for interval {contour_interval_m} m")

_script_success = True

set(globals().keys()).difference(myglobals)

for g in set(globals().keys()).difference(myglobals):
    if g not in ('myglobals', '_script_success'):
        del globals()[g]
