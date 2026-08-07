"""
_contour_utils.py — Pure-Python contour helpers for qOLS stepped surfaces.

No QGIS dependency: safe to import in unit tests without a QGIS context.

Usage inside exec()-based scripts (approach-surface-UTM.py, take-off-surface_UTM.py):
    import importlib.util as _ilu, os as _os
    _spec = _ilu.spec_from_file_location(
        '_contour_utils',
        _os.path.join(_os.path.dirname(__file__), '_contour_utils.py')
    )
    _cu = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(_cu)
    # then: _cu.contour_elevations(z_start, z_end, interval)

Related issue: #84 — Enhancement stepped surface.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import ceil, floor
from typing import List, Tuple


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ContourSpec:
    """Geometry-agnostic specification for a single contour line.

    All distances and elevations are in metres.

    Attributes:
        elevation:            The surface elevation this contour represents.
        distance_from_origin: Distance along the surface centre axis from the
                              section origin point (pt_01 for approach,
                              pt_01D for take-off).
        half_width:           Half the width of the contour line at this
                              distance (left and right of the centre axis).
    """
    elevation: float
    distance_from_origin: float
    half_width: float


# ---------------------------------------------------------------------------
# Elevation level helpers
# ---------------------------------------------------------------------------

def contour_elevations(z_start: float, z_end: float, interval: int) -> List[float]:
    """Return whole-number elevation levels spaced ``interval`` metres apart.

    Only levels strictly inside the open interval (z_start, z_end] are
    returned.  The surface start elevation itself is not a contour because
    the surface polygon already starts there.

    Args:
        z_start:  Elevation at the near (origin) end of the section, metres.
        z_end:    Elevation at the far end of the section, metres.
        interval: Contour spacing in metres.  Must be a positive integer.
                  Pass 0 to disable (returns empty list).

    Returns:
        Sorted list of float elevations.  Empty when interval <= 0
        or z_end <= z_start (flat / descending sections).

    Examples:
        >>> contour_elevations(21.7, 81.7, 10)
        [30.0, 40.0, 50.0, 60.0, 70.0, 80.0]
        >>> contour_elevations(0.0, 10.0, 10)
        [10.0]
        >>> contour_elevations(10.0, 10.0, 10)
        []
        >>> contour_elevations(21.7, 81.7, 0)
        []
    """
    if interval <= 0 or z_end <= z_start:
        return []
    # Add a small epsilon so z_start is strictly excluded when it falls exactly
    # on an interval boundary (contract: open at z_start, closed at z_end).
    first = int(ceil(z_start / interval + 1e-9)) * interval
    last = int(floor(z_end / interval)) * interval
    return [float(v) for v in range(first, last + 1, interval)]


# ---------------------------------------------------------------------------
# Per-section geometry helpers
# ---------------------------------------------------------------------------

def contour_specs_for_linear_section(
    z_section_start: float,
    z_section_end: float,
    slope: float,
    d_offset: float,
    near_half_width: float,
    divergence_ratio: float,
    elevations: List[float],
) -> List[ContourSpec]:
    """Compute ContourSpecs for a **linearly sloped** trapezoidal section.

    The section runs from ``d_offset`` (start, elevation ``z_section_start``)
    to ``d_offset + (z_section_end - z_section_start) / slope`` (end,
    elevation ``z_section_end``).  The half-width at distance ``d`` from the
    global origin is::

        half_width(d) = near_half_width + d * divergence_ratio

    where *near_half_width* is the half-width at ``d_offset`` (i.e., at the
    start of this section in the global coordinate system).

    Only elevations strictly inside the section range are placed.  Levels at
    exactly ``z_section_start`` are skipped (the polygon edge is already
    there); levels at exactly ``z_section_end`` are included (the far edge).

    Args:
        z_section_start:  Elevation at the start of this section, metres.
        z_section_end:    Elevation at the end of this section, metres.
        slope:            Vertical rise per horizontal metre (decimal, > 0).
                          E.g. 0.02 for a 2 % slope.
        d_offset:         Horizontal distance of the section start from the
                          global origin (pt_01 / pt_01D).
        near_half_width:  Half-width of the surface at ``d_offset``.
        divergence_ratio: Lateral growth per metre along the centre axis.
                          E.g. 0.15 means the surface grows 0.15 m wider
                          per metre of distance.
        elevations:       Pre-computed list of target elevations (from
                          :func:`contour_elevations`).

    Returns:
        List of :class:`ContourSpec` in elevation order.  Empty when the
        section is flat (slope == 0) or no elevations fall within the range.
    """
    if slope <= 0:
        return []

    specs: List[ContourSpec] = []
    for z_c in elevations:
        # Only include levels that fall strictly within this section
        # (use a small tolerance for float comparison at boundaries)
        if not (z_section_start - 1e-9 < z_c <= z_section_end + 1e-9):
            continue
        # Distance from the section's own start
        d_in_section = (z_c - z_section_start) / slope
        # Distance from the global origin
        d_from_origin = d_offset + d_in_section
        half_w = near_half_width + d_from_origin * divergence_ratio
        specs.append(ContourSpec(
            elevation=z_c,
            distance_from_origin=d_from_origin,
            half_width=half_w,
        ))
    return specs


def contour_specs_for_takeoff(
    z_start: float,
    slope_ratio: float,
    distance_to_max_width: float,
    surface_length: float,
    near_half_width: float,
    max_half_width: float,
    divergence_ratio: float,
    elevations: List[float],
) -> List[ContourSpec]:
    """Compute ContourSpecs for the Take-Off Climb Surface.

    The surface has a single constant slope throughout but two width zones:

    * **Expanding zone** ``[0, distance_to_max_width]``:
      half-width = ``near_half_width + d * divergence_ratio``
    * **Constant-width zone** ``[distance_to_max_width, surface_length]``:
      half-width = ``max_half_width``

    Elevation increases linearly: ``z(d) = z_start + d * slope_ratio``.

    Args:
        z_start:              Elevation at pt_01D (DER / threshold), metres.
        slope_ratio:          Vertical rise per horizontal metre (e.g. 0.02
                              for a 2 % slope — pass ``slopePct / 100``).
        distance_to_max_width: Distance at which the surface reaches its
                              maximum width.
        surface_length:       Total length of the climb surface from pt_01D.
        near_half_width:      Half of ``widthDep`` at pt_01D.
        max_half_width:       Half of ``maxWidthDep``.
        divergence_ratio:     Lateral growth per metre (``divergencePct / 100``).
        elevations:           Pre-computed list of target elevations.

    Returns:
        List of :class:`ContourSpec` in elevation order.
    """
    if slope_ratio <= 0:
        return []

    z_end = z_start + surface_length * slope_ratio
    specs: List[ContourSpec] = []

    for z_c in elevations:
        if not (z_start - 1e-9 < z_c <= z_end + 1e-9):
            continue
        d = (z_c - z_start) / slope_ratio
        if d > surface_length + 1e-6:
            continue
        # Width zone
        if d <= distance_to_max_width:
            half_w = near_half_width + d * divergence_ratio
        else:
            half_w = max_half_width
        specs.append(ContourSpec(
            elevation=z_c,
            distance_from_origin=d,
            half_width=half_w,
        ))
    return specs


# ---------------------------------------------------------------------------
# General polygon iso-elevation slicing (#122 — Transitional Surface)
# ---------------------------------------------------------------------------

def contour_specs_for_polygon_slice(
    vertices: List[Tuple[float, float, float]],
    elevations: List[float],
) -> List[Tuple[float, Tuple[float, float], Tuple[float, float]]]:
    """Slice a closed (x, y, z) polygon ring at each target elevation.

    Unlike :func:`contour_specs_for_linear_section`/`_for_takeoff`, this
    makes no assumption about a single axis driving both elevation and
    width — it works directly from the ring's own per-vertex elevations,
    which is required for Transitional Surface's 5-vertex pentagon (three
    vertices share the max elevation, the other two sit at the two
    threshold elevations — not a simple single-axis trapezoid). Returns
    plain ``(elevation, (x1, y1), (x2, y2))`` tuples instead of
    :class:`ContourSpec`, since there's no single "distance from origin"
    or "half-width" axis to report here.

    ``vertices`` is an ordered ring, NOT closed (no repeated first point);
    edge ``(vertices[-1], vertices[0])`` is treated as the closing edge.

    For each ``level`` in ``elevations``, every edge ``(za, zb)`` is kept
    if ``min(za, zb) < level <= max(za, zb)`` — flat edges (``za == zb``)
    never cross under this half-open convention, which is also what
    avoids double-counting a level that lands exactly on a shared vertex
    (the edge for which that vertex is the upper endpoint reports it, the
    edge for which it's the lower endpoint does not).

    Levels producing exactly 2 crossings become one contour segment.
    Levels producing 0, 1, or more than 2 crossings are silently omitted
    (0 = level outside this ring's range; 1 or >2 = a degenerate/non-simple
    ring, which shouldn't occur for the standard pentagon under valid
    input parameters — e.g. ``Tslope > 0`` and ``ZIH`` above both
    threshold elevations). This mirrors the existing convention of
    producing fewer contour lines than requested rather than guessing at
    a possibly-wrong pairing.

    Args:
        vertices:   Ordered ring of (x, y, z) points, ring not closed.
        elevations: Pre-computed target elevations (from
                    :func:`contour_elevations`).

    Returns:
        List of ``(elevation, (x1, y1), (x2, y2))`` tuples, one per level
        that yields exactly 2 crossings.
    """
    n = len(vertices)
    if n < 3:
        return []

    specs: List[Tuple[float, Tuple[float, float], Tuple[float, float]]] = []
    for level in elevations:
        crossings: List[Tuple[float, float]] = []
        for i in range(n):
            x1, y1, z1 = vertices[i]
            x2, y2, z2 = vertices[(i + 1) % n]
            if z1 == z2:
                continue
            lo, hi = (z1, z2) if z1 < z2 else (z2, z1)
            if not (lo < level <= hi):
                continue
            t = (level - z1) / (z2 - z1)
            crossings.append((x1 + t * (x2 - x1), y1 + t * (y2 - y1)))
        if len(crossings) == 2:
            specs.append((level, crossings[0], crossings[1]))
    return specs


# ---------------------------------------------------------------------------
# Conical Surface (#126) — radial contour helper
# ---------------------------------------------------------------------------

def conical_contour_radius(
    elevation: float,
    bottom_z: float,
    r_inner: float,
    slope: float,
) -> float:
    """Radius at which the Conical surface reaches ``elevation``.

    Unlike Approach/Take-off/Transitional, Conical's elevation varies
    purely with radial distance from the runway spine, not along the
    runway's length — its rise is linear in radius:
    ``elevation(r) = bottom_z + slope * (r - r_inner)``. Solving for
    ``r`` gives this formula.

    Precondition: ``slope > 0`` — the caller's responsibility to check
    (same convention as :func:`contour_specs_for_linear_section`'s own
    ``slope <= 0`` guard); a non-positive slope makes "radius at this
    elevation" undefined, so callers should skip contour generation
    entirely rather than call this.

    Args:
        elevation: Target contour elevation, metres.
        bottom_z:  Elevation at the inner edge (``r_inner``), metres —
                   equals Datum + Inner Horizontal Height.
        r_inner:   Radius of the inner edge (Inner Horizontal's own
                   radius), metres.
        slope:     Vertical rise per horizontal metre (decimal, > 0).

    Returns:
        The radius, in metres, at which the cone reaches ``elevation``.
    """
    return r_inner + (elevation - bottom_z) / slope


# ---------------------------------------------------------------------------
# Layer styling
# ---------------------------------------------------------------------------

def apply_contour_style(layer, script_file: str, label_font_size: float = None) -> bool:
    """Apply the distributed QML style to a contour layer.

    Looks for ``<plugin_root>/styles/contour_styling.qml`` relative to the
    calling script's location (``script_file`` should be ``__file__`` of the
    caller, e.g. ``approach-surface-UTM.py``).

    If the file is found and successfully loaded it is preferred over the
    hardcoded fallback.  If the file is missing or ``loadNamedStyle`` fails,
    the fallback is applied silently so the layer is always styled.

    The fallback style matches the previous behaviour:
      * Red solid line, 0.5 mm
      * Plain label from the ``surface_elevation`` field

    Args:
        layer:            A ``QgsVectorLayer`` (LineStringZ) for the contour layer.
        script_file:      ``__file__`` of the calling script.  Used to locate the
                          ``styles/`` folder one directory above ``scripts/``.
        label_font_size:  If given, overrides the label text size (points) on
                          top of whichever style (QML or fallback) got applied —
                          e.g. Conical's many closely-spaced contour rings
                          (#126) need a larger label than Approach/
                          Transitional's more sparsely spaced ones.

    Returns:
        ``True`` if the QML file was applied, ``False`` if the fallback was used.
    """
    import os

    # styles/ lives at <plugin_root>/styles/ — one level above scripts/
    styles_path = os.path.join(
        os.path.dirname(os.path.dirname(script_file)),
        'styles',
        'contour_styling.qml',
    )

    applied_qml = False
    if os.path.isfile(styles_path):
        try:
            _msg, success = layer.loadNamedStyle(styles_path)
            if success:
                applied_qml = True
        except Exception:
            pass  # fall through to hardcoded fallback

    if not applied_qml:
        # Fallback: hardcoded style (previous behaviour, always safe)
        from qgis.core import (  # noqa: PLC0415 — intentional late import (no QGIS at test time)
            QgsLineSymbol,
            QgsSingleSymbolRenderer,
            QgsPalLayerSettings,
            QgsVectorLayerSimpleLabeling,
        )
        _sym = QgsLineSymbol.createSimple({'color': 'red', 'width': '0.5'})
        layer.setRenderer(QgsSingleSymbolRenderer(_sym))
        _pal = QgsPalLayerSettings()
        _pal.fieldName = 'surface_elevation'
        _pal.enabled = True
        layer.setLabeling(QgsVectorLayerSimpleLabeling(_pal))
        layer.setLabelsEnabled(True)

    if label_font_size is not None:
        from qgis.core import QgsVectorLayerSimpleLabeling  # noqa: PLC0415
        labeling = layer.labeling()
        if labeling is not None:
            settings = labeling.settings()
            text_format = settings.format()
            text_format.setSize(label_font_size)
            settings.setFormat(text_format)
            layer.setLabeling(QgsVectorLayerSimpleLabeling(settings))
            layer.setLabelsEnabled(True)

    layer.triggerRepaint()
    return applied_qml
