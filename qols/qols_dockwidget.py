import os
import sys
from qgis.PyQt import uic
from qgis.PyQt.QtCore import pyqtSignal, Qt
from qgis.PyQt.QtWidgets import QDockWidget
from qgis.core import QgsMapLayerProxyModel, QgsProject, Qgis, QgsWkbTypes, QgsVectorLayer

# Load the UI file
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'qols_panel_base.ui'))

class QolsDockWidget(QDockWidget, FORM_CLASS):
    closingPlugin = pyqtSignal()
    calculateClicked = pyqtSignal()
    closeClicked = pyqtSignal()

    def __init__(self, iface, parent=None):
        """Constructor with enhanced error handling and layer management."""
        super(QolsDockWidget, self).__init__(parent)
        self.iface = iface
        
        try:
            print("QOLS: Initializing QolsDockWidget")
            self.setupUi(self)
            print("QOLS: Setting up UI")
            
            # Configure layer combo boxes with geometry filtering
            self.setup_layer_filters()
            
            # Set default values - separate controls for each layer
            self.useSelectedRunwayCheckBox.setChecked(False)
            self.useSelectedThresholdCheckBox.setChecked(False)
            
            # Connect signals for real-time feedback
            self.useSelectedRunwayCheckBox.toggled.connect(self.update_selection_info)
            self.useSelectedThresholdCheckBox.toggled.connect(self.update_selection_info)
            self.runwayLayerCombo.layerChanged.connect(self.update_selection_info)
            self.thresholdLayerCombo.layerChanged.connect(self.update_selection_info)
            
            # SAFETY: Connect to layer combo changes for immediate validation
            self.runwayLayerCombo.layerChanged.connect(self.validate_layer_change)
            self.thresholdLayerCombo.layerChanged.connect(self.validate_layer_change)
            
            # Connect signals
            self.calculateButton.clicked.connect(self.on_calculate_clicked)
            self.cancelButton.clicked.connect(self.on_close_clicked)
            self.directionButton.clicked.connect(self.toggle_direction)
            
            # Set initial direction
            self.direction_start_to_end = True
            self.update_direction_button()
            
            # Update selection info initially
            self.update_selection_info()
            
            print("QOLS: QolsDockWidget initialized successfully")
            
        except Exception as e:
            print(f"QOLS: Error initializing QolsDockWidget: {e}")
            import traceback
            traceback.print_exc()
            raise

    def setup_layer_filters(self):
        """Configure layer combo boxes with geometry-specific filtering."""
        try:
            print("QOLS: Setting up layer filters")
            
            # Configure runway layer combo - only show LINE geometry layers
            self.runwayLayerCombo.setFilters(QgsMapLayerProxyModel.VectorLayer)
            self.runwayLayerCombo.setExceptedLayerList([])
            
            # Configure threshold layer combo - only show POINT geometry layers  
            self.thresholdLayerCombo.setFilters(QgsMapLayerProxyModel.VectorLayer)
            self.thresholdLayerCombo.setExceptedLayerList([])
            
            # Apply geometry filtering
            self.apply_geometry_filters()
            
            # Connect to layer changes to reapply filters
            QgsProject.instance().layersAdded.connect(self.apply_geometry_filters)
            QgsProject.instance().layersRemoved.connect(self.apply_geometry_filters)
            
            print("QOLS: Layer filters configured successfully")
            
        except Exception as e:
            print(f"QOLS: Error setting up layer filters: {e}")

    def apply_geometry_filters(self):
        """Apply geometry-specific filters to layer combo boxes."""
        try:
            # Get all vector layers
            vector_layers = [layer for layer in QgsProject.instance().mapLayers().values() 
                           if isinstance(layer, QgsVectorLayer)]
            
            # Filter runway layers - only show LINE geometry
            runway_excluded = []
            threshold_excluded = []
            
            for layer in vector_layers:
                if layer.geometryType() != QgsWkbTypes.LineGeometry:
                    runway_excluded.append(layer)
                    
                if layer.geometryType() != QgsWkbTypes.PointGeometry:
                    threshold_excluded.append(layer)
            
            # Apply exclusion lists
            self.runwayLayerCombo.setExceptedLayerList(runway_excluded)
            self.thresholdLayerCombo.setExceptedLayerList(threshold_excluded)
            
            print(f"QOLS: Applied geometry filters - Runway excluded: {len(runway_excluded)}, Threshold excluded: {len(threshold_excluded)}")
            
        except Exception as e:
            print(f"QOLS: Error applying geometry filters: {e}")

    def update_selection_info(self):
        """Update selection information in real-time."""
        try:
            runway_layer = self.runwayLayerCombo.currentLayer()
            threshold_layer = self.thresholdLayerCombo.currentLayer()
            
            use_runway_selected = self.useSelectedRunwayCheckBox.isChecked()
            use_threshold_selected = self.useSelectedThresholdCheckBox.isChecked()
            
            info_parts = []
            
            # Runway selection info
            if runway_layer:
                runway_selected = len(runway_layer.selectedFeatures())
                runway_total = runway_layer.featureCount()
                
                if use_runway_selected:
                    if runway_selected > 0:
                        info_parts.append(f"✅ Runway: {runway_selected}/{runway_total} selected")
                    else:
                        info_parts.append(f"⚠️ Runway: No features selected!")
                else:
                    info_parts.append(f"📄 Runway: Using all {runway_total} features")
            else:
                info_parts.append("❌ Runway: No layer selected")
            
            # Threshold selection info  
            if threshold_layer:
                threshold_selected = len(threshold_layer.selectedFeatures())
                threshold_total = threshold_layer.featureCount()
                
                if use_threshold_selected:
                    if threshold_selected > 0:
                        info_parts.append(f"✅ Threshold: {threshold_selected}/{threshold_total} selected")
                    else:
                        info_parts.append(f"⚠️ Threshold: No features selected!")
                else:
                    info_parts.append(f"📄 Threshold: Using all {threshold_total} features")
            else:
                info_parts.append("❌ Threshold: No layer selected")
            
            # Update the info label
            info_text = " | ".join(info_parts)
            self.selectionInfoLabel.setText(info_text)
            
            # Update tooltip with detailed info
            tooltip_text = (
                "Selection Status:\n"
                f"• Runway Layer: {'Selected features' if use_runway_selected else 'All features'}\n"
                f"• Threshold Layer: {'Selected features' if use_threshold_selected else 'All features'}\n\n"
                "Instructions:\n"
                "1. Select features in the map layers\n"
                "2. Check the boxes to use only selected features\n"
                "3. Uncheck to use all features in the layer"
            )
            self.selectionInfoLabel.setToolTip(tooltip_text)
            
        except Exception as e:
            print(f"QOLS: Error updating selection info: {e}")
            self.selectionInfoLabel.setText("Error updating selection info")

    def validate_layer_change(self):
        """Validate layers immediately when user changes selection."""
        try:
            runway_layer = self.runwayLayerCombo.currentLayer()
            threshold_layer = self.thresholdLayerCombo.currentLayer()
            
            # Validate runway layer
            if runway_layer:
                if runway_layer.geometryType() != QgsWkbTypes.LineGeometry:
                    geom_type = self.get_layer_geometry_info(runway_layer)
                    self.show_error_message(
                        f"Invalid Runway Layer!\n"
                        f"'{runway_layer.name()}' contains {geom_type} geometry.\n"
                        f"Runway layer must contain LINE geometry (runway lines)."
                    )
                    # Reset to no selection
                    self.runwayLayerCombo.setCurrentIndex(-1)
                    return
            
            # Validate threshold layer
            if threshold_layer:
                if threshold_layer.geometryType() != QgsWkbTypes.PointGeometry:
                    geom_type = self.get_layer_geometry_info(threshold_layer)
                    self.show_error_message(
                        f"Invalid Threshold Layer!\n"
                        f"'{threshold_layer.name()}' contains {geom_type} geometry.\n"
                        f"Threshold layer must contain POINT geometry (threshold points)."
                    )
                    # Reset to no selection
                    self.thresholdLayerCombo.setCurrentIndex(-1)
                    return
            
            # If both layers are valid, update status
            self.update_selection_info()
            
        except Exception as e:
            print(f"QOLS: Error in layer change validation: {e}")

    def get_layer_geometry_info(self, layer):
        """Get human-readable geometry type information for a layer."""
        try:
            if not isinstance(layer, QgsVectorLayer):
                return "Not a vector layer"
                
            geom_type = layer.geometryType()
            wkb_type = layer.wkbType()
            
            if geom_type == QgsWkbTypes.PointGeometry:
                return "Point"
            elif geom_type == QgsWkbTypes.LineGeometry:
                return "Line"
            elif geom_type == QgsWkbTypes.PolygonGeometry:
                return "Polygon"
            else:
                return f"Unknown ({geom_type})"
                
        except Exception as e:
            return f"Error: {e}"

    def get_layer_summary(self):
        """Get summary of available layers for debugging."""
        try:
            vector_layers = [layer for layer in QgsProject.instance().mapLayers().values() 
                           if isinstance(layer, QgsVectorLayer)]
            
            summary = []
            summary.append("=== LAYER SUMMARY ===")
            
            line_layers = []
            point_layers = []
            polygon_layers = []
            other_layers = []
            
            for layer in vector_layers:
                layer_info = f"'{layer.name()}' ({self.get_layer_geometry_info(layer)}, {layer.featureCount()} features)"
                
                if layer.geometryType() == QgsWkbTypes.LineGeometry:
                    line_layers.append(layer_info)
                elif layer.geometryType() == QgsWkbTypes.PointGeometry:
                    point_layers.append(layer_info)
                elif layer.geometryType() == QgsWkbTypes.PolygonGeometry:
                    polygon_layers.append(layer_info)
                else:
                    other_layers.append(layer_info)
            
            summary.append(f"LINE layers (for Runway): {len(line_layers)}")
            for layer_info in line_layers:
                summary.append(f"  • {layer_info}")
            
            summary.append(f"POINT layers (for Threshold): {len(point_layers)}")
            for layer_info in point_layers:
                summary.append(f"  • {layer_info}")
            
            if polygon_layers:
                summary.append(f"POLYGON layers (not usable): {len(polygon_layers)}")
                for layer_info in polygon_layers:
                    summary.append(f"  • {layer_info}")
            
            if other_layers:
                summary.append(f"OTHER geometry layers: {len(other_layers)}")
                for layer_info in other_layers:
                    summary.append(f"  • {layer_info}")
            
            return "\n".join(summary)
            
        except Exception as e:
            return f"Error getting layer summary: {e}"

    def toggle_direction(self):
        """Toggle direction between Start to End and End to Start."""
        self.direction_start_to_end = not self.direction_start_to_end
        self.update_direction_button()

    def update_direction_button(self):
        """Update the direction button text."""
        if self.direction_start_to_end:
            self.directionButton.setText("Direction: Start to End")
        else:
            self.directionButton.setText("Direction: End to Start")

    def on_calculate_clicked(self):
        """Handle calculate button click with validation."""
        try:
            print("QOLS: Calculate button clicked")
            
            # Validate layers
            if not self.validate_layers():
                return
            
            # Show friendly message
            self.show_info_message("Starting calculation...")
            
            # Emit signal
            self.calculateClicked.emit()
            
        except Exception as e:
            print(f"QOLS: Error in calculate clicked: {e}")
            self.show_error_message(f"Error starting calculation: {str(e)}")

    def validate_layers(self):
        """Validate that required layers are selected with correct geometry types - ULTRA ROBUST VERSION."""
        try:
            print("QOLS: Starting comprehensive layer validation...")
            
            runway_layer = self.runwayLayerCombo.currentLayer()
            threshold_layer = self.thresholdLayerCombo.currentLayer()
            
            # CRITICAL CHECK 1: Ensure layers are selected
            if not runway_layer:
                self.show_error_message(
                    "No Runway Layer Selected!\n\n"
                    "Please select a runway layer from the dropdown.\n"
                    "The runway layer must contain LINE geometry (runway lines)."
                )
                return False
            
            if not threshold_layer:
                self.show_error_message(
                    "No Threshold Layer Selected!\n\n"
                    "Please select a threshold layer from the dropdown.\n"
                    "The threshold layer must contain POINT geometry (threshold points)."
                )
                return False
            
            # CRITICAL CHECK 2: Ensure layers are valid QGIS objects
            if not isinstance(runway_layer, QgsVectorLayer):
                self.show_error_message(
                    f"Invalid Runway Layer Object!\n\n"
                    f"Selected object is not a valid vector layer: {type(runway_layer)}\n"
                    f"Please select a different runway layer."
                )
                return False
            
            if not isinstance(threshold_layer, QgsVectorLayer):
                self.show_error_message(
                    f"Invalid Threshold Layer Object!\n\n"
                    f"Selected object is not a valid vector layer: {type(threshold_layer)}\n"
                    f"Please select a different threshold layer."
                )
                return False
            
            # CRITICAL CHECK 3: Ensure layers are still in project
            project_layers = list(QgsProject.instance().mapLayers().values())
            if runway_layer not in project_layers:
                self.show_error_message(
                    f"Runway Layer Not Found!\n\n"
                    f"Layer '{runway_layer.name()}' is no longer in the project.\n"
                    f"It may have been removed. Please select a different runway layer."
                )
                return False
            
            if threshold_layer not in project_layers:
                self.show_error_message(
                    f"Threshold Layer Not Found!\n\n"
                    f"Layer '{threshold_layer.name()}' is no longer in the project.\n"
                    f"It may have been removed. Please select a different threshold layer."
                )
                return False
            
            # CRITICAL CHECK 4: Ensure layers are valid and accessible
            if not runway_layer.isValid():
                self.show_error_message(
                    f"Corrupted Runway Layer!\n\n"
                    f"Layer '{runway_layer.name()}' is invalid or corrupted.\n"
                    f"Please check the layer source and select a different runway layer."
                )
                return False
            
            if not threshold_layer.isValid():
                self.show_error_message(
                    f"Corrupted Threshold Layer!\n\n"
                    f"Layer '{threshold_layer.name()}' is invalid or corrupted.\n"
                    f"Please check the layer source and select a different threshold layer."
                )
                return False
            
            # CRITICAL CHECK 5: Validate runway layer geometry (must be LINE)
            if runway_layer.geometryType() != QgsWkbTypes.LineGeometry:
                runway_geom_type = self.get_layer_geometry_info(runway_layer)
                self.show_error_message(
                    f"Wrong Geometry Type for Runway!\n\n"
                    f"Layer: '{runway_layer.name()}'\n"
                    f"Current geometry: {runway_geom_type}\n"
                    f"Required geometry: LINE (runway lines)\n\n"
                    f"Please select a layer containing runway lines."
                )
                return False
            
            # CRITICAL CHECK 6: Validate threshold layer geometry (must be POINT)
            if threshold_layer.geometryType() != QgsWkbTypes.PointGeometry:
                threshold_geom_type = self.get_layer_geometry_info(threshold_layer)
                self.show_error_message(
                    f"Wrong Geometry Type for Threshold!\n\n"
                    f"Layer: '{threshold_layer.name()}'\n"
                    f"Current geometry: {threshold_geom_type}\n"
                    f"Required geometry: POINT (threshold points)\n\n"
                    f"Please select a layer containing threshold points."
                )
                return False
            
            # CRITICAL CHECK 7: Ensure layers contain features
            runway_total = runway_layer.featureCount()
            threshold_total = threshold_layer.featureCount()
            
            if runway_total == 0:
                self.show_error_message(
                    f"Empty Runway Layer!\n\n"
                    f"Layer '{runway_layer.name()}' contains no features.\n"
                    f"Please select a runway layer with runway line features."
                )
                return False
            
            if threshold_total == 0:
                self.show_error_message(
                    f"Empty Threshold Layer!\n\n"
                    f"Layer '{threshold_layer.name()}' contains no features.\n"
                    f"Please select a threshold layer with threshold point features."
                )
                return False
            
            # CRITICAL CHECK 8: Validate selected features if required
            use_runway_selected = self.useSelectedRunwayCheckBox.isChecked()
            use_threshold_selected = self.useSelectedThresholdCheckBox.isChecked()
            
            # Validate runway selection
            if use_runway_selected:
                runway_selected = len(runway_layer.selectedFeatures())
                if runway_selected == 0:
                    self.show_error_message(
                        f"No Runway Features Selected!\n\n"
                        f"'Use Selected Runway Features' is checked but no features are selected.\n\n"
                        f"Please either:\n"
                        f"• Select runway line features in '{runway_layer.name()}' layer, OR\n"
                        f"• Uncheck 'Use Selected Runway Features' to use all runway features"
                    )
                    return False
                print(f"QOLS: Using {runway_selected} selected runway features")
            else:
                print(f"QOLS: Using all {runway_total} runway features")
            
            # Validate threshold selection  
            if use_threshold_selected:
                threshold_selected = len(threshold_layer.selectedFeatures())
                if threshold_selected == 0:
                    self.show_error_message(
                        f"No Threshold Features Selected!\n\n"
                        f"'Use Selected Threshold Features' is checked but no features are selected.\n\n"
                        f"Please either:\n"
                        f"• Select threshold point features in '{threshold_layer.name()}' layer, OR\n"
                        f"• Uncheck 'Use Selected Threshold Features' to use all threshold features"
                    )
                    return False
                print(f"QOLS: Using {threshold_selected} selected threshold features")
            else:
                print(f"QOLS: Using all {threshold_total} threshold features")
            
            # SUCCESS: All validations passed
            print(f"QOLS: ✅ ALL VALIDATIONS PASSED")
            print(f"QOLS: Runway Layer: '{runway_layer.name()}' (LINE geometry, {runway_total} features)")
            print(f"QOLS: Threshold Layer: '{threshold_layer.name()}' (POINT geometry, {threshold_total} features)")
            print(f"QOLS: Selection Mode: Runway={'selected' if use_runway_selected else 'all'}, Threshold={'selected' if use_threshold_selected else 'all'}")
            
            return True
            
        except Exception as e:
            print(f"QOLS: CRITICAL ERROR in layer validation: {e}")
            import traceback
            traceback.print_exc()
            self.show_error_message(
                f"Critical Validation Error!\n\n"
                f"An unexpected error occurred during validation:\n{str(e)}\n\n"
                f"Please check the console for details and try again."
            )
            return False

    def show_info_message(self, message):
        """Show friendly info message to user."""
        try:
            self.iface.messageBar().pushMessage(
                "QOLS Info", 
                message, 
                level=Qgis.Info,
                duration=3
            )
        except Exception as e:
            print(f"QOLS: Error showing info message: {e}")

    def show_error_message(self, message):
        """Show friendly error message to user."""
        try:
            self.iface.messageBar().pushMessage(
                "QOLS Error", 
                message, 
                level=Qgis.Critical,
                duration=5
            )
        except Exception as e:
            print(f"QOLS: Error showing error message: {e}")

    def on_close_clicked(self):
        """Handle close button click."""
        try:
            print("QOLS: Close button clicked")
            self.closeClicked.emit()
        except Exception as e:
            print(f"QOLS: Error in close clicked: {e}")

    def get_parameters(self):
        """Get all parameters from the UI with validation."""
        try:
            # CRITICAL VALIDATION: Re-verify layers before creating parameters
            runway_layer = self.runwayLayerCombo.currentLayer()
            threshold_layer = self.thresholdLayerCombo.currentLayer()
            
            # SAFETY CHECK: Ensure layers are still valid (could have been removed)
            if not runway_layer:
                raise Exception("CRITICAL ERROR: No runway layer selected. This should not happen after validation.")
            
            if not threshold_layer:
                raise Exception("CRITICAL ERROR: No threshold layer selected. This should not happen after validation.")
            
            # SAFETY CHECK: Ensure layers are still in project (could have been removed)
            project_layers = QgsProject.instance().mapLayers().values()
            if runway_layer not in project_layers:
                raise Exception(f"CRITICAL ERROR: Runway layer '{runway_layer.name()}' no longer exists in project.")
            
            if threshold_layer not in project_layers:
                raise Exception(f"CRITICAL ERROR: Threshold layer '{threshold_layer.name()}' no longer exists in project.")
            
            # SAFETY CHECK: Re-verify geometry types (layers could have changed)
            if runway_layer.geometryType() != QgsWkbTypes.LineGeometry:
                raise Exception(f"CRITICAL ERROR: Runway layer '{runway_layer.name()}' geometry changed to {self.get_layer_geometry_info(runway_layer)}.")
            
            if threshold_layer.geometryType() != QgsWkbTypes.PointGeometry:
                raise Exception(f"CRITICAL ERROR: Threshold layer '{threshold_layer.name()}' geometry changed to {self.get_layer_geometry_info(threshold_layer)}.")
            
            # Get separate selection settings for each layer
            use_runway_selected = self.useSelectedRunwayCheckBox.isChecked()
            use_threshold_selected = self.useSelectedThresholdCheckBox.isChecked()
            
            # SAFETY CHECK: Re-verify feature selections if required
            if use_runway_selected:
                runway_selected = len(runway_layer.selectedFeatures())
                if runway_selected == 0:
                    raise Exception(f"CRITICAL ERROR: No runway features selected but 'Use Selected Runway Features' is checked.")
            
            if use_threshold_selected:
                threshold_selected = len(threshold_layer.selectedFeatures())
                if threshold_selected == 0:
                    raise Exception(f"CRITICAL ERROR: No threshold features selected but 'Use Selected Threshold Features' is checked.")
            
            # Get direction
            direction = 0 if self.direction_start_to_end else -1
            
            # Get current tab to determine surface type
            current_tab = self.scriptTabWidget.currentWidget()
            current_tab_index = self.scriptTabWidget.currentIndex()
            surface_type = self.scriptTabWidget.tabText(current_tab_index)
            
            # Get parameters based on current tab
            if surface_type == "Approach Surface":
                specific_params = {
                    'code': self.spin_code.value(),
                    'typeAPP': self.combo_typeAPP.currentText(),
                    'widthApp': self.spin_widthApp.value(),
                    'Z0': self.spin_Z0.value(),
                    'ZE': self.spin_ZE.value(),
                    'ARPH': self.spin_ARPH.value(),
                    'IHSlope': self.spin_IHSlope.value() / 100.0,  # Convert to decimal
                    'L1': self.spin_L1.value(),
                    'L2': self.spin_L2.value(),
                    'LH': self.spin_LH.value()
                }
            elif surface_type == "Conical":
                specific_params = {
                    'radius': self.spin_L_conical.value(),  # Distance L is the radius
                    'offset_right': self.spin_o1_conical.value(),  # Offset Right
                    'offset_left': self.spin_o2_conical.value()   # Offset Left
                }
            elif surface_type == "Inner Horizontal":
                specific_params = {
                    'radius': self.spin_L_inner.value(),          # Distance L is the radius
                    'offset_right': self.spin_o1_inner.value(),   # Offset Right
                    'offset_left': self.spin_o2_inner.value()     # Offset Left
                }
            elif surface_type == "Outer Horizontal":
                specific_params = {
                    'height': self.spin_outer_horizontal_height.value(),
                    'radius': self.spin_outer_horizontal_radius.value()
                }
            elif surface_type == "Take-off Surface":
                specific_params = {
                    'code': self.spin_code_takeoff.value(),
                    'typeAPP': self.combo_typeAPP_takeoff.currentText(),
                    'widthApp': self.spin_widthApp_takeoff.value(),
                    'widthDep': self.spin_widthDep_takeoff.value(),
                    'maxWidthDep': self.spin_maxWidthDep_takeoff.value(),
                    'CWYLength': self.spin_CWYLength_takeoff.value(),
                    'Z0': self.spin_Z0_takeoff.value(),
                    'ZE': self.spin_ZE_takeoff.value(),
                    'ARPH': self.spin_ARPH_takeoff.value()
                    # NOTA: IHSlope, L1, L2, LH no se usan en cálculos reales del script
                }
            elif surface_type == "Transitional Surface":
                specific_params = {
                    'slope': self.spin_transitional_slope.value() / 100.0,  # Convert to decimal
                    'height': self.spin_transitional_height.value()
                }
            elif surface_type == "OFZ":
                specific_params = {
                    'width': self.spin_ofz_width.value(),
                    'length': self.spin_ofz_length.value(),
                    'height': self.spin_ofz_height.value()
                }
            else:
                specific_params = {}
            
            # Combine all parameters
            params = {
                'surface_type': surface_type,
                'runway_layer': runway_layer,
                'threshold_layer': threshold_layer,
                'use_runway_selected': use_runway_selected,
                'use_threshold_selected': use_threshold_selected,
                'direction': direction,
                'specific_params': specific_params
            }
            
            print(f"QOLS: Parameters collected for {surface_type}: {params}")
            return params
            
        except Exception as e:
            print(f"QOLS: Error getting parameters: {e}")
            self.show_error_message(f"Error collecting parameters: {str(e)}")
            return None

    def closeEvent(self, event):
        """Handle close event with proper cleanup."""
        try:
            print("QOLS: Widget close event")
            
            # Disconnect signals to prevent memory leaks
            try:
                QgsProject.instance().layersAdded.disconnect(self.apply_geometry_filters)
                QgsProject.instance().layersRemoved.disconnect(self.apply_geometry_filters)
                self.useSelectedRunwayCheckBox.toggled.disconnect(self.update_selection_info)
                self.useSelectedThresholdCheckBox.toggled.disconnect(self.update_selection_info)
                self.runwayLayerCombo.layerChanged.disconnect(self.update_selection_info)
                self.thresholdLayerCombo.layerChanged.disconnect(self.update_selection_info)
                self.runwayLayerCombo.layerChanged.disconnect(self.validate_layer_change)
                self.thresholdLayerCombo.layerChanged.disconnect(self.validate_layer_change)
            except:
                pass  # Signals might not be connected
            
            self.closingPlugin.emit()
            event.accept()
        except Exception as e:
            print(f"QOLS: Error in close event: {e}")
            event.accept()
