"""
New OLS Concept — OFS Approach Surface
Single-section trapezoidal approach surface per ICAO New OLS concept.
Uses ADG group classification instead of current OLS classification + code.
Procedure to be used in Projected Coordinate System Only.
"""
myglobals = set(globals().keys())

from qgis.core import *
from qgis.PyQt.QtCore import *
from qgis.PyQt.QtGui import *
from math import sqrt, hypot
import json

_script_success = False


def _normalize_polyline_points(geometry):
    if geometry is None or geometry.isEmpty():
        raise Exception("Empty geometry provided for runway centerline.")
    if geometry.isMultipart():
        parts = geometry.asMultiPolyline()
        if not parts:
            raise Exception("Empty MultiLineString geometry.")

        def part_len(pts):
            if not pts or len(pts) < 2:
                return 0.0
            total = 0.0
            for i in range(1, len(pts)):
                dx = pts[i].x() - pts[i - 1].x()
                dy = pts[i].y() - pts[i - 1].y()
                total += sqrt(dx * dx + dy * dy)
            return total

        return [QgsPoint(p) for p in max(parts, key=part_len)]
    poly = geometry.asPolyline()
    if poly and len(poly) >= 2:
        return [QgsPoint(p) for p in poly]
    raise Exception("Line geometry cannot be converted to a polyline.")


# ---------------------------------------------------------------------------
# Parameter extraction
# ---------------------------------------------------------------------------
try:
    rwy_type = globals().get('rwy_type', 'Instrument')
    adg = globals().get('adg', 'III')
    runway_width_m = globals().get('runway_width_m', 45.0)
    distance_from_threshold_m = globals().get('distance_from_threshold_m', 60.0)
    inner_edge_m = globals().get('inner_edge_m', 175.0)
    divergence_ratio = globals().get('divergence_ratio', 0.10)
    length_m = globals().get('length_m', 4500.0)
    slope_pct = globals().get('slope_pct', 3.33)
    start_elevation_m = globals().get('start_elevation_m', 0.0)
    end_elevation_m = globals().get('end_elevation_m', 0.0)
    arp_elevation_m = globals().get('arp_elevation_m', 0.0)
    direction = globals().get('direction', 0)
    runway_layer = globals().get('runway_layer', None)
    threshold_layer = globals().get('threshold_layer', None)
    use_selected_feature = globals().get('use_selected_feature', True)
    contour_interval_m = int(globals().get('contour_interval_m', 0))

    slope_ratio = slope_pct / 100.0

    print(
        f"QOLS New OLS OFS: rwy_type={rwy_type}, adg={adg}, "
        f"inner_edge={inner_edge_m}m, length={length_m}m, "
        f"slope={slope_pct}%, dist_thr={distance_from_threshold_m}m"
    )
except Exception as e:
    print(f"QOLS New OLS OFS: Error getting parameters: {e}")
    raise

map_srid = iface.mapCanvas().mapSettings().destinationCrs().authid()

# ---------------------------------------------------------------------------
# Runway layer
# ---------------------------------------------------------------------------
try:
    if runway_layer is None:
        raise Exception("No Runway Layer Centerline provided.")
    if use_selected_feature:
        selection = runway_layer.selectedFeatures()
        if not selection:
            raise Exception("No runway features selected.")
    else:
        selection = runway_layer.selectedFeatures() or list(runway_layer.getFeatures())
        if not selection:
            raise Exception("No features found in Runway Layer.")
    rwy_geom = selection[0].geometry()
except Exception as e:
    iface.messageBar().pushMessage("QOLS Error", str(e), level=MSG_CRITICAL)
    raise

for feat in selection:
    line_pts = _normalize_polyline_points(feat.geometry())
    break

# ---------------------------------------------------------------------------
# Threshold layer
# ---------------------------------------------------------------------------
try:
    if threshold_layer is None:
        raise Exception("No threshold layer provided.")
    if use_selected_feature:
        threshold_sel = threshold_layer.selectedFeatures()
        if not threshold_sel:
            raise Exception("No threshold features selected.")
    else:
        threshold_sel = threshold_layer.selectedFeatures() or list(threshold_layer.getFeatures())
        if not threshold_sel:
            raise Exception("No features found in threshold layer.")
