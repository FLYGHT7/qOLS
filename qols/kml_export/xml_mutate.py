"""qols/kml_export/xml_mutate.py — KML XML post-processing (#153).

Operates purely on ``xml.etree.ElementTree`` objects (stdlib only, no QGIS
dependency), mirroring the pure/QGIS-aware split used in
``qols/direction_marker.py``. This is where ``ols_2_kml_v8.py``'s
post-``QgsVectorFileWriter`` KML mutation logic lives: per-feature
``<Style>`` injection (deduped), clean ``<name>``/HTML ``<description>``,
suppressing the Desktop sidebar preview, ``absolute`` altitude mode while
preserving each vertex's real Z (#153), and optional grouping into
per-label ``<Folder>`` elements.

``postprocess_kml_tree`` is the composed entry point exporter.py calls;
the smaller functions are exposed individually for focused unit testing.
"""
from __future__ import annotations

import math
import xml.etree.ElementTree as ET  # nosec B405 - only builds/mutates elements, never parses external/untrusted input
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Callable, Deque, Dict, List, Tuple, TypedDict

from .colors import rgba_to_kml_abgr
from .html_table import generate_attribute_table_html

__all__ = [
    "StyleCache",
    "FeatureMetadata",
    "KmlAltitudeSummary",
    "KmlAltitudeValidationError",
    "resolve_kml_namespace",
    "build_style_element",
    "set_placemark_name",
    "set_placemark_description_html",
    "suppress_snippet",
    "strip_inline_style_and_link",
    "set_altitude_and_elevation",
    "validate_kml_altitudes",
    "group_placemarks_into_folders",
    "remove_empty_folders",
    "postprocess_kml_tree",
]

KtagFn = Callable[[str], str]


class FeatureMetadata(TypedDict):
    """Per-feature values required to style and validate one KML placemark."""

    name: str
    attributes: Dict[str, str]
    fill_rgba: Tuple[int, int, int, int]
    outline_rgba: Tuple[int, int, int, int]
    has_geometry_z: bool
    fallback_z: float
    expected_z_min: float
    expected_z_max: float
    label: str


@dataclass(frozen=True)
class KmlAltitudeSummary:
    """Verified altitude statistics for a generated KML document."""

    coordinate_count: int
    minimum_z: float
    maximum_z: float


class KmlAltitudeValidationError(ValueError):
    """Raised when generated KML altitude data differs from its source."""


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


def set_altitude_and_elevation(
    placemark: ET.Element,
    ktag: KtagFn,
    ns: Dict[str, str],
    *,
    fallback_z: float = 0.0,
    preserve_existing_z: bool = True,
) -> None:
    """Sets ``<altitudeMode>absolute</altitudeMode>`` on every
    Polygon/LineString/Point, then normalises each coordinate tuple's Z (#153):

    * a tuple with a finite Z (``lon,lat,alt``) keeps it when the source
      geometry had real Z values;
    * a bare 2-D tuple, or one with a non-finite Z, gains ``fallback_z``.

    ``preserve_existing_z=False`` marks a 2-D source. It replaces even a
    three-part tuple because some GDAL versions serialize missing source Z as
    a synthetic zero. Real geometry Z otherwise has unconditional priority.

    Looks up ``<coordinates>`` recursively (``.//``), not as a direct
    child: for LineString/Point it *is* a direct child, but for Polygon
    it's nested under ``outerBoundaryIs/LinearRing`` (and
    ``innerBoundaryIs/LinearRing`` for holes) — a direct-child lookup
    would silently rewrite nothing for the polygon geometries this
    feature is primarily used for.
    """
    if not math.isfinite(fallback_z):
        raise KmlAltitudeValidationError("KML fallback altitude must be finite")

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
                    if len(parts) not in (2, 3):
                        raise KmlAltitudeValidationError(
                            f"Invalid KML coordinate tuple: {coord_str!r}")
                    try:
                        longitude = float(parts[0])
                        latitude = float(parts[1])
                    except ValueError as error:
                        raise KmlAltitudeValidationError(
                            f"Non-numeric KML coordinate tuple: {coord_str!r}") from error
                    if not math.isfinite(longitude) or not math.isfinite(latitude):
                        raise KmlAltitudeValidationError(
                            f"Non-finite KML coordinate tuple: {coord_str!r}")

                    if len(parts) == 2:
                        updated_coords.append(f"{parts[0]},{parts[1]},{fallback_z}")
                        continue

                    try:
                        altitude = float(parts[2])
                    except ValueError as error:
                        raise KmlAltitudeValidationError(
                            f"Non-numeric KML altitude: {parts[2]!r}") from error
                    if preserve_existing_z and math.isfinite(altitude):
                        updated_coords.append(coord_str)
                    else:
                        updated_coords.append(f"{parts[0]},{parts[1]},{fallback_z}")
                coords_elem.text = " ".join(updated_coords)


