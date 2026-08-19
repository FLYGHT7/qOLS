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

import os
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
from .xml_mutate import postprocess_kml_tree

__all__ = [
    "AUTOMATIC_FIELD_OPTION",
    "ELEV_FIELD",
    "DEFAULT_Z",
    "KmlExportOptions",
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
DEFAULT_Z = 10

_AUTO_LABEL_FIELD_NAMES = ("name", "label", "title", "id")
_LAST_DIR_SETTINGS_KEY = "QOLS/KmlExportLastDir"


@dataclass
class KmlExportOptions:
    output_dir: str
    label_field: Optional[str]
    group_by_label: bool
    theme: str
    densify_interval: float


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
    options.sourceCrs = layer.crs()
    options.destCrs = QgsCoordinateReferenceSystem("EPSG:4326")

    result, err_msg = QgsVectorFileWriter.writeAsVectorFormatV2(
        layer, kml_path, QgsCoordinateTransformContext(), options)
    return None if result == WRITER_NO_ERROR else err_msg


def build_feature_metadata(layer_fields, features, label_field, color_info, mode) -> List[dict]:
    """Builds the per-feature metadata list ``xml_mutate.postprocess_kml_tree`` expects."""
    field_names = [f.name() for f in layer_fields]
    has_elev_field = ELEV_FIELD in field_names

    metadata = []
    for feat in features:
        if has_elev_field and feat[ELEV_FIELD] is not None:
            try:
                z_value = float(feat[ELEV_FIELD])
            except (ValueError, TypeError):
                z_value = DEFAULT_Z
        else:
            z_value = DEFAULT_Z

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
            "elevation_z": z_value,
            "label": label,
        })
    return metadata


def _sanitize_layer_name(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name)


def export_layer(iface, layer, options: KmlExportOptions) -> Optional[Tuple[str, str]]:
    """Exports one layer to KML per *options*. Returns ``(layer_name, kml_path)``
    on success, or None if skipped/failed (already logged/messaged)."""
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

    err_msg = write_layer_to_kml(export_source, kml_path)
    if err_msg is not None:
        logger.error(f"KML export failed for '{layer.name()}': {err_msg}")
        return None

    try:
        tree = ET.parse(kml_path)  # nosec B314 - just written by write_layer_to_kml() above, not external XML
    except ET.ParseError as e:
        logger.error(f"KML XML parse failed for '{layer.name()}': {e}")
        return None

    features = list(export_source.getFeatures())
    metadata = build_feature_metadata(export_source.fields(), features, target_name_field, color_info, mode)

    try:
        kml_ns = postprocess_kml_tree(
            tree, metadata, group_by_label=options.group_by_label, theme=options.theme)
        ET.register_namespace('', kml_ns)
        tree.write(kml_path, encoding="utf-8", xml_declaration=True)
    except Exception as e:
        logger.error(f"KML post-processing failed for '{layer.name()}': {e}")
        return None

    return layer.name(), kml_path


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
            f'<a href="{QUrl.fromLocalFile(os.path.dirname(path)).toString()}">{name}</a>'
            for name, path in exported
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
