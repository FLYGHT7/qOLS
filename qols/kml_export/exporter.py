"""qols/kml_export/exporter.py — QGIS-aware KML export orchestration (#153).

The QGIS-aware counterpart to ``colors.py``/``html_table.py``/
``xml_mutate.py``: layer/renderer introspection, geometry densification,
``QgsVectorFileWriter`` export, and ``QSettings`` persistence, mirroring
the pure/QGIS-aware split used in ``qols/direction_marker.py``.
``run_kml_export(iface)`` is the single entry point ``plugin.py`` calls.

Ported from the reporter's reference script (``ols_2_kml_v8.py``, #153),
with two deliberate behavior changes beyond straight porting:
- ``iface._last_kml_export_dir`` (a monkeypatched attribute on the QGIS
  interface singleton) is replaced with ``QSettings``, mirroring the
  existing precedent in ``qols/rules/manager.py``
  (``get_active_rule_set_name``/``set_active_rule_set_name``).
- An empty layer-tree selection now shows a message-bar warning and
  returns, instead of the script's bare ``raise RuntimeError`` (which
  would surface as an ugly crash from a plugin menu action).
"""
from __future__ import annotations

import math
import os
import tempfile
import xml.etree.ElementTree as ET  # nosec B405 - self-written KML only, not external input
from dataclasses import dataclass
from typing import List, Optional, Tuple

import processing
from qgis.core import (
    QgsCoordinateReferenceSystem,
    QgsCoordinateTransformContext,
    QgsVectorFileWriter,
)
from qgis.PyQt.QtCore import QSettings, QUrl
from qgis.PyQt.QtGui import QColor

from .. import logger
from ..compat import (
    DIALOG_ACCEPTED,
    DISTANCE_UNIT_DEGREES,
    FILE_ACTION_CREATE_OR_OVERWRITE,
    MSG_CRITICAL,
    MSG_SUCCESS,
    MSG_WARNING,
    SYMBOLOGY_NO_SYMBOLOGY,
    WRITER_NO_ERROR,
)
from .colors import FILL_ALPHA, OUTLINE_ALPHA
from .xml_mutate import (
    FeatureMetadata,
    KmlAltitudeSummary,
    postprocess_kml_tree,
    validate_kml_altitudes,
)

__all__ = [
    "AUTOMATIC_FIELD_OPTION",
    "ELEV_FIELD",
    "DEFAULT_Z",
    "KmlExportOptions",
    "KmlExportResult",
    "collect_selected_layers",
    "union_of_field_names",
    "resolve_label_field",
    "extract_layer_color_map",
    "get_color_for_feature",
    "densify_layer",
    "write_layer_to_kml",
    "build_feature_metadata",
    "export_layer",
    "run_kml_export",
    "get_last_output_dir",
    "set_last_output_dir",
]

AUTOMATIC_FIELD_OPTION = "[Automatic / Default]"
ELEV_FIELD = "elev_m"
# Fallback altitude (metres, absolute) used only for genuinely 2-D geometries
# without a usable ``elev_m`` attribute. Finite geometry Z always wins (#153).
DEFAULT_Z = 0

_AUTO_LABEL_FIELD_NAMES = ("name", "label", "title", "id")
_LAST_DIR_SETTINGS_KEY = "QOLS/KmlExportLastDir"


@dataclass
class KmlExportOptions:
    output_dir: str
    label_field: Optional[str]
    group_by_label: bool
    theme: str
    densify_interval: float


@dataclass(frozen=True)
class KmlExportResult:
    """Successful, altitude-validated export of one QGIS layer."""

    layer_name: str
    path: str
    altitude: KmlAltitudeSummary


def get_last_output_dir() -> str:
    """Reads the last-used export directory from QSettings, defaulting to home."""
    try:
        settings = QSettings()
        value = settings.value(_LAST_DIR_SETTINGS_KEY, type=str)
        return value or os.path.expanduser("~")
    except Exception as e:
        logger.warning(f"get_last_output_dir failed: {e}")
        return os.path.expanduser("~")


def set_last_output_dir(path: str) -> None:
    """Persists the last-used export directory to QSettings."""
    try:
        settings = QSettings()
        settings.setValue(_LAST_DIR_SETTINGS_KEY, path)
    except Exception as e:
        logger.warning(f"set_last_output_dir failed: {e}")


