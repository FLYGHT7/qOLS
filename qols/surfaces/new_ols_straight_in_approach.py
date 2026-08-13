"""New OLS concept — Surface for straight-in instrument approaches.

Table 4-11 (Dimensions of surface for straight-in instrument
approaches). Like Table 4-12/4-13 (``new_ols_precision_approach.py``,
``new_ols_departure.py``), this table has a single "I to V" column —
no Aeroplane Design Group variation, so this surface is always drawn
the same way regardless of the runway's ADG.

The table's own "Length: Horizontal OES as per ADG I" note for the
Lower section is an explicit cross-reference to the Horizontal OES
surface's ADG-I ring (``new_ols_horizontal.py``'s ``_TIERS[0]``:
radius 3350 m, height 45 m — matching this table's own Lower section
height of 45 m). That radius is looked up via
:func:`~qols.surfaces.new_ols_horizontal.get_horizontal_surface_rings`
rather than hardcoded, so the two tables stay in sync if Table 4-10
ever changes.
"""
from typing import Dict

from qols.surfaces.new_ols_horizontal import ADG_I, get_horizontal_surface_rings


def get_straight_in_approach_dimensions() -> Dict[str, dict]:
    """Return ICAO Annex 14 Table 4-11 as a nested dict.

    Returns:
        Dict with:

        * ``lower_section`` — ``height_m``/``length_m`` (the racetrack
          radius, taken from the Horizontal OES surface's ADG-I ring).
        * ``upper_section`` — ``height_m``/``shorter_side_m``/
          ``longer_side_from_threshold_m``.
    """
    lower_ring = get_horizontal_surface_rings(ADG_I)[0]
    return {
        'lower_section': {'height_m': 45.0, 'length_m': lower_ring['radius_m']},
        'upper_section': {
            'height_m': 60.0,
            'shorter_side_m': 7410.0,
            'longer_side_from_threshold_m': 5350.0,
        },
    }


__all__ = ['get_straight_in_approach_dimensions']
