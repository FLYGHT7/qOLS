"""
qols/compat.py — Qt5 / Qt6 compatibility shim.

All version-sensitive API differences are centralised here.
The rest of the codebase imports from this module instead of
branching on the Qt version inline.
"""

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QPainter
from qgis.PyQt.QtWidgets import QDialogButtonBox
from qgis.core import Qgis

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

# ---------------------------------------------------------------------------
# Item data roles
# Qt5 (PyQt5):  Qt.ToolTipRole  (plain int on Qt namespace)
# Qt6 (PyQt6):  Qt.ItemDataRole.ToolTipRole
# ---------------------------------------------------------------------------
try:
    TOOLTIP_ROLE = Qt.ItemDataRole.ToolTipRole
except AttributeError:
    TOOLTIP_ROLE = Qt.ToolTipRole  # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# Global colours
# Qt5 (PyQt5):  Qt.lightGray / Qt.darkGray
# Qt6 (PyQt6):  Qt.GlobalColor.lightGray / Qt.GlobalColor.darkGray
# ---------------------------------------------------------------------------
try:
    COLOR_LIGHT_GRAY = Qt.GlobalColor.lightGray
    COLOR_DARK_GRAY = Qt.GlobalColor.darkGray
except AttributeError:
    COLOR_LIGHT_GRAY = Qt.lightGray  # type: ignore[attr-defined]
    COLOR_DARK_GRAY = Qt.darkGray    # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# QPainter render hints
# Qt5 (PyQt5):  QPainter.Antialiasing
# Qt6 (PyQt6):  QPainter.RenderHint.Antialiasing
# ---------------------------------------------------------------------------
try:
    RENDER_ANTIALIAS = QPainter.RenderHint.Antialiasing
except AttributeError:
    RENDER_ANTIALIAS = QPainter.Antialiasing  # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# Qgis message-level constants
# QGIS 3 / Qt5:  Qgis.Info, Qgis.Warning, Qgis.Critical, Qgis.Success
# QGIS 4 / Qt6:  Qgis.MessageLevel.Info, etc.
# ---------------------------------------------------------------------------
try:
    MSG_INFO = Qgis.MessageLevel.Info
    MSG_WARNING = Qgis.MessageLevel.Warning
    MSG_CRITICAL = Qgis.MessageLevel.Critical
    MSG_SUCCESS = Qgis.MessageLevel.Success
except AttributeError:
    MSG_INFO = Qgis.Info        # type: ignore[attr-defined]
    MSG_WARNING = Qgis.Warning  # type: ignore[attr-defined]
    MSG_CRITICAL = Qgis.Critical  # type: ignore[attr-defined]
    MSG_SUCCESS = Qgis.Success  # type: ignore[attr-defined]

__all__ = [
    "DOCK_RIGHT", "DOCK_LEFT",
    "BTN_SAVE", "BTN_CANCEL",
    "TOOLTIP_ROLE",
    "COLOR_LIGHT_GRAY", "COLOR_DARK_GRAY",
    "RENDER_ANTIALIAS",
    "MSG_INFO", "MSG_WARNING", "MSG_CRITICAL", "MSG_SUCCESS",
]