def collect_selected_layers(iface) -> list:
    """Returns the valid layers currently selected in the QGIS Layers panel."""
    return [lyr for lyr in iface.layerTreeView().selectedLayers() if lyr.isValid()]


def union_of_field_names(layers) -> List[str]:
    """Returns the sorted union of field names across all *layers*."""
    names = set()
    for layer in layers:
        names.update(f.name() for f in layer.fields())
    return sorted(names)


def resolve_label_field(layer, chosen_field: Optional[str]) -> Optional[str]:
    """Resolves the label/name field for *layer*: the explicit *chosen_field*
    if it exists on this layer, else the first of name/label/title/id
    (case-insensitive), else None."""
    layer_field_names = [f.name() for f in layer.fields()]
    if chosen_field and chosen_field != AUTOMATIC_FIELD_OPTION:
        if chosen_field in layer_field_names:
            return chosen_field
        logger.warning(
            f"Field '{chosen_field}' not found in layer '{layer.name()}'. "
            "Falling back to automatic selection.")
    for fn in layer_field_names:
        if fn.lower() in _AUTO_LABEL_FIELD_NAMES:
            return fn
    return None


def extract_layer_color_map(layer):
    """Inspects *layer*'s renderer, returning ``(color_info, mode)`` where
    ``mode`` is one of ``"single"``/``"categorized"``/``"graduated"``."""
    renderer = layer.renderer()
    if not renderer:
        return QColor("#ffffff"), "single"

    r_type = renderer.type()

    if r_type == "singleSymbol":
        sym = renderer.symbol()
        col = sym.color() if sym else QColor("#ffffff")
        return col, "single"

    if r_type == "categorizedSymbol":
        attr_name = renderer.classAttribute()
        cat_map = {}
        for cat in renderer.categories():
            c_val = str(cat.value()) if cat.value() is not None else ""
            sym = cat.symbol()
            col = sym.color() if sym else QColor("#ffffff")
            cat_map[c_val] = col
        return (attr_name, cat_map), "categorized"

    if r_type == "graduatedSymbol":
        attr_name = renderer.classAttribute()
        ranges = []
        for rng in renderer.ranges():
            sym = rng.symbol()
            col = sym.color() if sym else QColor("#ffffff")
            ranges.append((rng.lowerValue(), rng.upperValue(), col))
        return (attr_name, ranges), "graduated"

    return QColor("#ffffff"), "single"


def get_color_for_feature(feat, color_info, mode) -> QColor:
    """Looks up the fill color for *feat* given ``extract_layer_color_map``'s output."""
    if mode == "single":
        return color_info if color_info is not None else QColor("#ffffff")

    if mode == "categorized":
        attr_name, cat_map = color_info
        if attr_name in feat.fields().names():
            val = str(feat[attr_name]) if feat[attr_name] is not None else ""
            return cat_map.get(val, QColor("#ffffff"))
        return QColor("#ffffff")

    if mode == "graduated":
        attr_name, ranges = color_info
        if attr_name in feat.fields().names() and feat[attr_name] is not None:
            try:
                num_val = float(feat[attr_name])
                for low, high, col in ranges:
                    if low <= num_val <= high:
                        return col
            except (ValueError, TypeError):
                pass
        return QColor("#ffffff")

    return QColor("#ffffff")


def densify_layer(layer, interval_meters: float):
    """Densifies *layer*'s geometry vertices by *interval_meters*, returning an in-memory layer."""
    crs = layer.crs()
    if crs.mapUnits() == DISTANCE_UNIT_DEGREES:
        interval = interval_meters / 111320.0
    else:
        interval = interval_meters

    result = processing.run("native:densifygeometriesbyinterval", {
        'INPUT': layer,
        'INTERVAL': interval,
        'OUTPUT': 'memory:',
    })
    return result['OUTPUT']


