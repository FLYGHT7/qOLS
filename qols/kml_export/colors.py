"""qols/kml_export/colors.py — RGBA-to-KML color conversion (#153).

Pure Python, no QGIS dependency: callers extract ``.red()``/``.green()``/
``.blue()``/``.alpha()`` from a ``QColor`` before calling
``rgba_to_kml_abgr``, so this module is directly unit-testable without a
QGIS mock — mirrors the pure/QGIS-aware split used in
``qols/direction_marker.py``.
"""
from __future__ import annotations

# KML polygon fill/outline alpha values (0-255), ported verbatim from the
# reference script (ols_2_kml_v8.py): 50% fill opacity, fully opaque outline.
FILL_ALPHA = 128
OUTLINE_ALPHA = 255

__all__ = ["FILL_ALPHA", "OUTLINE_ALPHA", "rgba_to_kml_abgr"]


def rgba_to_kml_abgr(r: int, g: int, b: int, a: int) -> str:
    """Converts 0-255 RGBA components to KML's ``aabbggrr`` hex color format."""
    return f"{a:02x}{b:02x}{g:02x}{r:02x}".lower()
