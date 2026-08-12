"""New OLS concept — Instrument Departure Surface ICAO defaults.

Table 4-13 (Dimensions of instrument departure surface). Like Table
4-12 (``new_ols_precision_approach.py``), this table has a single
"I to V" column — no Aeroplane Design Group variation.

Ported from qpansopy's Omnidirectional SID module
(``Q_Pansopy/modules/departures/omnidirectional_sid.py``), per #136's
own request ("similar to the OMNI SID without Area 3"): qpansopy's
Area 1 (15 deg splay) / Area 2 (30 deg splay) match this table's
``section_1``/``section_2`` shape exactly, and its
``INITIAL_HEIGHT_ABOVE_DER = 5`` m / ``INITIAL_SEMI_WIDTH = 150`` m
constants match ``initial_height_above_der_m`` / half of
``inner_edge_m`` here exactly.

Two differences found (values, not shape) — reported per the issue's
own "let me know" request:

* qpansopy's Area 1/Area 2 splay angles (15 deg / 30 deg) give
  ``tan(15) = 26.79%`` / ``tan(30) = 57.735%`` — the table's own
  published ``26.8%`` / ``57.8%`` are the same values rounded. Small
  difference, so (per the issue's own criterion) the table's literal
  percentages are used directly here rather than re-deriving them from
  degrees.
* qpansopy's Area 1/Area 2 *lengths* are derived from a user-supplied
  Procedure Design Gradient and target altitudes (120 m AGL, then
  TNA) — it models one specific departure procedure's climb profile.
  This table instead gives fixed lengths (``3500``/``8300`` m) for the
  generic OLS protection surface, independent of aircraft performance
  — intentionally different tools, so the table's fixed lengths are
  used as-is. Likewise qpansopy subtracts a 0.8% obstacle-clearance
  margin from the PDG to get its effective climb slope; this table
  publishes the final surface slope directly (``2.5%``), no margin
  subtraction needed.
"""
from typing import Dict


def get_departure_surface_dimensions() -> Dict[str, object]:
    """Return ICAO Annex 14 Table 4-13 as a nested dict.

    Returns:
        Dict with:

        * ``initial_height_above_der_m`` — height of the surface's
          start above DER elevation.
        * ``inner_edge_m`` — full width of the surface at DER.
        * ``slope_pct`` — constant slope shared by both sections.
        * ``section_1``/``section_2`` — ``length_m``/``divergence_pct``
          dicts (divergence is each side, incremental from the
          previous section's own edge).
    """
    return {
        'initial_height_above_der_m': 5.0,
        'inner_edge_m': 300.0,
        'slope_pct': 2.5,
        'section_1': {'length_m': 3500.0, 'divergence_pct': 26.8},
        'section_2': {'length_m': 8300.0, 'divergence_pct': 57.8},
    }


__all__ = ['get_departure_surface_dimensions']
