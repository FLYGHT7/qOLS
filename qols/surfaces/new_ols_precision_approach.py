"""New OLS concept — Surface for precision approaches ICAO defaults.

Table 4-12 (Dimensions of surface for precision approaches). Unlike the
Approach/Horizontal tables, this one has a single "I to V" column — no
Aeroplane Design Group variation — so there is nothing to look up by
ADG, just the table's own fixed values.

``missed_approach.section_1.divergence_pct`` (17.48) is the table's own
published value, kept here for attribute/metadata display only. The
geometry script derives the actual 1st-section half-width from the
transitional slope reaching 45 m of rise instead of multiplying by this
percentage directly — numerically equivalent (17.48% is itself a
rounded display of that same relationship), but the derived form is
exact. See qpansopy's own bugfix history (issue #188 in that project)
for why the direct-percentage form silently narrows the surface.
"""
from typing import Dict


def get_precision_approach_dimensions() -> Dict[str, dict]:
    """Return ICAO Annex 14 Table 4-12 as a nested dict.

    Returns:
        Dict with three keys:

        * ``approach`` — ``distance_from_threshold_m``, ``inner_edge_m``,
          and ``section_1``/``section_2`` dicts (``length_m``,
          ``divergence_pct``, ``slope_pct`` each).
        * ``missed_approach`` — ``distance_after_threshold_m``,
          ``inner_edge_m``, and ``section_1``/``section_2`` dicts, same
          shape as ``approach``.
        * ``transitional`` — ``slope_pct``.
    """
    return {
        'approach': {
            'distance_from_threshold_m': 60.0,
            'inner_edge_m': 300.0,
            'section_1': {'length_m': 3000.0, 'divergence_pct': 15.0, 'slope_pct': 2.0},
            'section_2': {'length_m': 9600.0, 'divergence_pct': 15.0, 'slope_pct': 2.5},
        },
        'missed_approach': {
            'distance_after_threshold_m': 900.0,
            'inner_edge_m': 300.0,
            'section_1': {'length_m': 1800.0, 'divergence_pct': 17.48, 'slope_pct': 2.5},
            'section_2': {'length_m': 10200.0, 'divergence_pct': 25.0, 'slope_pct': 2.5},
        },
        'transitional': {'slope_pct': 14.3},
    }


__all__ = ['get_precision_approach_dimensions']
