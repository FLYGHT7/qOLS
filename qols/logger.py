"""
qols/logger.py — Thin wrapper around QgsMessageLog.

Usage:
    from . import logger
    logger.info("Surface computed successfully")
    logger.warning("Missing optional field, using default")
    logger.error("CRS mismatch — aborting")
"""

from qgis.core import Qgis, QgsMessageLog

TAG = "QOLS"


def info(message: str) -> None:
    """Log an informational message to the QGIS Message Log panel."""
    QgsMessageLog.logMessage(message, TAG, Qgis.Info)


def warning(message: str) -> None:
    """Log a warning message to the QGIS Message Log panel."""
    QgsMessageLog.logMessage(message, TAG, Qgis.Warning)


def error(message: str) -> None:
    """Log a critical/error message to the QGIS Message Log panel."""
    QgsMessageLog.logMessage(message, TAG, Qgis.Critical)
