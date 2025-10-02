"""Approach surface ICAO Annex 14 Table 4-1 defaults.

This module provides default values for the APPROACH surface parameters based on
simplified interpretation of the user-provided table images and clarification:

Classification groupings (user clarification):
- Non-instrument: 4 code numbers (1..4)
- Non-precision approach: codes (1-2 grouped), 3, 4
- Precision (CAT I) and Precision (CAT II or III): last groups; widths treated
  uniformly (codes 1-2 grouped @ 140 m, codes 3-4 @ 280 m). CAT II/III only
  valid for codes 3-4 in the table; we still guard for 1-2.

Rows interpreted:
1. Length of inner edge (Approach width at threshold)
2. Distance from threshold (threshold offset) -> Only Non-instrument Code 1 = 30 m, all others 60 m.
3. Divergence (each side): Non-instrument = 10%; all other classifications = 15%.
4. First section length (L1)
5. First section slope (percent) -> converted to decimal here.
6. Second section length (L2) - Only for higher performance runways (see mapping).
7. Second section slope (percent) -> decimal.
8. Horizontal section length (LH) -> Provided where total length reaches 15000 m (L1+L2+LH = 15000). If L2 absent -> no horizontal section (LH=0).

Assumptions / Ambiguities resolved pragmatically:
- Where table shows combined columns (e.g. codes 1-2), the same value used for both.
- If second section not present in table -> L2 = 0; LH = 0.
- For codes with L2 provided and total length known (15 000 m), LH derived = 15000 - L1 - L2.
- For precision categories codes 3 & 4: adopt L1=3000, L2=3600, LH=8400, slopes 2% (first), 2.5% or 2%?  Using commonly referenced values: first=2% (code ≥3), second=2.5% for CAT I code 3 then 2% others ambiguous. Chosen consistent values: first section slope: CAT I (codes1-2)=2.5%, CAT I (3-4)=2%; CAT II/III (3-4)=2%. Second section slope: 2.5% for CAT I code3? Ambiguity simplified to 2.5% for CAT I code3 only else 2.0%.

NOTE: These can be refined later if higher-resolution table data supplied.
"""
from typing import Dict

# Classification constants (reuse strings from existing icao_defaults for consistency)
RWY_NON_INSTRUMENT = "Non-instrument"
RWY_NON_PRECISION = "Non-precision approach"
RWY_CAT_I = "Precision Approach CAT I"
RWY_CAT_II_III = "Precision Approach CAT II or III"

TOTAL_LENGTH_TARGET = 15000.0  # For cases with second + horizontal sections

# Width (inner edge length) mapping
_WIDTH_MAP = {
    RWY_NON_INSTRUMENT: {1: 60.0, 2: 80.0, 3: 150.0, 4: 150.0},
    RWY_NON_PRECISION: {1: 140.0, 2: 140.0, 3: 280.0, 4: 280.0},
    RWY_CAT_I: {1: 140.0, 2: 140.0, 3: 280.0, 4: 280.0},
    RWY_CAT_II_III: {1: 140.0, 2: 140.0, 3: 280.0, 4: 280.0},  # Codes 1-2 rarely applicable but guarded
}

# Threshold offset mapping (distance from threshold)
_THRESHOLD_OFFSET_MAP = {
    RWY_NON_INSTRUMENT: {1: 30.0, 2: 60.0, 3: 60.0, 4: 60.0},
    RWY_NON_PRECISION: {1: 60.0, 2: 60.0, 3: 60.0, 4: 60.0},
    RWY_CAT_I: {1: 60.0, 2: 60.0, 3: 60.0, 4: 60.0},
    RWY_CAT_II_III: {1: 60.0, 2: 60.0, 3: 60.0, 4: 60.0},
}

# Divergence (each side) as ratio (table gives % per side)
_DIVERGENCE_MAP = {
    RWY_NON_INSTRUMENT: {1: 0.10, 2: 0.10, 3: 0.10, 4: 0.10},
    RWY_NON_PRECISION: {1: 0.15, 2: 0.15, 3: 0.15, 4: 0.15},
    RWY_CAT_I: {1: 0.15, 2: 0.15, 3: 0.15, 4: 0.15},
    RWY_CAT_II_III: {1: 0.15, 2: 0.15, 3: 0.15, 4: 0.15},
}

