"""
qols/logger.py — Thin wrapper around QgsMessageLog.

Usage:
    from . import logger
    logger.info("Surface computed successfully")
    logger.warning("Missing optional field, using default")
    logger.error("CRS mismatch — aborting")
"""

from qgis.core import QgsMessageLog

from .compat import MSG_INFO, MSG_WARNING, MSG_CRITICAL

TAG = "QOLS"


def info(message: str) -> None:
    """Log an informational message to the QGIS Message Log panel."""
    QgsMessageLog.logMessage(message, TAG, MSG_INFO)


def warning(message: str) -> None:
    """Log a warning message to the QGIS Message Log panel."""
    QgsMessageLog.logMessage(message, TAG, MSG_WARNING)


def error(message: str) -> None:
    """Log a critical/error message to the QGIS Message Log panel."""
    QgsMessageLog.logMessage(message, TAG, MSG_CRITICAL)
