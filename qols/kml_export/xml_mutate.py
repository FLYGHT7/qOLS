"""qols/kml_export/xml_mutate.py — KML XML post-processing (#153).

Operates purely on ``xml.etree.ElementTree`` objects (stdlib only, no QGIS
dependency), mirroring the pure/QGIS-aware split used in
``qols/direction_marker.py``. This is where ``ols_2_kml_v8.py``'s
post-``QgsVectorFileWriter`` KML mutation logic lives: per-feature
``<Style>`` injection (deduped), clean ``<name>``/HTML ``<description>``,
suppressing the Desktop sidebar preview, absolute altitude + per-feature
Z, and optional grouping into per-label ``<Folder>`` elements.

``postprocess_kml_tree`` is the composed entry point exporter.py calls;
the smaller functions are exposed individually for focused unit testing.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET  # nosec B405 - only builds/mutates elements, never parses external/untrusted input
from typing import Callable, Dict, List, Tuple

from .colors import rgba_to_kml_abgr
from .html_table import generate_attribute_table_html

__all__ = [
    "StyleCache",
    "resolve_kml_namespace",
    "build_style_element",
    "set_placemark_name",
    "set_placemark_description_html",
    "suppress_snippet",
    "strip_inline_style_and_link",
    "set_altitude_and_elevation",
    "group_placemarks_into_folders",
    "remove_empty_folders",
    "postprocess_kml_tree",
]

KtagFn = Callable[[str], str]


class StyleCache:
    """Dedupes KML ``<Style>`` elements by ``(fill_hex, outline_hex)``."""

    def __init__(self) -> None:
        self._cache: Dict[Tuple[str, str], str] = {}

    def style_id_for(self, fill_hex: str, outline_hex: str) -> Tuple[str, bool]:
        """Returns ``(style_id, is_new)`` for this fill/outline hex pair."""
        key = (fill_hex, outline_hex)
        if key in self._cache:
            return self._cache[key], False
        style_id = f"style_{len(self._cache) + 1}"
        self._cache[key] = style_id
        return style_id, True


def resolve_kml_namespace(root: ET.Element) -> Tuple[Dict[str, str], KtagFn]:
    """Returns ``(ns_dict, ktag)`` for *root*'s actual KML namespace URI."""
    if root.tag.startswith('{'):
        kml_ns = root.tag.split('}')[0].strip('{')
    else:
        kml_ns = "http://www.opengis.net/kml/2.2"
    ns = {'kml': kml_ns}

    def ktag(tag_name: str) -> str:
        return f"{{{kml_ns}}}{tag_name}" if kml_ns else tag_name

    return ns, ktag


def build_style_element(ktag: KtagFn, style_id: str, fill_hex: str, outline_hex: str) -> ET.Element:
    style_elem = ET.Element(ktag("Style"), id=style_id)

    linestyle = ET.SubElement(style_elem, ktag("LineStyle"))
    ET.SubElement(linestyle, ktag("color")).text = outline_hex
    ET.SubElement(linestyle, ktag("width")).text = "1"

    polystyle = ET.SubElement(style_elem, ktag("PolyStyle"))
    ET.SubElement(polystyle, ktag("color")).text = fill_hex
    ET.SubElement(polystyle, ktag("fill")).text = "1"
    ET.SubElement(polystyle, ktag("outline")).text = "1"

    return style_elem


def set_placemark_name(placemark: ET.Element, ktag: KtagFn, ns: Dict[str, str], name: str) -> None:
    name_elem = placemark.find("kml:name", ns)
    if name_elem is None:
        name_elem = ET.Element(ktag("name"))
        placemark.insert(0, name_elem)
    name_elem.text = name


def set_placemark_description_html(placemark: ET.Element, ktag: KtagFn, ns: Dict[str, str], html: str) -> None:
    desc_elem = placemark.find("kml:description", ns)
    if desc_elem is None:
        desc_elem = ET.Element(ktag("description"))
        placemark.insert(1, desc_elem)
    desc_elem.text = html


def suppress_snippet(placemark: ET.Element, ktag: KtagFn, ns: Dict[str, str]) -> None:
    """Forces an empty ``<Snippet maxLines="0">`` to hide the Desktop sidebar preview."""
    snippet_elem = placemark.find("kml:Snippet", ns)
    if snippet_elem is None:
        snippet_elem = ET.Element(ktag("Snippet"))
        placemark.insert(2, snippet_elem)
    snippet_elem.set("maxLines", "0")
    snippet_elem.text = ""


def strip_inline_style_and_link(placemark: ET.Element, ktag: KtagFn, ns: Dict[str, str], style_id: str) -> None:
    """Removes any QGIS-auto-generated inline ``<Style>`` and links to the shared ``style_id``."""
    inline_style = placemark.find("kml:Style", ns)
    if inline_style is not None:
        placemark.remove(inline_style)

    style_url = ET.Element(ktag("styleUrl"))
    style_url.text = f"#{style_id}"
    placemark.insert(0, style_url)


