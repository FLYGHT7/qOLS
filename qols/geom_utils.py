from qgis.core import QgsWkbTypes, QgsPoint, QgsGeometry
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


def polygonz_geometry_from_points(points):
    """Create a true PolygonZ QgsGeometry from a sequence of points.

    Accepts a list/iterable of:
    - QgsPoint (preferred, may include Z)
    - QgsPointXY (Z assumed 0)
    - (x, y) or (x, y, z) tuples

    Ensures the ring is closed and builds a POLYGONZ WKT to create
    a robust 3D polygon geometry compatible with QGIS 3.4x.

    This addresses constructor issues seen with legacy usages like
    QgsPolygon(QgsLineString(points), rings=[]) in QGIS 3.42
    (see Issue #72: "Invalid type in constructor arguments").
    """
    coords = []
    for p in points:
        # QgsPoint has x(), y(), z()
        if hasattr(p, 'x') and hasattr(p, 'y'):
            x = p.x()
            y = p.y()
            # Some points may not carry Z explicitly; default to 0.0
            try:
                z = p.z()
                # z() may return nan in some contexts; coerce to 0 if not finite
                if z is None:
                    z = 0.0
            except Exception:
                z = 0.0
            coords.append((x, y, float(z)))
        else:
            # Assume tuple-like
            try:
                x, y = float(p[0]), float(p[1])
                z = float(p[2]) if len(p) > 2 else 0.0
                coords.append((x, y, z))
            except Exception:
                raise TypeError("Unsupported point type for polygon construction: {}".format(type(p)))

    if len(coords) < 3:
        raise ValueError("Polygon requires at least 3 distinct points")

    # Ensure closed ring (first point equals last)
    if coords[0] != coords[-1]:
        coords.append(coords[0])

    # Build POLYGONZ WKT string
    wkt_points = [f"{x} {y} {z}" for (x, y, z) in coords]
    wkt_polygon = f"POLYGONZ(({', '.join(wkt_points)}))"
    return QgsGeometry.fromWkt(wkt_polygon)
