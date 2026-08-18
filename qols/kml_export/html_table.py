"""qols/kml_export/html_table.py — KML popup attribute-table HTML (#153).

Pure Python, no QGIS dependency: callers pass an already-stringified,
field-order-preserving ``{name: value}`` mapping (extracted from a QGIS
feature) rather than the feature itself, so this module is directly
unit-testable — mirrors the pure/QGIS-aware split used in
``qols/direction_marker.py``.

Colors and zebra-striping are ported verbatim from the reference script
(ols_2_kml_v8.py's ``generate_web_and_desktop_html_table``). Unlike the
reference script, field names and values are HTML-escaped before being
embedded in the table — the script didn't escape them, so an attribute
value containing ``<``, ``>``, or ``&`` would silently corrupt the
generated KML/HTML; escaping doesn't change what's visibly rendered for
ordinary values.
"""
from __future__ import annotations

from html import escape
from typing import Dict

__all__ = ["generate_attribute_table_html"]

_THEMES = {
    "Dark": {
        "row_even": "#0f172a",
        "row_odd": "#1e293b",
        "border_color": "#334155",
        "attr_color": "#38bdf8",
        "val_color": "#cbd5e1",
    },
    "Light": {
        "row_even": "#ffffff",
        "row_odd": "#f8fafc",
        "border_color": "#cbd5e1",
        "attr_color": "#005a9c",
        "val_color": "#334155",
    },
}


def generate_attribute_table_html(attributes: Dict[str, str], theme: str = "Dark") -> str:
    """Builds a zebra-striped, headerless HTML attribute table for a KML popup.

    Args:
        attributes: Ordered ``{field_name: value}`` mapping — insertion
            order determines row order, mirroring the layer's field order.
        theme: ``"Dark"`` or ``"Light"``; unrecognized values fall back to Dark.
    """
    colors = _THEMES.get(theme, _THEMES["Dark"])

    rows = []
    for i, (name, value) in enumerate(attributes.items()):
        bg = colors["row_even"] if i % 2 == 0 else colors["row_odd"]
        rows.append(
            f'<tr style="background-color: {bg};">'
            f'<td style="padding: 6px 10px; font-weight: bold; '
            f'border: 1px solid {colors["border_color"]}; color: {colors["attr_color"]};">'
            f'{escape(str(name))}</td>'
            f'<td style="padding: 6px 10px; border: 1px solid {colors["border_color"]}; '
            f'color: {colors["val_color"]};">{escape(str(value))}</td>'
            f'</tr>'
        )

    return (
        f'<table style="border-collapse: collapse; width: 100%; font-family: sans-serif; '
        f'font-size: 12px; border: 1px solid {colors["border_color"]};">'
        + "".join(rows) +
        '</table>'
    )