def _placemark_altitudes(
    placemark: ET.Element,
    ns: Dict[str, str],
    placemark_index: int,
) -> List[float]:
    altitudes: List[float] = []
    geometry_count = 0

    for geom_tag in ("Polygon", "LineString", "Point"):
        for geom in placemark.findall(f".//kml:{geom_tag}", ns):
            geometry_count += 1
            altitude_mode = geom.find("kml:altitudeMode", ns)
            if altitude_mode is None or altitude_mode.text != "absolute":
                raise KmlAltitudeValidationError(
                    f"Placemark {placemark_index} does not use absolute altitude mode")

            coordinate_elements = geom.findall(".//kml:coordinates", ns)
            if not coordinate_elements:
                raise KmlAltitudeValidationError(
                    f"Placemark {placemark_index} contains geometry without coordinates")

            for coordinates in coordinate_elements:
                if not coordinates.text or not coordinates.text.strip():
                    raise KmlAltitudeValidationError(
                        f"Placemark {placemark_index} contains empty coordinates")
                for coordinate in coordinates.text.strip().split():
                    parts = coordinate.split(",")
                    if len(parts) != 3:
                        raise KmlAltitudeValidationError(
                            f"Placemark {placemark_index} has coordinate without Z: {coordinate!r}")
                    try:
                        values = tuple(float(part) for part in parts)
                    except ValueError as error:
                        raise KmlAltitudeValidationError(
                            f"Placemark {placemark_index} has non-numeric coordinate: {coordinate!r}") from error
                    if not all(math.isfinite(value) for value in values):
                        raise KmlAltitudeValidationError(
                            f"Placemark {placemark_index} has non-finite coordinate: {coordinate!r}")
                    altitudes.append(values[2])

    if geometry_count == 0:
        raise KmlAltitudeValidationError(
            f"Placemark {placemark_index} contains no supported geometry")
    return altitudes


def validate_kml_altitudes(
    tree: ET.ElementTree,
    feature_metadata: List[FeatureMetadata],
    *,
    tolerance: float = 1e-6,
) -> KmlAltitudeSummary:
    """Validates generated KML Z values against the densified source features."""
    root = tree.getroot()
    ns, _ktag = resolve_kml_namespace(root)
    placemarks = root.findall(".//kml:Placemark", ns)

    if len(placemarks) != len(feature_metadata):
        raise KmlAltitudeValidationError(
            "KML placemark count does not match exported feature count: "
            f"{len(placemarks)} != {len(feature_metadata)}")
    if not placemarks:
        raise KmlAltitudeValidationError("Generated KML contains no placemarks")

    metadata_by_name: Dict[str, Deque[FeatureMetadata]] = defaultdict(deque)
    for metadata in feature_metadata:
        metadata_by_name[metadata["name"]].append(metadata)

    all_altitudes: List[float] = []
    for index, placemark in enumerate(placemarks, start=1):
        name_element = placemark.find("kml:name", ns)
        placemark_name = name_element.text if name_element is not None else None
        matching_metadata = metadata_by_name.get(placemark_name or "")
        if not matching_metadata:
            raise KmlAltitudeValidationError(
                f"Placemark {index} has unexpected name: {placemark_name!r}")
        metadata = matching_metadata.popleft()
        altitudes = _placemark_altitudes(placemark, ns, index)
        if not altitudes:
            raise KmlAltitudeValidationError(
                f"Placemark {index} contains no altitude coordinates")

        actual_min = min(altitudes)
        actual_max = max(altitudes)
        expected_min = metadata["expected_z_min"]
        expected_max = metadata["expected_z_max"]
        if not math.isclose(actual_min, expected_min, rel_tol=0.0, abs_tol=tolerance):
            raise KmlAltitudeValidationError(
                f"Placemark {index} minimum Z changed: {expected_min} -> {actual_min}")
        if not math.isclose(actual_max, expected_max, rel_tol=0.0, abs_tol=tolerance):
            raise KmlAltitudeValidationError(
                f"Placemark {index} maximum Z changed: {expected_max} -> {actual_max}")
        all_altitudes.extend(altitudes)

    return KmlAltitudeSummary(
        coordinate_count=len(all_altitudes),
        minimum_z=min(all_altitudes),
        maximum_z=max(all_altitudes),
    )


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
    feature_metadata: List[FeatureMetadata],
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
    ``fill_rgba``/``outline_rgba`` (4-tuples of 0-255 ints),
    ``has_geometry_z`` (bool), ``fallback_z`` (float — Z for genuinely 2-D
    coordinates), ``expected_z_min`` /
    ``expected_z_max`` (source geometry validation range), and ``label``.
    """
    root = tree.getroot()
    ns, ktag = resolve_kml_namespace(root)
    doc = root.find("kml:Document", ns)
    if doc is None:
        doc = root

    placemarks = root.findall(".//kml:Placemark", ns)
    if len(placemarks) != len(feature_metadata):
        raise KmlAltitudeValidationError(
            "KML placemark count does not match exported feature count: "
            f"{len(placemarks)} != {len(feature_metadata)}")
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
        set_altitude_and_elevation(
            pm,
            ktag,
            ns,
            fallback_z=meta["fallback_z"],
            preserve_existing_z=meta["has_geometry_z"],
        )

        labeled_placemarks.append((pm, meta["label"]))

    if group_by_label:
        group_placemarks_into_folders(root, doc, ktag, labeled_placemarks)
        remove_empty_folders(root, ns)

    return ns['kml']