# First section length (L1)
_L1_MAP = {
    RWY_NON_INSTRUMENT: {1: 1600.0, 2: 2500.0, 3: 3000.0, 4: 3000.0},
    RWY_NON_PRECISION: {1: 2500.0, 2: 2500.0, 3: 3000.0, 4: 3000.0},
    RWY_CAT_I: {1: 3000.0, 2: 3000.0, 3: 3000.0, 4: 3000.0},
    RWY_CAT_II_III: {1: 3000.0, 2: 3000.0, 3: 3000.0, 4: 3000.0},
}

# First section slope (decimal)
_SLOPE1_MAP = {
    RWY_NON_INSTRUMENT: {1: 0.05, 2: 0.04, 3: 0.0333, 4: 0.025},
    RWY_NON_PRECISION: {1: 0.0333, 2: 0.0333, 3: 0.02, 4: 0.02},
    RWY_CAT_I: {1: 0.025, 2: 0.025, 3: 0.02, 4: 0.02},
    RWY_CAT_II_III: {1: 0.025, 2: 0.025, 3: 0.02, 4: 0.02},  # Codes 1-2 guarded
}

# Second section length (L2) only for higher categories / codes (otherwise 0)
_L2_MAP = {
    RWY_NON_INSTRUMENT: {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0},
    RWY_NON_PRECISION: {1: 0.0, 2: 0.0, 3: 3600.0, 4: 3600.0},
    RWY_CAT_I: {1: 0.0, 2: 0.0, 3: 3600.0, 4: 3600.0},
    RWY_CAT_II_III: {1: 0.0, 2: 0.0, 3: 3600.0, 4: 3600.0},
}

# Second section slope (decimal)
_SLOPE2_MAP = {
    RWY_NON_INSTRUMENT: {1: 0.0, 2: 0.0, 3: 0.0, 4: 0.0},
    RWY_NON_PRECISION: {1: 0.0, 2: 0.0, 3: 0.025, 4: 0.025},
    RWY_CAT_I: {1: 0.0, 2: 0.0, 3: 0.025, 4: 0.02},  # Ambiguity resolved: code4 lowered to 2%
    RWY_CAT_II_III: {1: 0.0, 2: 0.0, 3: 0.02, 4: 0.02},
}


def get_approach_defaults(rwy_classification: str, code: int) -> Dict[str, float]:
    """Return defaults for APPROACH surface for given classification & code.

    Returns dict:
      width_m
      threshold_offset_m
      divergence_ratio
      L1_m
      first_section_slope
      L2_m
      second_section_slope
      LH_m
    """
    code = int(code)
    rwy = rwy_classification

    width = _WIDTH_MAP.get(rwy, _WIDTH_MAP[RWY_CAT_I]).get(code, 280.0)
    thr_off = _THRESHOLD_OFFSET_MAP.get(rwy, _THRESHOLD_OFFSET_MAP[RWY_CAT_I]).get(code, 60.0)
    divergence = _DIVERGENCE_MAP.get(rwy, _DIVERGENCE_MAP[RWY_CAT_I]).get(code, 0.15)
    l1 = _L1_MAP.get(rwy, _L1_MAP[RWY_CAT_I]).get(code, 3000.0)
    slope1 = _SLOPE1_MAP.get(rwy, _SLOPE1_MAP[RWY_CAT_I]).get(code, 0.02)
    l2 = _L2_MAP.get(rwy, _L2_MAP[RWY_CAT_I]).get(code, 0.0)
    slope2 = _SLOPE2_MAP.get(rwy, _SLOPE2_MAP[RWY_CAT_I]).get(code, 0.0)

    # Horizontal section only if L2 > 0 and table implies total length 15000
    if l2 > 0:
        lh = max(0.0, TOTAL_LENGTH_TARGET - l1 - l2)
    else:
        lh = 0.0

    return {
        'width_m': width,
        'threshold_offset_m': thr_off,
        'divergence_ratio': divergence,
        'L1_m': l1,
        'first_section_slope': slope1,
        'L2_m': l2,
        'second_section_slope': slope2,
        'LH_m': lh,
    }

__all__ = [
    'get_approach_defaults',
    'RWY_NON_INSTRUMENT',
    'RWY_NON_PRECISION',
    'RWY_CAT_I',
    'RWY_CAT_II_III'
]
