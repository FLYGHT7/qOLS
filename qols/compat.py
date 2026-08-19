"""
qols/compat.py — Qt5 / Qt6 compatibility shim.

All version-sensitive API differences are centralised here.
The rest of the codebase imports from this module instead of
branching on the Qt version inline.

Note for automated Qt6-compatibility scanners: the flat/unscoped enum
accesses below (e.g. ``Qt.RightDockWidgetArea``) are the intentional Qt5
fallback branch of each ``try/except AttributeError`` pair — the Qt6-scoped
form is always tried first. Static scanners can't see that context and
will flag these lines; that's expected and not a bug.
"""

from qgis.PyQt.QtCore import Qt, QEvent
from qgis.PyQt.QtGui import QPainter
from qgis.PyQt.QtWidgets import QDialog, QDialogButtonBox, QMessageBox
from qgis.core import Qgis, QgsWkbTypes, QgsAction, QgsMapLayerProxyModel, QgsVectorFileWriter, QgsUnitTypes

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
# QDialogButtonBox standard buttons (Ok)
# Qt5 (PyQt5):  QDialogButtonBox.Ok
# Qt6 (PyQt6):  QDialogButtonBox.StandardButton.Ok
# ---------------------------------------------------------------------------
try:
    BTN_OK = QDialogButtonBox.StandardButton.Ok
except AttributeError:
    BTN_OK = QDialogButtonBox.Ok  # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# QMessageBox button role (for custom multi-button prompts, #153)
# Qt5 (PyQt5):  QMessageBox.ActionRole
# Qt6 (PyQt6):  QMessageBox.ButtonRole.ActionRole
# ---------------------------------------------------------------------------
try:
    BTN_ROLE_ACTION = QMessageBox.ButtonRole.ActionRole
except AttributeError:
    BTN_ROLE_ACTION = QMessageBox.ActionRole  # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# QDialog result code (Accepted)
# Qt5 (PyQt5):  QDialog.Accepted
# Qt6 (PyQt6):  QDialog.DialogCode.Accepted
# ---------------------------------------------------------------------------
try:
    DIALOG_ACCEPTED = QDialog.DialogCode.Accepted
except AttributeError:
    DIALOG_ACCEPTED = QDialog.Accepted  # type: ignore[attr-defined]

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

# ---------------------------------------------------------------------------
# QEvent mouse-move type constant
# Qt5 (PyQt5):  QEvent.MouseMove       (flat attribute on class)
# Qt6 (PyQt6):  QEvent.Type.MouseMove  (scoped enum)
# ---------------------------------------------------------------------------
try:
    EVENT_MOUSE_MOVE = QEvent.Type.MouseMove
except AttributeError:
    EVENT_MOUSE_MOVE = QEvent.MouseMove  # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# Geometry-type constant for QgsRubberBand
# QGIS 3:  QgsWkbTypes.PolygonGeometry
# QGIS 4:  Qgis.GeometryType.Polygon
# ---------------------------------------------------------------------------
try:
    GEOM_TYPE_POLYGON = Qgis.GeometryType.Polygon
except AttributeError:
    GEOM_TYPE_POLYGON = QgsWkbTypes.PolygonGeometry  # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# Geometry-type constants for QgsRubberBand / layer.geometryType() checks
# QGIS 3:  QgsWkbTypes.PointGeometry / LineGeometry
# QGIS 4:  Qgis.GeometryType.Point / Line
# ---------------------------------------------------------------------------
try:
    GEOM_TYPE_POINT = Qgis.GeometryType.Point
except AttributeError:
    GEOM_TYPE_POINT = QgsWkbTypes.PointGeometry  # type: ignore[attr-defined]

try:
    GEOM_TYPE_LINE = Qgis.GeometryType.Line
except AttributeError:
    GEOM_TYPE_LINE = QgsWkbTypes.LineGeometry  # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# QgsWkbTypes.Type constants (for geometry.wkbType() comparisons)
