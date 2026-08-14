"""New OLS concept — Take-off Climb Surface ICAO defaults.

Tables 4-14 (mass up to 5 700 kg — ADG I and IIA-IIB only) and 4-15
(mass above 5 700 kg — all ADG I through V), Figure 4-8.

Table 4-15's "Distance from TODA" column is "-" for every ADG — the
surface starts right at TODA (runway end + clearway), which already
folds the clearway in. Modeled here as ``distance_from_runway_end_m
= 0.0`` for every Table 4-15 row, so the *same*
``dD = max(distance_from_runway_end_m, cwy_length_m)`` formula used
for Table 4-14 (whose own footnote says the surface starts at the end
of the clearway if the clearway length exceeds the specified
distance) also produces the correct TODA-relative origin for Table
4-15 (``max(0, CWY) == CWY``) — no mass-category branching is needed
in the geometry script itself, only in which table this module reads
from.

ADG grouping mirrors ``new_ols_approach.py``'s merged "IIA-IIB" scheme
(Tables 4-1/4-2), not ``new_ols_horizontal.py``'s split I/IIA/IIB
scheme (Table 4-10) — reused directly via import to avoid drift.
"""
from typing import Dict, List

from .new_ols_approach import ADG_I, ADG_IIA_IIB, ADG_IIC, ADG_III, ADG_IV, ADG_V, ADG_GROUPS

MASS_CATEGORY_LE_5700 = "Up to 5 700 kg (Table 4-14)"
MASS_CATEGORY_GT_5700 = "Over 5 700 kg (Table 4-15)"
MASS_CATEGORIES = [MASS_CATEGORY_LE_5700, MASS_CATEGORY_GT_5700]

_TABLE_4_14: Dict[str, Dict[str, float]] = {
    ADG_I: {
        'distance_from_runway_end_m': 30.0,
        'inner_edge_m': 60.0,
        'divergence_pct': 10.0,
        'final_width_m': 380.0,
        'length_m': 1600.0,
        'slope_pct': 5.0,
    },
    ADG_IIA_IIB: {
        'distance_from_runway_end_m': 60.0,
        'inner_edge_m': 80.0,
        'divergence_pct': 10.0,
        'final_width_m': 580.0,
        'length_m': 2500.0,
        'slope_pct': 4.0,
    },
}

_TABLE_4_15: Dict[str, Dict[str, float]] = {
    ADG_I: {
        'distance_from_runway_end_m': 0.0,
        'inner_edge_m': 144.0,
        'divergence_pct': 12.5,
        'final_width_m': 1800.0,
        'length_m': 10000.0,
        'slope_pct': 5.0,
    },
    ADG_IIA_IIB: {
        'distance_from_runway_end_m': 0.0,
        'inner_edge_m': 156.0,
        'divergence_pct': 12.5,
        'final_width_m': 1800.0,
        'length_m': 10000.0,
        'slope_pct': 4.0,
    },
    ADG_IIC: {
        'distance_from_runway_end_m': 0.0,
        'inner_edge_m': 156.0,
        'divergence_pct': 12.5,
        'final_width_m': 1800.0,
        'length_m': 10000.0,
        'slope_pct': 2.0,
    },
    ADG_III: {
        'distance_from_runway_end_m': 0.0,
        'inner_edge_m': 172.0,
        'divergence_pct': 12.5,
        'final_width_m': 1800.0,
        'length_m': 10000.0,
        'slope_pct': 2.0,
    },
    ADG_IV: {
        'distance_from_runway_end_m': 0.0,
        'inner_edge_m': 180.0,
        'divergence_pct': 12.5,
        'final_width_m': 1800.0,
        'length_m': 10000.0,
        'slope_pct': 2.0,
    },
    ADG_V: {
        'distance_from_runway_end_m': 0.0,
        'inner_edge_m': 180.0,
        'divergence_pct': 12.5,
        'final_width_m': 1800.0,
        'length_m': 10000.0,
        'slope_pct': 2.0,
    },
}


def get_valid_adg_groups(mass_category: str) -> List[str]:
    """Return the ADG groups applicable to the given mass category.

    Table 4-14 (up to 5 700 kg) only applies to ADG I and IIA-IIB;
    Table 4-15 (above 5 700 kg) applies to all six ADG groups.
    """
    if mass_category == MASS_CATEGORY_LE_5700:
        return [ADG_I, ADG_IIA_IIB]
    return list(ADG_GROUPS)


def get_takeoff_climb_surface_dimensions(mass_category: str, adg: str) -> Dict[str, float]:
    """Return Table 4-14/4-15 defaults for the given mass category and ADG.

    Args:
        mass_category: ``MASS_CATEGORY_LE_5700`` or ``MASS_CATEGORY_GT_5700``.
        adg: Aeroplane Design Group (``"I"``, ``"IIA-IIB"``, ``"IIC"``,
             ``"III"``, ``"IV"``, ``"V"``). Falls back to ADG I if not
             valid for the given mass category.

    Returns:
        Dict with keys ``distance_from_runway_end_m``, ``inner_edge_m``,
        ``divergence_pct``, ``final_width_m``, ``length_m``, ``slope_pct``.
    """
    table = _TABLE_4_14 if mass_category == MASS_CATEGORY_LE_5700 else _TABLE_4_15
    return dict(table.get(adg, table[ADG_I]))


__all__ = [
    'MASS_CATEGORY_LE_5700', 'MASS_CATEGORY_GT_5700', 'MASS_CATEGORIES',
    'get_valid_adg_groups', 'get_takeoff_climb_surface_dimensions',
]