def write_layer_to_kml(layer, kml_path: str) -> Optional[str]:
    """Writes *layer* to *kml_path* as KML, reprojected to EPSG:4326.
    Returns an error message on failure, or None on success."""
    options = QgsVectorFileWriter.SaveVectorOptions()
    options.driverName = "KML"
    options.layerName = layer.name()
    options.symbologyExport = SYMBOLOGY_NO_SYMBOLOGY
    options.actionOnExistingFile = FILE_ACTION_CREATE_OR_OVERWRITE
    options.fileEncoding = 'UTF-8'
    options.datasourceOptions = ["AltitudeMode=absolute"]
    options.sourceCrs = layer.crs()
    options.destCrs = QgsCoordinateReferenceSystem("EPSG:4326")

    result, err_msg = QgsVectorFileWriter.writeAsVectorFormatV2(
        layer, kml_path, QgsCoordinateTransformContext(), options)
    return None if result == WRITER_NO_ERROR else err_msg


def _geometry_z_profile(feature, fallback_z: float) -> Tuple[bool, float, float]:
    """Returns whether source Z exists and the expected exported Z range."""
    z_values = []
    has_geometry_z = False
    for vertex in feature.geometry().vertices():
        z_value = float(vertex.z())
        if math.isfinite(z_value):
            has_geometry_z = True
            z_values.append(z_value)
        else:
            z_values.append(fallback_z)
    if not z_values:
        z_values.append(fallback_z)
    return has_geometry_z, min(z_values), max(z_values)


def _attribute_fallback_z(feature, has_elev_field: bool) -> float:
    """Returns a finite ``elev_m`` fallback, otherwise sea level."""
    if not has_elev_field or feature[ELEV_FIELD] is None:
        return float(DEFAULT_Z)
    try:
        fallback_z = float(feature[ELEV_FIELD])
    except (TypeError, ValueError):
        return float(DEFAULT_Z)
    return fallback_z if math.isfinite(fallback_z) else float(DEFAULT_Z)


def build_feature_metadata(
    layer_fields,
    features,
    label_field,
    color_info,
    mode,
) -> List[FeatureMetadata]:
    """Builds the per-feature metadata list ``xml_mutate.postprocess_kml_tree`` expects.

    Finite per-vertex geometry Z has priority. A usable ``elev_m`` attribute is
    retained only as the fallback for a genuinely 2-D feature; otherwise 0 m is
    used. The expected range lets the finished KML be checked against the
    densified source instead of assuming the writer preserved altitude.
    """
    field_names = [f.name() for f in layer_fields]
    has_elev_field = ELEV_FIELD in field_names

    metadata = []
    for feat in features:
        fallback_z = _attribute_fallback_z(feat, has_elev_field)
        has_geometry_z, expected_z_min, expected_z_max = _geometry_z_profile(
            feat, fallback_z)

        fill_color = get_color_for_feature(feat, color_info, mode)
        rgb = (fill_color.red(), fill_color.green(), fill_color.blue())

        if label_field and label_field in field_names:
            value = feat[label_field]
            label = str(value) if value is not None else f"Feature #{feat.id()}"
        else:
            label = f"Feature #{feat.id()}"

        attributes = {fn: ("" if feat[fn] is None else str(feat[fn])) for fn in field_names}

        metadata.append({
            "name": label,
            "attributes": attributes,
            "fill_rgba": rgb + (FILL_ALPHA,),
            "outline_rgba": rgb + (OUTLINE_ALPHA,),
            "has_geometry_z": has_geometry_z,
            "fallback_z": fallback_z,
            "expected_z_min": expected_z_min,
            "expected_z_max": expected_z_max,
            "label": label,
        })
    return metadata


def _sanitize_layer_name(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name)


def _format_altitude_range(altitude: KmlAltitudeSummary) -> str:
    if math.isclose(altitude.minimum_z, altitude.maximum_z, rel_tol=0.0, abs_tol=1e-6):
        return f"{altitude.minimum_z:.2f} m AMSL"
    return f"{altitude.minimum_z:.2f}–{altitude.maximum_z:.2f} m AMSL"


