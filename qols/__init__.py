# -*- coding: utf-8 -*-
"""
/***************************************************************************
 QOLS
                                 A QGIS plugin
 Obstacle Limitation Surfaces Tool
 ***************************************************************************/
"""

def classFactory(iface):
    """Load QOLS class from file qols."""
    from .qols import QOLS
    return QOLS(iface)
