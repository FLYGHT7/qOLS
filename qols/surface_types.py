"""Surface type enumeration for qOLS.

Centralises the string constants used to identify ICAO Annex 14 obstacle
limitation surfaces.  Using this Enum instead of bare string literals ensures:
- Typos are caught at import time by the Enum constructor or IDEs.
- A single place to update if a tab label ever changes in the .ui file.
- Type-checker support for exhaustive ``match``/``if`` chains.

Because ``SurfaceType`` inherits from ``str`` as well as ``Enum``, every member
**is** a plain string and compares equal to its corresponding tab label:

    >>> SurfaceType.APPROACH == "Approach Surface"
    True
"""
from enum import Enum


class SurfaceType(str, Enum):
    """ICAO Annex 14 obstacle limitation surface types.

    Values match the ``QTabWidget`` tab labels defined in
    ``qols_panel_base.ui`` exactly.
    """

    APPROACH = "Approach Surface"
    CONICAL = "Conical"
    INNER_HORIZONTAL = "Inner Horizontal"
    INNER_CONICAL = "Inner Horizontal & Conical"
    OFZ = "OFZ"
    OUTER_HORIZONTAL = "Outer Horizontal"
    TAKEOFF = "Take-Off Surface"
    TRANSITIONAL = "Transitional Surface"

    @classmethod
    def from_tab_text(cls, text: str) -> "SurfaceType":
        """Return the matching member for a tab-text string.

        Performs a case-insensitive strip before lookup so minor whitespace
        differences (common in translated Qt labels) don't cause failures.

        Args:
            text: Raw tab label returned by ``QTabWidget.tabText()``.

        Returns:
            The matching ``SurfaceType`` member.

        Raises:
            ValueError: If *text* doesn't correspond to any known surface type.
        """
        clean = text.strip()
        # Direct value match (most common path)
        for member in cls:
            if member.value == clean:
                return member
        # Legacy / alias: "Transitional" without "Surface"
        if clean.lower() == "transitional":
            return cls.TRANSITIONAL
        raise ValueError(
            f"Unknown surface type: {clean!r}. "
            f"Expected one of {[m.value for m in cls]}"
        )


__all__ = ["SurfaceType"]