def export_layer(iface, layer, options: KmlExportOptions) -> Optional[KmlExportResult]:
    """Exports and validates one layer, returning its path and altitude range."""
    from .dialog import resolve_output_conflict

    target_name_field = resolve_label_field(layer, options.label_field)

    kml_path = os.path.join(options.output_dir, f"{_sanitize_layer_name(layer.name())}.kml")

    if os.path.exists(kml_path):
        action, new_path = resolve_output_conflict(iface.mainWindow(), kml_path)
        if action == "skip":
            logger.info(f"Skipped layer '{layer.name()}' (output file already exists).")
            return None
        if action == "rename":
            if not new_path:
                return None
            kml_path = new_path

    color_info, mode = extract_layer_color_map(layer)

    try:
        export_source = densify_layer(layer, options.densify_interval)
    except Exception as e:
        logger.warning(f"Densification failed for '{layer.name()}': {e}. Using undensified layer.")
        export_source = layer

    features = list(export_source.getFeatures())
    metadata = build_feature_metadata(export_source.fields(), features, target_name_field, color_info, mode)

    temporary_path = ""
    try:
        temporary_file = tempfile.NamedTemporaryFile(
            prefix=".qols_kml_", suffix=".kml", dir=options.output_dir, delete=False)
        temporary_path = temporary_file.name
        temporary_file.close()

        err_msg = write_layer_to_kml(export_source, temporary_path)
        if err_msg is not None:
            logger.error(f"KML export failed for '{layer.name()}': {err_msg}")
            return None

        tree = ET.parse(temporary_path)  # nosec B314 - self-generated KML, not external XML
        kml_ns = postprocess_kml_tree(
            tree, metadata, group_by_label=options.group_by_label, theme=options.theme)
        ET.register_namespace('', kml_ns)
        tree.write(temporary_path, encoding="utf-8", xml_declaration=True)

        written_tree = ET.parse(temporary_path)  # nosec B314 - validates self-generated KML
        altitude = validate_kml_altitudes(written_tree, metadata)
        os.replace(temporary_path, kml_path)
        temporary_path = ""
    except Exception as e:
        logger.error(f"KML export validation failed for '{layer.name()}': {e}")
        return None
    finally:
        if temporary_path and os.path.exists(temporary_path):
            try:
                os.remove(temporary_path)
            except OSError as e:
                logger.warning(f"Could not remove temporary KML '{temporary_path}': {e}")

    logger.info(
        f"KML exported and altitude-validated for '{layer.name()}': "
        f"{kml_path} ({_format_altitude_range(altitude)})")
    return KmlExportResult(layer.name(), kml_path, altitude)


def run_kml_export(iface) -> None:
    """Entry point: prompts for options once, exports every layer currently
    selected in the QGIS Layers panel to a styled KML file."""
    from .dialog import KmlExportOptionsDialog

    layers = collect_selected_layers(iface)
    if not layers:
        iface.messageBar().pushMessage(
            "QOLS", "No valid layers selected in the Layers panel.",
            level=MSG_WARNING, duration=4)
        return

    field_names = union_of_field_names(layers)
    dlg = KmlExportOptionsDialog(len(layers), field_names, parent=iface.mainWindow())
    if dlg.exec() != DIALOG_ACCEPTED:
        return

    options = KmlExportOptions(
        output_dir=dlg.output_dir(),
        label_field=dlg.label_field(),
        group_by_label=dlg.group_by_label(),
        theme=dlg.theme(),
        densify_interval=dlg.densify_interval(),
    )
    set_last_output_dir(options.output_dir)
    os.makedirs(options.output_dir, exist_ok=True)

    exported = []
    failed = []
    for layer in layers:
        try:
            result = export_layer(iface, layer, options)
        except Exception as e:
            logger.error(f"Unexpected error exporting '{layer.name()}': {e}")
            result = None
        if result is not None:
            exported.append(result)
        else:
            failed.append(layer.name())

    if exported:
        links = [
            f'<a href="{QUrl.fromLocalFile(os.path.dirname(result.path)).toString()}">'
            f'{result.layer_name}</a> ({_format_altitude_range(result.altitude)})'
            for result in exported
        ]
        message = "Exported layers: " + ", ".join(links)
        if failed:
            message += " — failed: " + ", ".join(failed) + " (see Log Messages panel for details)"
        iface.messageBar().pushMessage(
            "Export Complete" if not failed else "Export Partially Complete", message,
            level=MSG_SUCCESS if not failed else MSG_WARNING, duration=10)
    else:
        iface.messageBar().pushMessage(
            "QOLS",
            "KML export failed for: " + ", ".join(failed) + " (see View → Panels → Log Messages for details)",
            level=MSG_CRITICAL, duration=10)
