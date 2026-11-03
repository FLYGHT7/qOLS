"""ARP-centered Current OLS surfaces, built before publication to the project."""
from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Optional

from qgis.PyQt.QtCore import QVariant
from qgis.core import (
    QgsCircle, QgsCoordinateReferenceSystem, QgsCoordinateTransform, QgsFeature,
    QgsField, QgsFillSymbol, QgsGeometry, QgsLineString, QgsPoint, QgsPointXY,
    QgsPolygon, QgsProject, QgsVectorLayer,
)

from ..compat import DISTANCE_UNIT_METERS, GEOM_TYPE_POINT
from ..parameters_inspector import add_parameters_field, build_parameters_json
from ..scripts._contour_utils import (
    apply_contour_style, conical_contour_radius, contour_elevations,
)


@dataclass(frozen=True)
class CircleLayers:
    """Unregistered layers; the executor trims Conical before publishing."""

    inner_layer: QgsVectorLayer
    conical_layer: QgsVectorLayer
    contour_layer: Optional[QgsVectorLayer]


def _validate_output_crs(crs: QgsCoordinateReferenceSystem) -> None:
    if not crs.isValid() or crs.isGeographic() or crs.mapUnits() != DISTANCE_UNIT_METERS:
        raise ValueError("Circle (ARP) requires a valid projected output CRS in metres.")


def resolve_arp_center(
    arp_layer: Optional[QgsVectorLayer],
    use_selected: bool,
    output_crs: QgsCoordinateReferenceSystem,
) -> QgsPointXY:
    """Resolve exactly one effective ARP point into the output CRS."""
    _validate_output_crs(output_crs)
    if not isinstance(arp_layer, QgsVectorLayer) or not arp_layer.isValid():
        raise ValueError("Select a valid ARP point layer for Circle (ARP).")
    if QgsProject.instance().mapLayer(arp_layer.id()) is not arp_layer:
        raise ValueError("The ARP layer is no longer present in the current project.")
    if arp_layer.geometryType() != GEOM_TYPE_POINT:
        raise ValueError("The ARP layer must contain point geometry.")
    if not arp_layer.crs().isValid():
        raise ValueError("The ARP layer must have a valid CRS.")
    features = arp_layer.getSelectedFeatures() if use_selected else arp_layer.getFeatures()
    feature = next(features, None)
    if feature is None or next(features, None) is not None:
        raise ValueError("Circle (ARP) requires exactly one ARP point; select one or use a single-point layer.")
    geometry = feature.geometry()
    if geometry.isEmpty() or geometry.isMultipart():
        raise ValueError("The ARP feature must be a non-empty single Point, not MultiPoint.")
    point = geometry.asPoint()
    if not all(isfinite(value) for value in (point.x(), point.y())):
        raise ValueError("The ARP point coordinates must be finite.")
    # Same native transform pattern as other QGIS coordinate conversions.
    transform = QgsCoordinateTransform(arp_layer.crs(), output_crs, QgsProject.instance())
    center = transform.transform(QgsPointXY(point.x(), point.y()))
    if not all(isfinite(value) for value in (center.x(), center.y())):
        raise ValueError("The ARP cannot be transformed to finite output coordinates.")
    return center


def _finite_number(value: object, name: str, *, positive: bool = False) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValueError(f"{name} must be numeric.") from error
    if not isfinite(number) or (positive and number <= 0):
        qualifier = "finite and positive" if positive else "finite"
        raise ValueError(f"{name} must be {qualifier}.")
    return number


def _circle_points(center: QgsPointXY, radius: float, z: float) -> list[QgsPoint]:
    # Copy the QgsCircle.toPolygon(360) sampling used by outer-horizontal.py.
    polygon = QgsCircle(QgsPoint(center.x(), center.y()), radius).toPolygon(360)
    return [QgsPoint(point.x(), point.y(), z) for point in polygon.exteriorRing().vertices()]


def _polygon(center: QgsPointXY, radius: float, z: float) -> QgsGeometry:
    polygon = QgsPolygon()
    polygon.setExteriorRing(QgsLineString(_circle_points(center, radius, z)))
    return QgsGeometry(polygon)