except Exception as e:
    iface.messageBar().pushMessage("QOLS Error", str(e), level=MSG_CRITICAL)
    raise


def _closest_feature(features, pt):
    return min(
        features,
        key=lambda f: hypot(f.geometry().asPoint().x() - pt.x(), f.geometry().asPoint().y() - pt.y()),
    )


# direction picks the runway-centerline endpoint directly (0 = Start to
# End, -1 = End to Start), mirroring the legacy TransitionalSurface_UTM.py
# line_pts[-1-s]/line_pts[s] convention — no threshold-distance matching or
# post-hoc azimuth flip needed.
s = direction
near_end_pt = line_pts[s]
far_end_pt = line_pts[-1 - s]
azimuth = far_end_pt.azimuth(near_end_pt)

# Anchored to the selected threshold (threshold_sel), same as legacy
# TransitionalSurface_UTM.py — direction changes azimuth (which way the
# surface points), not which threshold is used. In "Selected Only" mode
# with a single feature selected, re-selecting the matching threshold when
# toggling direction is the user's responsibility (same as legacy); in
# "All" mode threshold_sel already covers every feature, so the nearest
# match still follows direction automatically.
near_thr_feat = _closest_feature(threshold_sel, near_end_pt)
thr_geom = near_thr_feat.geometry().asPoint()
new_geom = QgsPoint(thr_geom)
new_geom.addZValue(start_elevation_m)

print(f"QOLS New OLS OFS: azimuth={azimuth:.2f}°, direction={direction}")

# ---------------------------------------------------------------------------
# Surface geometry — single trapezoidal section
# ---------------------------------------------------------------------------
pt_thr = new_geom

# Inner edge (at distance_from_threshold_m)
pt_inner = pt_thr.project(distance_from_threshold_m, azimuth)
pt_inner.setZ(start_elevation_m)
half_inner = inner_edge_m / 2.0
pt_inner_l = pt_inner.project(half_inner, azimuth + 90)
pt_inner_r = pt_inner.project(half_inner, azimuth - 90)

# Outer edge (at inner + length_m)
height_outer = start_elevation_m + length_m * slope_ratio
pt_outer = pt_inner.project(length_m, azimuth)
pt_outer.setZ(height_outer)
half_outer = half_inner + length_m * divergence_ratio
pt_outer_l = pt_outer.project(half_outer, azimuth + 90)
pt_outer_r = pt_outer.project(half_outer, azimuth - 90)

# Assign Z to corners
for pt, z in [
    (pt_inner_l, start_elevation_m), (pt_inner_r, start_elevation_m),
    (pt_outer_l, height_outer), (pt_outer_r, height_outer),
]:
    pt.addZValue(z) if not pt.is3D() else pt.setZ(z)

# ---------------------------------------------------------------------------
# Memory layer
# ---------------------------------------------------------------------------
layer_name = f"NewOLS_OFS_Approach_{rwy_type}_{adg}"
approach_layer = QgsVectorLayer("PolygonZ?crs=" + map_srid, layer_name, "memory")
approach_layer.dataProvider().addAttributes([
    QgsField('ID', QVariant.String),
    QgsField('SurfaceName', QVariant.String),
    QgsField('rwy_type', QVariant.String),
    QgsField('adg', QVariant.String),
    QgsField('slope_pct', QVariant.Double),
    QgsField('surface_start_elev', QVariant.Double),
    QgsField('surface_end_elev', QVariant.Double),
    QgsField('params_json', QVariant.String),
])
approach_layer.updateFields()

_params_json = json.dumps({
    'rwy_type': rwy_type,
    'adg': adg,
    'runway_width_m': runway_width_m,
    'inner_edge_m': inner_edge_m,
    'distance_from_threshold_m': distance_from_threshold_m,
    'divergence_pct': round(divergence_ratio * 100, 3),
    'length_m': length_m,
    'slope_pct': slope_pct,
    'start_elevation_m': round(start_elevation_m, 3),
    'end_elevation_m': round(end_elevation_m, 3),
})

