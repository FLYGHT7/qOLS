from qgis.core import QgsWkbTypes, QgsPoint
from qgis.utils import iface
from qgis.PyQt.QtCore import QCoreApplication
from qgis.PyQt.QtGui import QColor
from qgis.core import Qgis


def _push_message(title: str, text: str, level=Qgis.Info, duration: int = 4):
    try:
        iface.messageBar().pushMessage(title, text, level=level, duration=duration)
    except Exception:
        # In headless or test environments iface may be unavailable
        pass


def get_polyline_points(geometry):
    """Return a list of points for a polyline from the given geometry.
    - If geometry is LineString: returns geometry.asPolyline().
    - If geometry is MultiLineString with exactly 1 part: returns that part and informs user.
    - If geometry is MultiLineString with >1 parts: raises with friendly warning and UI message.
    """
    if geometry is None or geometry.isEmpty():
        raise Exception("Empty geometry received for runway feature.")

    wkb = geometry.wkbType()
    if QgsWkbTypes.geometryType(wkb) != QgsWkbTypes.LineGeometry:
        raise Exception("Runway geometry must be a line type (LineString or MultiLineString).")

    if QgsWkbTypes.isMultiType(wkb):
        multi = geometry.asMultiPolyline()
        if len(multi) == 1:
            _push_message(
                "QOLS Info",
                "Detected MultiLineString with 1 part; converted to LineString automatically.",
                level=Qgis.Info,
                duration=3,
            )
            return [QgsPoint(p) for p in multi[0]]
        else:
            _push_message(
                "QOLS Warning",
                f"Runway feature has {len(multi)} parts. Please select a single-part line or split the geometry.",
                level=Qgis.Warning,
                duration=6,
            )
            raise Exception(
                f"MultiLineString with {len(multi)} parts is not supported. Select a single-part feature or split it."
            )
    else:
        pts = geometry.asPolyline()
        if not pts:
            # Fallback: try to segmentize/convert complex curves if any were present
            try:
                # Convert curved types to straight segments with a small tolerance
                seg = geometry.segmentize(1.0)
                pts2 = seg.asPolyline()
                if pts2:
                    return [QgsPoint(p) for p in pts2]
            except Exception:
                pass
            raise Exception("Unable to obtain polyline points from geometry.")
        return [QgsPoint(p) for p in pts]
