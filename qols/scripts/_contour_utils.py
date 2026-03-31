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
from typing import List


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
