"""New OLS concept — Horizontal Surface ICAO defaults.

Table 4-10 (Dimensions of horizontal surface), keyed by Aeroplane Design
Group (ADG). Unlike the Approach surface's Tables 4-1/4-2
(``new_ols_approach.py``), which merge IIA and IIB into a single value
set, Table 4-10 splits I/IIA into one tier and IIB into another — so ADG
groups are kept fully separate here (``"I"``, ``"IIA"``, ``"IIB"``, ...)
rather than reusing the OFS tab's merged ``"IIA-IIB"`` combo value.

Per the ICAO note under the table: selecting a higher ADG group does not
replace the lower groups' surfaces — all rings up to and including the
selected group's tier are retained, each at its own height above the
aerodrome elevation. Table 4-10 collapses to exactly 3 distinct
radius/height tiers (IIC, III, IV and V all share the same values), so a
single feature covers all of them rather than repeating identical rings.
"""
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# ADG group constants
# ---------------------------------------------------------------------------
ADG_I = "I"
ADG_IIA = "IIA"
ADG_IIB = "IIB"
ADG_IIC = "IIC"
ADG_III = "III"
ADG_IV = "IV"
ADG_V = "V"

ADG_GROUPS = [ADG_I, ADG_IIA, ADG_IIB, ADG_IIC, ADG_III, ADG_IV, ADG_V]

# ---------------------------------------------------------------------------
# Table 4-10  Dimensions of horizontal surface — 3 distinct tiers,
# ascending radius/height, each retained by every higher ADG group.
# ---------------------------------------------------------------------------
_TIERS: List[Dict[str, float]] = [
    {"radius_m": 3350.0, "height_m": 45.0},    # I, IIA
    {"radius_m": 5350.0, "height_m": 60.0},    # IIB
    {"radius_m": 10750.0, "height_m": 90.0},   # IIC, III, IV, V
]

_ADG_TIER_INDEX: Dict[str, int] = {
    ADG_I: 0,
    ADG_IIA: 0,
    ADG_IIB: 1,
    ADG_IIC: 2,
    ADG_III: 2,
    ADG_IV: 2,
    ADG_V: 2,
}


def get_ring_hole_pairs(
    rings: List[Dict[str, float]],
) -> List[Tuple[Dict[str, float], Optional[Dict[str, float]]]]:
    """Pair each ring with the immediately-smaller ring whose footprint
    must be subtracted from it to form an annulus.

    Table 4-10's tiers are always nested (each successive tier's
    ``radius_m`` is >= the previous one's), so the immediately-smaller
    ring's full disc already covers every ring below it — subtracting
    just that one ring, not the union of all smaller ones, is enough.
    The smallest ring (index 0) has no hole source and stays a full
    disc, matching the reported behaviour ("similar to the conical but
    flat" — only the innermost tier is solid; #124 already established
    this same nested-annulus shape for Conical vs. Inner Horizontal).

    Args:
        rings: Rings ordered smallest to largest, as returned by
            :func:`get_horizontal_surface_rings`.

    Returns:
        A list of ``(ring, hole_source)`` tuples, one per input ring,
        in the same order; ``hole_source`` is ``None`` for the first
        ring and the previous ring otherwise.
    """
    return [(ring, rings[i - 1] if i > 0 else None) for i, ring in enumerate(rings)]


def get_adg_tier_count(adg: str) -> int:
    """Return how many of the 3 cumulative tiers apply to ``adg``.

    Args:
        adg: Aeroplane Design Group (``"I"``, ``"IIA"``, ``"IIB"``,
             ``"IIC"``, ``"III"``, ``"IV"``, or ``"V"``).

    Returns:
        ``1`` for I/IIA, ``2`` for IIB, ``3`` for IIC-V. An
        unrecognized ``adg`` falls back to ``3``.
    """
    return _ADG_TIER_INDEX.get(adg, 2) + 1


def get_horizontal_surface_rings(adg: str) -> List[Dict[str, float]]:
    """Return the cumulative list of rings for the given ADG group.

    Args:
        adg: Aeroplane Design Group (``"I"``, ``"IIA"``, ``"IIB"``,
             ``"IIC"``, ``"III"``, ``"IV"``, or ``"V"``).

    Returns:
        A list of ``{"radius_m": float, "height_m": float}`` dicts,
        ordered from smallest to largest, including every tier up to and
        including the one for ``adg`` — e.g. ``"IIB"`` returns 2 rings
        (I/IIA's tier and IIB's own), ``"IIC"`` returns all 3. An
        unrecognized ``adg`` falls back to the largest (3-ring) tier.
    """
    idx = _ADG_TIER_INDEX.get(adg, 2)
    return [dict(tier) for tier in _TIERS[: idx + 1]]


__all__ = [
    "ADG_I", "ADG_IIA", "ADG_IIB", "ADG_IIC", "ADG_III", "ADG_IV", "ADG_V",
    "ADG_GROUPS",
    "get_horizontal_surface_rings",
    "get_ring_hole_pairs",
    "get_adg_tier_count",
]