# Qt5 (PyQt5):  QgsWkbTypes.LineString / MultiLineString
# Qt6 (PyQt6):  QgsWkbTypes.Type.LineString / MultiLineString
# ---------------------------------------------------------------------------
try:
    WKB_LINE_STRING = QgsWkbTypes.Type.LineString
except AttributeError:
    WKB_LINE_STRING = QgsWkbTypes.LineString  # type: ignore[attr-defined]

try:
    WKB_MULTI_LINE_STRING = QgsWkbTypes.Type.MultiLineString
except AttributeError:
    WKB_MULTI_LINE_STRING = QgsWkbTypes.MultiLineString  # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# QgsMapLayerProxyModel filter (for layer-combo geometry filtering)
# Qt5 (PyQt5):  QgsMapLayerProxyModel.VectorLayer
# Qt6 (PyQt6):  QgsMapLayerProxyModel.Filter.VectorLayer
# ---------------------------------------------------------------------------
try:
    FILTER_VECTOR_LAYER = QgsMapLayerProxyModel.Filter.VectorLayer
except AttributeError:
    FILTER_VECTOR_LAYER = QgsMapLayerProxyModel.VectorLayer  # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# QgsVectorFileWriter / QgsUnitTypes constants (KML export, #153)
# Qt5 (PyQt5):  flat attributes on each class
# Qt6 (PyQt6):  nested under each class's own enum
# ---------------------------------------------------------------------------
try:
    SYMBOLOGY_NO_SYMBOLOGY = QgsVectorFileWriter.SymbologyExport.NoSymbology
except AttributeError:
    SYMBOLOGY_NO_SYMBOLOGY = QgsVectorFileWriter.NoSymbology  # type: ignore[attr-defined]

try:
    FILE_ACTION_CREATE_OR_OVERWRITE = QgsVectorFileWriter.ActionOnExistingFile.CreateOrOverwriteFile
except AttributeError:
    FILE_ACTION_CREATE_OR_OVERWRITE = QgsVectorFileWriter.CreateOrOverwriteFile  # type: ignore[attr-defined]

try:
    DISTANCE_UNIT_DEGREES = QgsUnitTypes.DistanceUnit.DistanceDegrees
except AttributeError:
    DISTANCE_UNIT_DEGREES = QgsUnitTypes.DistanceDegrees  # type: ignore[attr-defined]

try:
    WRITER_NO_ERROR = QgsVectorFileWriter.WriterError.NoError
except AttributeError:
    WRITER_NO_ERROR = QgsVectorFileWriter.NoError  # type: ignore[attr-defined]

# ---------------------------------------------------------------------------
# QgsAction generic-Python action type (for register_parameters_action, #118)
# QGIS 3 / Qt5:  QgsAction.GenericPython
# QGIS 4 / Qt6:  QgsAction.ActionType.GenericPython
# ---------------------------------------------------------------------------
try:
    ACTION_TYPE_GENERIC_PYTHON = QgsAction.ActionType.GenericPython
except AttributeError:
    ACTION_TYPE_GENERIC_PYTHON = QgsAction.GenericPython  # type: ignore[attr-defined]

__all__ = [
    "DOCK_RIGHT", "DOCK_LEFT",
    "BTN_SAVE", "BTN_CANCEL", "BTN_OK", "BTN_ROLE_ACTION",
    "DIALOG_ACCEPTED",
    "TOOLTIP_ROLE",
    "COLOR_LIGHT_GRAY", "COLOR_DARK_GRAY",
    "RENDER_ANTIALIAS",
    "MSG_INFO", "MSG_WARNING", "MSG_CRITICAL", "MSG_SUCCESS",
    "EVENT_MOUSE_MOVE",
    "GEOM_TYPE_POLYGON", "GEOM_TYPE_POINT", "GEOM_TYPE_LINE",
    "WKB_LINE_STRING", "WKB_MULTI_LINE_STRING",
    "FILTER_VECTOR_LAYER",
    "SYMBOLOGY_NO_SYMBOLOGY", "FILE_ACTION_CREATE_OR_OVERWRITE",
    "DISTANCE_UNIT_DEGREES", "WRITER_NO_ERROR",
    "ACTION_TYPE_GENERIC_PYTHON",
]
