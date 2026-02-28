"""
ICAO Annex 14 Vol 1 — Table 4-1 helper defaults.

This module centralizes the mapping from Runway Classification + Aerodrome Code
Number to default dimensions for specific surfaces where the standard provides
clear values. It allows the UI/backend to stay thin and provides a pure-Python
module that can be unit-tested without QGIS.

Notes
- Conical: Slope is always 5%. The "height" varies by classification/code.
- Inner Horizontal: Height is 45 m across classifications; radius varies.
- Values derived from Table 4-1 (as commonly reproduced). When in doubt or when
  a specific jurisdiction deviates, the UI still allows manual override.
"""
from typing import Dict, Tuple

RWY_NON_INSTRUMENT = "Non-instrument"
RWY_NON_PRECISION = "Non-precision approach"
RWY_CAT_I = "Precision Approach CAT I"
RWY_CAT_II_III = "Precision Approach CAT II or III"


def get_conical_defaults(rwy_classification: str, code: int) -> Dict[str, float]:
    """Return ICAO Annex 14 Table 4-1 conical surface default dimensions.

    Args:
        rwy_classification: Canonical runway classification string.
        code: Aerodrome reference code (1–4).

    Returns:
        Dict with keys ``height_m`` and ``radius_m`` (both in metres).
        ``radius_m`` is fixed at 6000 m (ICAO outer extent value);
        the actual computed radius on-screen equals height / slope + inner
        horizontal radius.
    """
    # Conical height per classification/code. Slope is always 5% (not returned).
    height_map = {
        RWY_NON_INSTRUMENT: {1: 35.0, 2: 55.0, 3: 75.0, 4: 100.0},
        RWY_NON_PRECISION: {1: 60.0, 2: 60.0, 3: 75.0, 4: 100.0},
        RWY_CAT_I: {1: 60.0, 2: 60.0, 3: 100.0, 4: 100.0},
        RWY_CAT_II_III: {1: 60.0, 2: 60.0, 3: 100.0, 4: 100.0},
    }
    classification_map = height_map.get(rwy_classification, height_map[RWY_CAT_I])
    height = classification_map.get(int(code), 100.0)
    return {"height_m": height, "radius_m": 6000.0}


def get_inner_horizontal_defaults(rwy_classification: str, code: int) -> Dict[str, float]:
    """Return ICAO Annex 14 Table 4-1 inner horizontal surface defaults.

    Args:
        rwy_classification: Canonical runway classification string.
        code: Aerodrome reference code (1–4).

    Returns:
        Dict with keys ``height_m`` (always 45 m per Table 4-1) and
        ``radius_m`` (metres, varies by classification and code).
    """
    # Height is 45 m for all classifications in Table 4-1
    height = 45.0
    # Radius varies with classification and code
    radius_map = {
        RWY_NON_INSTRUMENT: {1: 2000.0, 2: 2500.0, 3: 4000.0, 4: 4000.0},
        RWY_NON_PRECISION: {1: 3000.0, 2: 3000.0, 3: 4000.0, 4: 4000.0},
        RWY_CAT_I: {1: 3500.0, 2: 3500.0, 3: 4000.0, 4: 4000.0},
        RWY_CAT_II_III: {1: 3500.0, 2: 3500.0, 3: 4000.0, 4: 4000.0},
    }
    classification_map = radius_map.get(rwy_classification, radius_map[RWY_CAT_I])
    radius = classification_map.get(int(code), 4000.0)
    return {"height_m": height, "radius_m": radius}


# ---------------------------------------------------------------------------
# ICAO Annex 14 Vol 1 — Table 5-4  Take-Off Climb Surface default dimensions
# ---------------------------------------------------------------------------
_TAKEOFF_TABLE: Dict[int, Dict[str, float]] = {
    1: {
        'inner_edge':               60.0,
        'distance_from_runway_end': 30.0,
        'divergence_pct':           10.0,
        'final_width':             380.0,
        'length':                 1600.0,
        'slope_pct':                 5.0,
    },
    2: {
        'inner_edge':               80.0,
        'distance_from_runway_end': 60.0,
        'divergence_pct':           10.0,
        'final_width':             580.0,
        'length':                 2500.0,
        'slope_pct':                 4.0,
    },
    3: {
        'inner_edge':              180.0,
        'distance_from_runway_end': 60.0,
        'divergence_pct':           12.5,
        'final_width':            1800.0,
        'length':                15000.0,
        'slope_pct':                 2.0,
    },
    4: {
        'inner_edge':              180.0,
        'distance_from_runway_end': 60.0,
        'divergence_pct':           12.5,
        'final_width':            1800.0,
        'length':                15000.0,
        'slope_pct':                 2.0,
    },
}


def get_takeoff_defaults(code: int) -> Dict[str, float]:
    """Return ICAO Annex 14 Table 5-4 Take-Off Climb Surface defaults.

    Args:
        code: Aerodrome reference code (1–4).

    Returns:
        Dict with keys ``inner_edge``, ``distance_from_runway_end``,
        ``divergence_pct``, ``final_width``, ``length``, ``slope_pct``.
        Falls back to code-4 values for unrecognised codes.
    """
    return dict(_TAKEOFF_TABLE.get(int(code), _TAKEOFF_TABLE[4]))


__all__ = [
    "get_conical_defaults",
    "get_inner_horizontal_defaults",
    "get_takeoff_defaults",
    "RWY_NON_INSTRUMENT",
    "RWY_NON_PRECISION",
    "RWY_CAT_I",
    "RWY_CAT_II_III",
]