def set_altitude_and_elevation(placemark: ET.Element, ktag: KtagFn, ns: Dict[str, str], z_value: float) -> None:
    """Sets ``<altitudeMode>absolute</altitudeMode>`` and rewrites every
    coordinate tuple's Z value to *z_value*, for Polygon/LineString/Point geometries.

    Looks up ``<coordinates>`` recursively (``.//``), not as a direct
    child: for LineString/Point it *is* a direct child, but for Polygon
    it's nested under ``outerBoundaryIs/LinearRing`` (and
    ``innerBoundaryIs/LinearRing`` for holes) — a direct-child lookup
    would silently rewrite nothing for the polygon geometries this
    feature is primarily used for.
    """
    for geom_tag in ("Polygon", "LineString", "Point"):
        for geom in placemark.findall(f".//kml:{geom_tag}", ns):
            alt_mode = geom.find("kml:altitudeMode", ns)
            if alt_mode is None:
                ET.SubElement(geom, ktag("altitudeMode")).text = "absolute"
            else:
                alt_mode.text = "absolute"

            for coords_elem in geom.findall(".//kml:coordinates", ns):
                if not coords_elem.text:
                    continue
                raw_coords = coords_elem.text.strip().split()
                updated_coords = []
                for coord_str in raw_coords:
                    parts = coord_str.split(",")
                    if len(parts) >= 2:
                        updated_coords.append(f"{parts[0]},{parts[1]},{z_value}")
                    else:
                        updated_coords.append(coord_str)
                coords_elem.text = " ".join(updated_coords)


def group_placemarks_into_folders(
    root: ET.Element,
    doc: ET.Element,
    ktag: KtagFn,
    labeled_placemarks: List[Tuple[ET.Element, str]],
) -> None:
    """Moves each ``(placemark, label)`` pair into a per-label ``<Folder>`` under *doc*."""
    parent_map = {child: parent for parent in root.iter() for child in parent}
    folder_dict: Dict[str, ET.Element] = {}

    for pm, label in labeled_placemarks:
        parent = parent_map.get(pm)
        if parent is not None:
            parent.remove(pm)

        if label not in folder_dict:
            folder_elem = ET.Element(ktag("Folder"))
            folder_name = ET.SubElement(folder_elem, ktag("name"))
            folder_name.text = str(label)
            doc.append(folder_elem)
            folder_dict[label] = folder_elem

        folder_dict[label].append(pm)


def remove_empty_folders(root: ET.Element, ns: Dict[str, str]) -> None:
    for folder in list(root.findall(".//kml:Folder", ns)):
        if folder.find(".//kml:Placemark", ns) is None:
            for parent in root.iter():
                if folder in list(parent):
                    parent.remove(folder)
                    break


def postprocess_kml_tree(
    tree: ET.ElementTree,
    feature_metadata: List[dict],
    *,
    group_by_label: bool,
    theme: str,
) -> str:
    """Mutates *tree* in place: per-feature style/name/description/altitude,
    and optional folder grouping. Returns the resolved KML namespace URI, so
    the caller can ``ET.register_namespace('', kml_ns)`` before writing.

    ``feature_metadata`` must have exactly one entry per ``<Placemark>`` in
    the tree, in document order — the same assumption the reference script
    made about ``QgsVectorFileWriter``'s placemark order matching
    ``layer.getFeatures()`` order. Each entry is a dict with keys:
    ``name`` (str), ``attributes`` (ordered ``{field: value}`` dict),
    ``fill_rgba``/``outline_rgba`` (4-tuples of 0-255 ints), ``elevation_z``
    (float), ``label`` (str, used for folder grouping when enabled).
    """
    root = tree.getroot()
    ns, ktag = resolve_kml_namespace(root)
    doc = root.find("kml:Document", ns)
    if doc is None:
        doc = root

    placemarks = root.findall(".//kml:Placemark", ns)
    style_cache = StyleCache()
    labeled_placemarks: List[Tuple[ET.Element, str]] = []

    for pm, meta in zip(placemarks, feature_metadata):
        fill_hex = rgba_to_kml_abgr(*meta["fill_rgba"])
        outline_hex = rgba_to_kml_abgr(*meta["outline_rgba"])
        style_id, is_new = style_cache.style_id_for(fill_hex, outline_hex)
        if is_new:
            doc.insert(0, build_style_element(ktag, style_id, fill_hex, outline_hex))

        set_placemark_name(pm, ktag, ns, meta["name"])
        html = generate_attribute_table_html(meta["attributes"], theme=theme)
        set_placemark_description_html(pm, ktag, ns, html)
        suppress_snippet(pm, ktag, ns)
        strip_inline_style_and_link(pm, ktag, ns, style_id)
        set_altitude_and_elevation(pm, ktag, ns, meta["elevation_z"])

        labeled_placemarks.append((pm, meta["label"]))

    if group_by_label:
        group_placemarks_into_folders(root, doc, ktag, labeled_placemarks)
        remove_empty_folders(root, ns)

    return ns['kml']
