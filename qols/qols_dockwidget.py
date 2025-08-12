import os
import sys
from qgis.PyQt import uic
from qgis.PyQt.QtCore import pyqtSignal, Qt
from qgis.PyQt.QtWidgets import QDockWidget
from qgis.core import QgsMapLayerProxyModel, QgsProject, Qgis

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
            
            # Configure layer combo boxes to only show vector layers
            self.runwayLayerCombo.setFilters(QgsMapLayerProxyModel.VectorLayer)
            self.thresholdLayerCombo.setFilters(QgsMapLayerProxyModel.VectorLayer)
            
            # Set default values
            self.useSelectedFeatureCheckBox.setChecked(True)
            
            # Connect signals
            self.calculateButton.clicked.connect(self.on_calculate_clicked)
            self.cancelButton.clicked.connect(self.on_close_clicked)
            self.directionButton.clicked.connect(self.toggle_direction)
            
            # Set initial direction
            self.direction_start_to_end = True
            self.update_direction_button()
            
            print("QOLS: QolsDockWidget initialized successfully")
            
        except Exception as e:
            print(f"QOLS: Error initializing QolsDockWidget: {e}")
            import traceback
            traceback.print_exc()
            raise

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
        """Validate that required layers are selected."""
        try:
            runway_layer = self.runwayLayerCombo.currentLayer()
            threshold_layer = self.thresholdLayerCombo.currentLayer()
            
            if not runway_layer:
                self.show_error_message("Please select a runway layer")
                return False
            
            if not threshold_layer:
                self.show_error_message("Please select a threshold layer")
                return False
            
            print(f"QOLS: Layers validated - Runway: {runway_layer.name()}, Threshold: {threshold_layer.name()}")
            return True
            
        except Exception as e:
            print(f"QOLS: Error validating layers: {e}")
            self.show_error_message(f"Error validating layers: {str(e)}")
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
            # Get layer information
            runway_layer = self.runwayLayerCombo.currentLayer()
            threshold_layer = self.thresholdLayerCombo.currentLayer()
            use_selected_feature = self.useSelectedFeatureCheckBox.isChecked()
            
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
                'use_selected_feature': use_selected_feature,
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
        """Handle close event."""
        try:
            print("QOLS: Widget close event")
            self.closingPlugin.emit()
            event.accept()
        except Exception as e:
            print(f"QOLS: Error in close event: {e}")
            event.accept()