def _surface_layer(
    name: str, surface: str, center: QgsPointXY, radius: float, height: float,
    z: float, datum: float, inner_height: float, code: int, classification: str,
    crs: QgsCoordinateReferenceSystem, rule_set: Optional[str],
    parameters: dict,
) -> QgsVectorLayer:
    layer = QgsVectorLayer("PolygonZ", name, "memory")
    layer.setCrs(crs)
    values = {
        "surface_type": surface, "radius_m": radius, "height_m": height,
        "datum_elevation_m": datum, "inner_height_m": inner_height,
        "rule_set": rule_set, "shape": "circle", "arp_x": center.x(),
        "arp_y": center.y(), "RWYType": classification, "Code": code,
    }
    string_fields = {"surface_type", "rule_set", "shape", "RWYType"}
    fields = [
        QgsField(key, QVariant.String if key in string_fields else
                 QVariant.Int if key == "Code" else QVariant.Double)
        for key in values
    ]
    provider = layer.dataProvider()
    provider.addAttributes(fields)
    layer.updateFields()
    add_parameters_field(layer)
    feature = QgsFeature(layer.fields())
    feature.setGeometry(_polygon(center, radius, z))
    for key, value in values.items():
        feature[key] = value
    feature["parameters"] = build_parameters_json(f"{surface} Surface", {
        **parameters, **values, "radius": radius,
        "output_crs": crs.authid() or crs.toWkt(),
    })
    if not provider.addFeatures([feature])[0]:
        raise ValueError(f"Could not create {surface} circle feature.")
    layer.updateExtents()
    color = "0,114,178" if surface == "Inner Horizontal" else "255,165,0"
    layer.renderer().setSymbol(QgsFillSymbol.createSimple({
        "color": f"{color},100", "style": "solid", "outline_color": f"{color},255",
        "outline_style": "solid", "outline_width": "0.7",
    }))
    return layer


def build_circle_layers(
    center: QgsPointXY,
    inner_params: dict,
    conical_params: dict,
    output_crs: QgsCoordinateReferenceSystem,
    active_rule_set: Optional[str] = None,
) -> CircleLayers:
    """Build a disk, outer disk and optional contours, without adding layers."""
    _validate_output_crs(output_crs)
    _finite_number(center.x(), "ARP X")
    _finite_number(center.y(), "ARP Y")
    radius = _finite_number(inner_params["radius"], "Inner Horizontal radius", positive=True)
    inner_height = _finite_number(inner_params["height"], "Inner Horizontal height", positive=True)
    height = _finite_number(conical_params["height"], "Conical height", positive=True)
    slope_pct = _finite_number(conical_params["slope"], "Conical slope", positive=True)
    datum = _finite_number(inner_params["datum_elevation"], "ARP elevation")
    conical_datum = _finite_number(conical_params["datum_elevation"], "Conical datum")
    if datum != conical_datum:
        raise ValueError("Both circular surfaces must use the same ARP elevation.")
    if _finite_number(conical_params["inner_height"], "Conical inner height") != inner_height:
        raise ValueError("Conical inner height must match Inner Horizontal height.")
    if _finite_number(conical_params["inner_radius"], "Conical inner radius") != radius:
        raise ValueError("Conical inner radius must match Inner Horizontal radius.")
    interval_value = _finite_number(conical_params.get("contour_interval_m", 0), "Contour interval")
    if interval_value < 0 or not interval_value.is_integer():
        raise ValueError("Contour interval must be a non-negative integer.")
    interval = int(interval_value)
    slope = _finite_number(slope_pct / 100, "Conical slope ratio", positive=True)
    outer_radius = _finite_number(radius + height / slope, "Conical radius", positive=True)
    bottom_z = _finite_number(datum + inner_height, "Inner Horizontal elevation")
    top_z = _finite_number(bottom_z + height, "Conical elevation")
    code = int(inner_params["code"])
    classification = str(inner_params["rwyClassification"])
    inner = _surface_layer(
        f"InnerHorizontal_{classification}_Code{code}", "Inner Horizontal", center,
        radius, inner_height, bottom_z, datum, inner_height, code, classification,
        output_crs, active_rule_set, inner_params,
    )
    conical = _surface_layer(
        f"Conical_{classification}_Code{code}", "Conical", center,
        outer_radius, height, top_z, datum, inner_height, code, classification,
        output_crs, active_rule_set, {
            **conical_params, "slope_pct": slope_pct, "inner_radius_m": radius,
            "contour_interval_m": interval,
        },
    )
    contour_layer = None
    elevations = [e for e in contour_elevations(bottom_z, top_z, interval) if e < top_z - 1e-6]
    if elevations:
        contour_layer = QgsVectorLayer("LineStringZ", "RWY_ConicalSurface_Contours", "memory")
        contour_layer.setCrs(output_crs)
        provider = contour_layer.dataProvider()
        provider.addAttributes([QgsField("ID", QVariant.Int), QgsField("surface_elevation", QVariant.Double)])
        contour_layer.updateFields()
        features = []
        for index, elevation in enumerate(elevations, 1):
            contour_radius = conical_contour_radius(elevation, bottom_z, radius, slope)
            feature = QgsFeature(contour_layer.fields())
            feature.setGeometry(QgsGeometry(QgsLineString(_circle_points(center, contour_radius, elevation))))
            feature.setAttributes([index, elevation])
            features.append(feature)
        if not provider.addFeatures(features)[0]:
            raise ValueError("Could not create Conical circle contours.")
        contour_layer.updateExtents()
        apply_contour_style(contour_layer, str(Path(__file__).resolve().parents[1] / "scripts" / "conical.py"),
                            label_font_size=16)
    return CircleLayers(inner, conical, contour_layer)
