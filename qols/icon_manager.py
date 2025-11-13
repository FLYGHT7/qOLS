"""
Custom icons manager for qOLS plugin
Provides intuitive icons for different layer types instead of default gray cubes
"""

import os
from qgis.PyQt.QtGui import QIcon, QPixmap, QPainter
from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtSvg import QSvgRenderer

class QolsIconManager:
    """Manager for custom qOLS icons"""
    
    def __init__(self, plugin_dir):
        self.plugin_dir = plugin_dir
        self.icons_dir = os.path.join(plugin_dir, 'icons')
        
        # Ensure icons directory exists
        if not os.path.exists(self.icons_dir):
            os.makedirs(self.icons_dir)
    
    def get_runway_icon(self, size=16):
        """Get runway icon"""
        return self._create_icon_from_svg('runway_icon.svg', size)
    
    def get_threshold_icon(self, size=16):
        """Get threshold icon"""  
        return self._create_icon_from_svg('threshold_icon.svg', size)
    
    def get_default_layer_icon(self, size=16):
        """Get a better default layer icon than gray cube"""
        return self._create_layer_icon(size)
    
    def _create_icon_from_svg(self, svg_filename, size):
        """Create QIcon from SVG file"""
        svg_path = os.path.join(self.icons_dir, svg_filename)
        
        if not os.path.exists(svg_path):
            # Return default icon if SVG doesn't exist
            return self.get_default_layer_icon(size)
        
        try:
            # Load SVG and render to pixmap
            svg_renderer = QSvgRenderer(svg_path)
            pixmap = QPixmap(QSize(size, size))
            pixmap.fill(0x00000000)  # Transparent background
            
            painter = QPainter(pixmap)
            svg_renderer.render(painter)
            painter.end()
            
            return QIcon(pixmap)
            
        except Exception as e:
            print(f"qOLS: Error loading SVG icon {svg_filename}: {e}")
            return self.get_default_layer_icon(size)
    
    def _create_layer_icon(self, size):
        """Create a simple, better layer icon than default gray cube"""
        pixmap = QPixmap(QSize(size, size))
        pixmap.fill(0x00000000)  # Transparent background
        
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Draw a simple layer representation
        from qgis.PyQt.QtGui import QBrush, QPen
        from qgis.PyQt.QtCore import Qt
        
        # Background circle
        painter.setBrush(QBrush(Qt.lightGray))
        painter.setPen(QPen(Qt.darkGray, 1))
        painter.drawEllipse(1, 1, size-2, size-2)
        
        # Layer lines
        painter.setPen(QPen(Qt.darkGray, 1))
        for i in range(3):
            y = 4 + i * 3
            painter.drawLine(4, y, size-4, y)
        
        painter.end()
        return QIcon(pixmap)

def apply_custom_icons_to_combos(dockwidget, icon_manager):
    """Apply custom icons to the layer combo boxes"""
    try:
        # Set custom icons for the combo boxes
        runway_icon = icon_manager.get_runway_icon(16)
        threshold_icon = icon_manager.get_threshold_icon(16)
        
        # Unfortunately, QgsMapLayerComboBox doesn't have a direct way to set custom icons
        # But we can customize the appearance through styling
        
        # Add tooltips to make the purpose clearer
        dockwidget.runwayLayerCombo.setToolTip(
            "🛬 Select Runway Layer Centerline\n"
            "Choose the vector layer containing runway geometries.\n"
            "Should contain LineString or Polygon features representing runways."
        )
        
        dockwidget.thresholdLayerCombo.setToolTip(
            "🎯 Select threshold layer\n" 
            "Choose the vector layer containing runway threshold points.\n"
            "Should contain Point features at runway ends."
        )
        
        print("qOLS: Custom icons and tooltips applied to combo boxes")
        
    except Exception as e:
        print(f"qOLS: Error applying custom icons: {e}")

def enhance_combo_styling():
    """Return enhanced CSS for combo boxes with better visual indicators"""
    return """
    /* Enhanced QgsMapLayerComboBox styling */
    QgsMapLayerComboBox {
        background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                  stop: 0 #ffffff, stop: 1 #f8f9fa);
        border: 2px solid #e9ecef;
        border-radius: 6px;
        padding: 6px 12px;
        font-size: 10pt;
        font-weight: 500;
        color: #2c3e50;
        min-height: 20px;
    }
    
    QgsMapLayerComboBox:hover {
        border-color: #3498db;
        box-shadow: 0 0 0 3px rgba(52, 152, 219, 0.1);
    }
    
    QgsMapLayerComboBox:focus {
        border-color: #3498db;
        box-shadow: 0 0 0 3px rgba(52, 152, 219, 0.2);
        outline: none;
    }
    
    QgsMapLayerComboBox::drop-down {
        subcontrol-origin: padding;
        subcontrol-position: top right;
        width: 20px;
        border-left: 1px solid #e9ecef;
        border-top-right-radius: 6px;
        border-bottom-right-radius: 6px;
        background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                  stop: 0 #ffffff, stop: 1 #f1f3f4);
    }
    
    QgsMapLayerComboBox::down-arrow {
        image: none;
        border-left: 4px solid transparent;
        border-right: 4px solid transparent;
        border-top: 5px solid #6c757d;
        width: 0;
        height: 0;
    }
    
    QgsMapLayerComboBox::down-arrow:hover {
        border-top-color: #3498db;
    }
    
    /* Custom styling for runway combo - blue accent */
    #runwayLayerCombo {
        border-left: 4px solid #3498db;
    }
    
    #runwayLayerCombo:hover {
        border-left: 4px solid #2980b9;
    }
    
    /* Custom styling for threshold combo - orange accent */  
    #thresholdLayerCombo {
        border-left: 4px solid #e67e22;
    }
    
    #thresholdLayerCombo:hover {
        border-left: 4px solid #d35400;
    }
    """
