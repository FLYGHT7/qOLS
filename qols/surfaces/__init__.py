"""Surfaces sub-package: ICAO Annex 14 default dimension tables.

Re-exports the complete public API of both *icao* and *approach* modules
so that legacy-style imports such as ``from qols.surfaces import ...``
continue to work in addition to the direct per-module imports.
"""

from .icao import (
    get_conical_defaults,
    get_inner_horizontal_defaults,
    get_takeoff_defaults,
    RWY_NON_INSTRUMENT,
    RWY_NON_PRECISION,
    RWY_CAT_I,
    RWY_CAT_II_III,
)
from .approach import (
    get_approach_defaults,
    TOTAL_LENGTH_TARGET,
)

__all__ = [
    # icao
    "get_conical_defaults",
    "get_inner_horizontal_defaults",
    "get_takeoff_defaults",
    "RWY_NON_INSTRUMENT",
    "RWY_NON_PRECISION",
    "RWY_CAT_I",
    "RWY_CAT_II_III",
    # approach
    "get_approach_defaults",
    "TOTAL_LENGTH_TARGET",
]
