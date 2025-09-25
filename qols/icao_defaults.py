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
    """Return default conical surface dimensions.

    Returns a dict with:
    - height_m: Conical height in meters
    - radius_m: Conical radius (L) in meters
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
    """Return default inner horizontal surface dimensions.

    Returns a dict with:
    - height_m: Inner horizontal height in meters (45 m per table)
    - radius_m: Inner horizontal radius (L) in meters
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


__all__ = [
    "get_conical_defaults",
    "get_inner_horizontal_defaults",
    "RWY_NON_INSTRUMENT",
    "RWY_NON_PRECISION",
    "RWY_CAT_I",
    "RWY_CAT_II_III",
]
