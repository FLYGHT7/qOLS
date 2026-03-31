"""
qols/compat.py — Qt5 / Qt6 compatibility shim.

All version-sensitive API differences are centralised here.
The rest of the codebase imports from this module instead of
branching on the Qt version inline.
"""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QDialogButtonBox

# ---------------------------------------------------------------------------
# Dock-widget area constants
# Qt5 (PyQt5):  Qt.RightDockWidgetArea
# Qt6 (PyQt6):  Qt.DockWidgetArea.RightDockWidgetArea
# ---------------------------------------------------------------------------
try:
    DOCK_RIGHT = Qt.DockWidgetArea.RightDockWidgetArea
    DOCK_LEFT = Qt.DockWidgetArea.LeftDockWidgetArea
except AttributeError:
    DOCK_RIGHT = Qt.RightDockWidgetArea  # type: ignore[attr-defined]
    DOCK_LEFT = Qt.LeftDockWidgetArea    # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# QDialogButtonBox standard buttons
# Qt5 (PyQt5):  QDialogButtonBox.Save
# Qt6 (PyQt6):  QDialogButtonBox.StandardButton.Save
# ---------------------------------------------------------------------------
try:
    BTN_SAVE = QDialogButtonBox.StandardButton.Save
    BTN_CANCEL = QDialogButtonBox.StandardButton.Cancel
except AttributeError:
    BTN_SAVE = QDialogButtonBox.Save    # type: ignore[attr-defined]
    BTN_CANCEL = QDialogButtonBox.Cancel  # type: ignore[attr-defined]

__all__ = ["DOCK_RIGHT", "DOCK_LEFT", "BTN_SAVE", "BTN_CANCEL"]