feat = QgsFeature()
feat.setGeometry(QgsPolygon(QgsLineString([pt_inner_r, pt_inner_l, pt_outer_l, pt_outer_r, pt_inner_r])))
feat.setAttributes([
    '1', f'New OLS OFS Approach ({rwy_type} / ADG {adg})',
    rwy_type, adg, slope_pct,
    round(start_elevation_m, 3), round(height_outer, 3), _params_json,
])
approach_layer.dataProvider().addFeatures([feat])

QgsProject.instance().addMapLayers([approach_layer])
approach_layer.renderer().symbol().setColor(QColor("#FF69B4"))  # pink — matches diagram
approach_layer.renderer().symbol().setOpacity(0.4)
approach_layer.triggerRepaint()

approach_layer.selectAll()
canvas = iface.mapCanvas()
canvas.zoomToSelected(approach_layer)
approach_layer.removeSelection()
sc = canvas.scale()
if sc < 20000:
    sc = 20000
canvas.zoomScale(sc)

# ---------------------------------------------------------------------------
# Contour layer (optional)
# ---------------------------------------------------------------------------
if contour_interval_m > 0 and slope_ratio > 0:
    import importlib.util as _ilu
    import os as _os
    import sys as _sys
    _utils_path = _os.path.join(_os.path.dirname(__file__), '_contour_utils.py')
    _cu_spec = _ilu.spec_from_file_location('_contour_utils', _utils_path)
    _cu = _ilu.module_from_spec(_cu_spec)
    _sys.modules['_contour_utils'] = _cu
    _cu_spec.loader.exec_module(_cu)

    _elevs = _cu.contour_elevations(start_elevation_m, height_outer, contour_interval_m)
    _all_specs = _cu.contour_specs_for_linear_section(
        z_section_start=start_elevation_m,
        z_section_end=height_outer,
        slope=slope_ratio,
        d_offset=0.0,
        near_half_width=half_inner,
        divergence_ratio=divergence_ratio,
        elevations=_elevs,
    )
    if _all_specs:
        _clayer = QgsVectorLayer(
            "LineStringZ?crs=" + map_srid,
            f"NewOLS_OFS_Approach_Contours_{adg}",
            "memory",
        )
        _clayer.dataProvider().addAttributes([
            QgsField('ID', QVariant.Int),
            QgsField('surface_elevation', QVariant.Double),
        ])
        _clayer.updateFields()
        _cfeats = []
        for _i, _spec in enumerate(_all_specs):
            _ctr = pt_inner.project(_spec.distance_from_origin, azimuth)
            _l2d = _ctr.project(_spec.half_width, azimuth + 90)
            _r2d = _ctr.project(_spec.half_width, azimuth - 90)
            _lpt = QgsPoint(_l2d.x(), _l2d.y(), _spec.elevation)
            _rpt = QgsPoint(_r2d.x(), _r2d.y(), _spec.elevation)
            _cf = QgsFeature()
            _cf.setGeometry(QgsGeometry(QgsLineString([_lpt, _rpt])))
            _cf.setAttributes([_i + 1, _spec.elevation])
            _cfeats.append(_cf)
        _clayer.dataProvider().addFeatures(_cfeats)
        _cu.apply_contour_style(_clayer, __file__)
        QgsProject.instance().addMapLayers([_clayer])
        _clayer.triggerRepaint()
        print(f"QOLS New OLS OFS: {len(_cfeats)} contour lines at {contour_interval_m} m")

print(f"QOLS New OLS OFS: Approach surface created — {layer_name}")
iface.messageBar().pushMessage(
    "QOLS Success",
    f"New OLS OFS Approach ({rwy_type} / ADG {adg}) calculated successfully",
    level=MSG_SUCCESS,
)
_script_success = True

# Clean up globals
for _g in set(globals().keys()).difference(myglobals):
    if _g not in ('myglobals', '_script_success'):
        del globals()[_g]
