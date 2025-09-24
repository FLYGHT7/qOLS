import os
import sys
from qgis.PyQt import uic
from qgis.PyQt.QtCore import pyqtSignal, Qt, QTimer
from qgis.PyQt.QtWidgets import QDockWidget, QToolTip
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
            
            # Apply modern stylesheet
            self.apply_modern_stylesheet()
            
            # Configure numeric input validation for all QLineEdit widgets (formerly QDoubleSpinBox)
            self.setup_numeric_lineedit_validation()
            
            # Configure layer combo boxes with geometry filtering
            self.setup_layer_filters()
            
            # Apply enhanced combo styling 
            self.setup_enhanced_combos()
            
            # Setup tooltips for individual dropdown items (AFTER styling to avoid override)
            self.setup_dropdown_tooltips()

            # Wire Take-Off code change to apply defaults from table
            try:
                if hasattr(self, 'spin_code_takeoff'):
                    self.spin_code_takeoff.currentIndexChanged.connect(self.update_takeoff_defaults_from_code)
            except Exception as e:
                print(f"QOLS: Could not connect Take-Off code change handler: {e}")
            
            # MÉTODO ADICIONAL: Override showEvent para formatear cada vez que se muestre
            original_showEvent = self.showEvent
            def enhanced_showEvent(event):
                original_showEvent(event)
                # Formatear después de que el widget se muestre
                QTimer.singleShot(50, self.force_clean_display)
            self.showEvent = enhanced_showEvent
            
            # Set default values - separate controls for each layer
            self.useSelectedRunwayCheckBox.setChecked(False)
            self.useSelectedThresholdCheckBox.setChecked(False)
            
            # Initialize Take-Off Surface default values immediately
            self.initialize_takeoff_defaults()

            
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
            self.button_rotate_transitional.clicked.connect(self.toggle_transitional_direction)
            
            # Connect tab change to reinitialize defaults (helpful for widget visibility)
            self.scriptTabWidget.currentChanged.connect(self.on_tab_changed)
            
            # Set initial direction
            self.direction_start_to_end = True
            self.transitional_direction_normal = True  # True = normal (s=0), False = rotated (s=-1)

            # Update direction buttons and initial selection info
            self.update_direction_button()
            self.update_transitional_direction_button()
            self.update_selection_info()

            print("QOLS: QolsDockWidget initialized successfully")
            
        except Exception as e:
            print(f"QOLS: Error initializing QolsDockWidget: {e}")
            import traceback
            traceback.print_exc()
            raise

    def apply_modern_stylesheet(self):
        """Use native Qt styling for maximum compatibility and performance."""
        try:
            self.setStyleSheet("")
            print("QOLS: Using native Qt styling for maximum compatibility")
        except Exception as e:
            print(f"QOLS: Error clearing stylesheet: {e}")
            self.setStyleSheet("")

    def setup_numeric_lineedit_validation(self):
        """Configure numeric input validation for all QLineEdit widgets (formerly QDoubleSpinBox)."""
        try:
            from qgis.PyQt.QtCore import QRegExp
            from qgis.PyQt.QtGui import QRegExpValidator
            
            print("QOLS: Setting up numeric validation for QLineEdit widgets")
            
            lineedit_names = [
                'spin_widthApp', 'spin_Z0', 'spin_ZE', 'spin_ARPH', 
                'spin_L1', 'spin_L2', 'spin_LH',
                'spin_L_conical', 'spin_height_conical',
                'spin_L_inner', 'spin_height_inner',
                'spin_width_ofz', 'spin_Z0_ofz', 'spin_ZE_ofz', 'spin_ARPH_ofz', 'spin_IHSlope_ofz',
                'spin_radius_outer', 'spin_height_outer',
                'spin_widthDep_takeoff', 'spin_maxWidthDep_takeoff',
                'spin_CWYLength_takeoff', 'spin_Z0_takeoff',
                'spin_widthApp_transitional', 'spin_Z0_transitional', 'spin_ZE_transitional',
                'spin_ARPH_transitional', 'spin_IHSlope_transitional', 'spin_Tslope_transitional'
            ]
            
            default_values = {
                'spin_widthApp': '280.00', 'spin_Z0': '21.70', 'spin_ZE': '42.70', 'spin_ARPH': '15.00',
                'spin_L1': '60.00', 'spin_L2': '60.00', 'spin_LH': '0.00',
                'spin_L_conical': '6000.00', 'spin_height_conical': '60.00',
                'spin_L_inner': '4000.00', 'spin_height_inner': '45.00',
                'spin_width_ofz': '120.00', 'spin_Z0_ofz': '2548.00', 'spin_ZE_ofz': '2546.50',
                'spin_ARPH_ofz': '2548.00', 'spin_IHSlope_ofz': '33.30',
                'spin_radius_outer': '15000.00', 'spin_height_outer': '150.00'
            }
            
            # Allow unlimited decimals; optional sign and decimal part
            decimal_pattern = r'^-?\d*(?:\.\d*)?$'
            regex = QRegExp(decimal_pattern)
            validator = QRegExpValidator(regex)
            
            configured_count = 0
            for name in lineedit_names:
                try:
                    lineedit = getattr(self, name, None)
                    if lineedit and hasattr(lineedit, 'setText'):
                        lineedit.setValidator(validator)
                        lineedit.setText(default_values.get(name, '0.00'))
                        self._configure_smart_formatting(lineedit)
                        configured_count += 1
                        print(f"QOLS: Configured {name} - numeric validation and default value set")
                except Exception as e:
                    print(f"QOLS: Warning - could not configure {name}: {e}")
            
            print(f"QOLS: Successfully configured {configured_count} QLineEdit widgets with numeric validation")
            print("QOLS: All numeric inputs now support unlimited decimal precision with clean display")
        except Exception as e:
            print(f"QOLS: Error in numeric validation setup: {e}")

    def _configure_smart_formatting(self, lineedit):
        """Smart formatting for QLineEdit: show clean 2-decimals for simple values."""
        try:
            def format_on_focus_out():
                try:
                    text = lineedit.text().strip()
                    if text:
                        try:
                            value = float(text)
                            if abs(value - round(value)) < 1e-6:
                                lineedit.setText(f"{int(round(value))}.00")
                            elif abs(value - round(value, 2)) < 1e-6:
                                lineedit.setText(f"{value:.2f}")
                            # Otherwise, leave user's precision as-is
                        except ValueError:
                            lineedit.setText('0.00')
                except:
                    pass
            try:
                lineedit.editingFinished.connect(format_on_focus_out)
            except:
                pass
        except Exception as e:
            print(f"QOLS: Warning - smart formatting setup failed for {getattr(lineedit, 'objectName', lambda: '')()}: {e}")

    def initialize_takeoff_defaults(self):
        """Initialize default values for Take-Off and other surfaces."""
        try:
            print("QOLS: Initializing Take-Off Surface default values")
            takeoff_defaults = {
                'spin_widthDep_takeoff': 180.0,
                'spin_maxWidthDep_takeoff': 1800.0,
                'spin_CWYLength_takeoff': 0.0,
                'spin_Z0_takeoff': 2548.0
            }
            for widget_name, default_value in takeoff_defaults.items():
                self.set_numeric_value(widget_name, default_value)
                print(f"QOLS: Set {widget_name} = {default_value}")
        except Exception as e:
            print(f"QOLS: Error initializing Take-Off defaults: {e}")

        # Transitional defaults
        try:
            print("QOLS: Initializing Transitional Surface default values")
            transitional_defaults = {
                'spin_widthApp_transitional': '280.00',
                'spin_Z0_transitional': '2548.00',
                'spin_ZE_transitional': '2546.50',
                'spin_ARPH_transitional': '2548.00',
                'spin_IHSlope_transitional': '33.30',
                'spin_Tslope_transitional': '14.30'
            }
            for widget_name, default_value in transitional_defaults.items():
                self.set_numeric_value(widget_name, default_value)
                print(f"QOLS: Set {widget_name} = {default_value}")
            self.set_code_value('spin_code_transitional', 4)
            print("QOLS: Set spin_code_transitional = 4")
            try:
                self.combo_rwyClassification_transitional.setCurrentText('Precision Approach CAT I')
                print("QOLS: Set combo_rwyClassification_transitional = Precision Approach CAT I")
            except AttributeError:
                print("QOLS: combo_rwyClassification_transitional not found")
        except Exception as e:
            print(f"QOLS: Error initializing Transitional defaults: {e}")

        # Other defaults
        try:
            print("QOLS: Initializing other surface default values")
            approach_defaults = {
                'spin_widthApp': 280.0,
                'spin_Z0': 2548.0,
                'spin_ZE': 2546.5,
                'spin_ARPH': 2548.0,
                'spin_L1': 3000.0,
                'spin_L2': 3600.0,
                'spin_LH': 8400.0
            }
            conical_defaults = {
                'spin_L_conical': 6000.0,
                'spin_height_conical': 60.0
            }
            inner_defaults = {
                'spin_L_inner': 4000.0,
                'spin_height_inner': 45.0
            }
            ofz_defaults = {
                'spin_width_ofz': 120.0,
                'spin_Z0_ofz': 2548.0,
                'spin_ZE_ofz': 2546.5,
                'spin_ARPH_ofz': 2548.0,
                'spin_IHSlope_ofz': 33.3
            }
            outer_defaults = {
                'spin_radius_outer': 15000.0,
                'spin_height_outer': 150.0
            }
            all_defaults = {**approach_defaults, **conical_defaults, **inner_defaults, **ofz_defaults, **outer_defaults}
            for widget_name, default_value in all_defaults.items():
                self.set_numeric_value(widget_name, default_value)
                print(f"QOLS: Set {widget_name} = {default_value}")
            # Initialize code dropdowns
            self.set_code_value('spin_code', 4)
            self.set_code_value('spin_code_ofz', 4)
            self.set_code_value('spin_code_takeoff', 4)
            self.set_code_value('spin_code_outer', 4)
            print("QOLS: Set all code widgets = 4")
            # Apply defaults from table for initial Take-Off code
            try:
                self.update_takeoff_defaults_from_code()
            except Exception as e:
                print(f"QOLS: Could not initialize Take-Off defaults: {e}")
            
            # Initialize RWY Classification dropdowns
            try:
                self.combo_rwyClassification.setCurrentText('Precision Approach CAT I')
                print("QOLS: Set combo_rwyClassification = Precision Approach CAT I")
            except:
                print("QOLS: combo_rwyClassification not found")
                
            try:
                self.combo_rwyClassification_ofz.setCurrentText('Precision Approach CAT I')
                print("QOLS: Set combo_rwyClassification_ofz = Precision Approach CAT I")
            except:
                print("QOLS: combo_rwyClassification_ofz not found")
                
        except Exception as e:
            print(f"QOLS: Error initializing other surface defaults: {e}")

    

    def get_numeric_value(self, widget_name):
        """Get numeric value from QLineEdit widget, returns float or 0.0 if invalid."""
        try:
            widget = getattr(self, widget_name, None)
            if widget and hasattr(widget, 'text'):
                text = widget.text().strip()
                if text:
                    return float(text)
            return 0.0
        except (ValueError, AttributeError):
            return 0.0

    def get_code_value(self, widget_name):
        """Get code value from QComboBox or QSpinBox widget, returns int."""
        try:
            widget = getattr(self, widget_name, None)
            if widget is None:
                return 1  # Default code value
            
            # Handle QComboBox (new code dropdowns)
            if hasattr(widget, 'currentText'):
                text = widget.currentText().strip()
                if text:
                    return int(text)
            
            # Handle QSpinBox (legacy code widgets)
            if hasattr(widget, 'value'):
                return widget.value()
                
            return 1  # Default code value
        except (ValueError, AttributeError):
            return 1  # Default code value

    def set_code_value(self, widget_name, value):
        """Set code value in QComboBox or QSpinBox widget."""
        try:
            widget = getattr(self, widget_name, None)
            if widget is None:
                print(f"QOLS: Warning - code widget {widget_name} not found")
                return
            
            # Handle QComboBox (new code dropdowns)
            if hasattr(widget, 'setCurrentText'):
                widget.setCurrentText(str(value))
                print(f"QOLS: Set {widget_name} (QComboBox) = {value}")
                return
            
            # Handle QSpinBox (legacy code widgets)
            if hasattr(widget, 'setValue'):
                widget.setValue(value)
                print(f"QOLS: Set {widget_name} (QSpinBox) = {value}")
                return
                
            print(f"QOLS: Warning - {widget_name} is neither QComboBox nor QSpinBox")
        except Exception as e:
            print(f"QOLS: Error setting code value for {widget_name}: {e}")

    def set_numeric_value(self, widget_name, value):
        """Set numeric value in widget - works with both QLineEdit and QDoubleSpinBox."""
        try:
            widget = getattr(self, widget_name, None)
            if widget is None:
                print(f"QOLS: Warning - widget {widget_name} not found")
                return
                
            if hasattr(widget, 'setValue'):  # QDoubleSpinBox or QSpinBox
                widget.setValue(float(value))
                print(f"QOLS: Set {widget_name} = {value} (using setValue)")
            elif hasattr(widget, 'setText'):  # QLineEdit
                if isinstance(value, (int, float)):
                    if abs(value - round(value)) < 0.000001:
                        widget.setText(f"{int(round(value))}.00")
                    else:
                        widget.setText(f"{value:.8f}".rstrip('0').rstrip('.'))
                else:
                    widget.setText(str(value))
                print(f"QOLS: Set {widget_name} = {value} (using setText)")
            else:
                print(f"QOLS: Warning - widget {widget_name} has no setValue or setText method")
                
        except Exception as e:
            print(f"QOLS: Warning - could not set value for {widget_name}: {e}")

    # Legacy QDoubleSpinBox helpers removed since all numeric inputs are QLineEdit now.

    def _configure_smart_decimal_display(self, spinbox):
        """
        Configurar display inteligente de decimales para requerimiento del cliente:
        - PERMITE: Input de hasta 6 decimales (ej: 60.123456)
        - MUESTRA: Solo decimales necesarios por defecto (ej: 60.000 no 60.000000)
        - ALMACENA: Valor exacto que ingresó el usuario
        
        Esto resuelve el problema específico del cliente en Conical e Inner Horizontal.
        """
        try:
            # ENFOQUE SIMPLE: Configurar step y comportamiento
            # Qt QDoubleSpinBox con 6 decimales + step inteligente
            
            # Configurar step más pequeño para permitir entrada precisa
            spinbox.setSingleStep(0.001)
            
            # Configurar para que no muestre trailing zeros innecesarios
            # (Esto es limitado en Qt, pero mejoramos la experiencia)
            
            # Store reference for potential custom formatting
            spinbox._smart_display_enabled = True
            
            # IMPORTANTE: El spinbox ya tiene 6 decimales configurados,
            # esto permite input preciso como requiere el cliente
            
            print(f"QOLS: Smart display enabled for {spinbox.objectName()} (6 decimals input)")
            
        except Exception as e:
            print(f"QOLS: Warning - smart display setup failed: {e}")

    def _format_smart_display(self, spinbox, value):
        """
        Nota: Qt QDoubleSpinBox tiene limitaciones para formateo dinámico.
        Este método documenta la intención, pero la implementación real
        requiere subclassing QDoubleSpinBox o usar QLineEdit personalizado.
        
        Para el requerimiento inmediato del cliente:
        - 6 decimales en UI = permite input preciso ✓
        - Valor se almacena exacto ✓  
        - Display puede mostrar 60.000000 pero funcionalmente correcto ✓
        """
        try:
            # Placeholder para futura mejora de display
            # Por ahora, 6 decimales cumplen el requerimiento de precisión
            pass
            
        except Exception as e:
            print(f"QOLS: Error in display formatting: {e}")

    def _configure_clean_display(self, spinbox):
        """
        Configure spinbox for clean decimal display:
        - Allow up to 6 decimals for precision
        - Show minimal decimals by default
        - This addresses client requirement: precision without ugly display
        """
        try:
            # Key solution: Set special property to control display
            # This allows 6 decimal input but shows clean values
            
            # Store original value
            original_value = spinbox.value()
            
            # Configure for clean display
            spinbox.setSpecialValueText("")  # Clean empty state
            
            # Set reasonable step for UI interaction
            spinbox.setSingleStep(0.01)
            
            # Restore value (this will use clean formatting)
            spinbox.setValue(original_value)
            
            print(f"QOLS: Clean display configured for {spinbox.objectName()}")
            
        except Exception as e:
            print(f"QOLS: Warning - could not configure clean display: {e}")

    def _format_display_value(self, spinbox, value):
        """
        Custom formatter that shows clean decimal display.
        Shows appropriate decimals based on the actual value.
        """
        try:
            # This method provides custom formatting logic
            # Currently using Qt's built-in formatting with 6 decimal capability
            pass
            
        except Exception as e:
            print(f"QOLS: Error in display formatting: {e}")

    def format_spinbox_display(self, spinbox, value):
        """Format spinbox display to show appropriate number of decimals."""
        try:
            # This method is kept for future enhancements
            # Currently, we rely on Qt's default formatting with increased decimal places
            pass
            
        except Exception as e:
            print(f"QOLS: Error formatting spinbox display: {e}")

    def apply_initial_clean_formatting(self):
        """
        Aplicar formateo inicial limpio INMEDIATAMENTE después del setup UI.
        Esto asegura que los campos se vean 60.00 desde el primer momento.
        """
        try:
            print("QOLS: Applying initial clean formatting")
            
            # Lista de campos que necesitan formateo limpio inicial
            spinbox_names = [
                'spin_L_conical', 'spin_height_conical',
                'spin_L_inner', 'spin_height_inner',
                'spin_widthApp', 'spin_Z0', 'spin_ZE', 'spin_ARPH', 
                'spin_L1', 'spin_L2', 'spin_LH',
                'spin_width_ofz', 'spin_Z0_ofz', 'spin_ZE_ofz', 'spin_ARPH_ofz', 'spin_IHSlope_ofz',
                'spin_radius_outer', 'spin_height_outer'
            ]
            
            for name in spinbox_names:
                try:
                    spinbox = getattr(self, name, None)
                    if spinbox:
                        current_value = spinbox.value()
                        
                        # Formatear el valor para display limpio
                        if abs(current_value - round(current_value)) < 1e-9:
                            # Es entero, mostrar con .00
                            clean_text = f"{int(round(current_value))}.00"
                        else:
                            # Tiene decimales, formatear inteligentemente
                            clean_text = f"{current_value:.6f}".rstrip('0').rstrip('.')
                            if '.' not in clean_text:
                                clean_text += ".00"
                            elif len(clean_text.split('.')[1]) == 1:
                                clean_text += "0"
                        
                        # FORZAR el display limpio directamente
                        spinbox.lineEdit().setText(clean_text)
                        
                        print(f"QOLS: {name} formatted: {current_value} → {clean_text}")
                        
                except Exception as e:
                    print(f"QOLS: Error formatting {name}: {e}")
            
            print("QOLS: Initial clean formatting applied successfully")
            
        except Exception as e:
            print(f"QOLS: Error in initial formatting: {e}")

    def force_initial_decimal_display(self):
        """
        Force initial 2-decimal display for all spinboxes after UI setup.
        Ensures clean initial appearance: 65.00, 280.00, etc.
        """
        try:
            print("QOLS: Forcing initial 2-decimal display for clean startup")
            
            # List of all QDoubleSpinBox widget names
            spinbox_names = [
                'spin_widthApp', 'spin_Z0', 'spin_ZE', 'spin_ARPH', 
                'spin_L1', 'spin_L2', 'spin_LH',
                'spin_L_conical', 'spin_height_conical',
                'spin_L_inner', 'spin_height_inner',
                'spin_width_ofz', 'spin_Z0_ofz', 'spin_ZE_ofz', 'spin_ARPH_ofz', 'spin_IHSlope_ofz',
                'spin_radius_outer', 'spin_height_outer'
            ]
            
            for name in spinbox_names:
                try:
                    spinbox = getattr(self, name, None)
                    if spinbox:
                        # Force to 2 decimals for initial display
                        spinbox.setDecimals(2)
                        
                        # Refresh the display
                        current_value = spinbox.value()
                        spinbox.setValue(current_value)
                        
                        # Reset expansion tracking
                        spinbox._has_been_expanded = False
                        
                        print(f"QOLS: Reset {name} to 2 decimals - shows {current_value:.2f}")
                        
                except Exception as e:
                    print(f"QOLS: Warning - could not reset {name}: {e}")
            
            print("QOLS: All spinboxes now show clean 2-decimal format for startup")
            
        except Exception as e:
            print(f"QOLS: Error in initial decimal display setup: {e}")

    def force_clean_display(self):
        """
        Forzar display limpio AGRESIVAMENTE.
        Se ejecuta múltiples veces hasta que funcione.
        """
        try:
            print("QOLS: FORCING clean display with AGGRESSIVE approach")
            
            # Lista de campos críticos que aparecen con muchos decimales
            critical_fields = [
                ('spin_L_conical', 6000.0),      # 6000.000000 → 6000.00
                ('spin_height_conical', 60.0),   # 60.000000 → 60.00
                ('spin_L_inner', 4000.0),        # 4000.000000 → 4000.00  
                ('spin_height_inner', 45.0)      # 45.000000 → 45.00
            ]
            
            # NUEVO: Campos de Take-Off Surface que deben mantener valores por defecto
            takeoff_fields = [
                ('spin_widthDep_takeoff', 180.0),
                ('spin_maxWidthDep_takeoff', 1800.0),
                ('spin_CWYLength_takeoff', 0.0),
                ('spin_Z0_takeoff', 2548.0)
            ]
            
            # Combinar todos los campos críticos
            all_critical_fields = critical_fields + takeoff_fields
            
            for name, expected_value in all_critical_fields:
                try:
                    # For QLineEdit widgets (all numeric inputs)
                    widget = getattr(self, name, None)
                    if widget and hasattr(widget, 'setText'):
                        current_text = widget.text()
                        
                        # Format expected value cleanly
                        if abs(expected_value - round(expected_value)) < 1e-9:
                            clean_text = f"{int(round(expected_value))}.00"
                        else:
                            clean_text = f"{expected_value:.2f}"
                        
                        # Only update if empty or different
                        if not current_text or current_text != clean_text:
                            widget.setText(clean_text)
                            widget.update()
                            print(f"QOLS: FORCE QLineEdit {name}: '{current_text}' → '{clean_text}'")
                        
                except Exception as e:
                    print(f"QOLS: Error aggressive forcing {name}: {e}")
            
            # Note: Nuclear method section removed - no longer needed since all widgets are QLineEdit
            
            print("QOLS: AGGRESSIVE clean display completed")
            
        except Exception as e:
            print(f"QOLS: Error in aggressive force_clean_display: {e}")

    def setup_layer_filters(self):
        """Configure layer combo boxes with geometry-specific filtering."""
        try:
            print("QOLS: Setting up layer filters")
            
            # Configure runway layer combo - only show LINE geometry layers
            self.runwayLayerCombo.setFilters(QgsMapLayerProxyModel.VectorLayer)
            self.runwayLayerCombo.setExceptedLayerList([])
            # Enable additional display options for runway combo
            self.runwayLayerCombo.setShowCrs(False)
            self.runwayLayerCombo.setAllowEmptyLayer(False)
            
            # Configure threshold layer combo - only show POINT geometry layers  
            self.thresholdLayerCombo.setFilters(QgsMapLayerProxyModel.VectorLayer)
            self.thresholdLayerCombo.setExceptedLayerList([])
            # Enable additional display options for threshold combo
            self.thresholdLayerCombo.setShowCrs(False)
            self.thresholdLayerCombo.setAllowEmptyLayer(False)
            
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

    def setup_dropdown_tooltips(self):
        """Setup enhanced tooltips for dropdown items - QGIS native styling only."""
        try:
            print("QOLS: Setting up dropdown tooltips with native QGIS styling")
            
            # Apply MINIMAL CSS fix only for hover text visibility
            hover_fix_style = """
            QgsMapLayerComboBox QAbstractItemView::item:hover {
                color: black !important;
                background-color: #0078d4 !important;
            }
            
            QgsMapLayerComboBox QAbstractItemView::item:selected {
                color: black !important;
            }
            """
            
            # Apply only the hover text fix - keep everything else native
            self.runwayLayerCombo.setStyleSheet(hover_fix_style)
            self.thresholdLayerCombo.setStyleSheet(hover_fix_style)
            
            # Connect to layer addition/removal to update item tooltips
            QgsProject.instance().layersAdded.connect(self.update_dropdown_item_tooltips)
            QgsProject.instance().layersRemoved.connect(self.update_dropdown_item_tooltips)
            
            # Also connect to model changes in the combos themselves
            self.runwayLayerCombo.layerChanged.connect(self.update_dropdown_item_tooltips)
            self.thresholdLayerCombo.layerChanged.connect(self.update_dropdown_item_tooltips)
            
            # Connect to mouse events on the dropdown views for real-time tooltip updates
            try:
                runway_view = self.runwayLayerCombo.view()
                threshold_view = self.thresholdLayerCombo.view()
                
                # Set mouse tracking to capture hover events
                runway_view.setMouseTracking(True)
                threshold_view.setMouseTracking(True)
                
                # Install event filters for hover detection
                runway_view.installEventFilter(self)
                threshold_view.installEventFilter(self)
                
            except Exception as e:
                print(f"QOLS: Could not setup hover event detection: {e}")
            
            # Use a timer to periodically update tooltips as QGIS may regenerate the model
            # Reduce frequency to avoid spam - only check every 10 seconds
            self.tooltip_timer = QTimer()
            self.tooltip_timer.timeout.connect(self.update_dropdown_item_tooltips)
            self.tooltip_timer.start(10000)  # Update every 10 seconds instead of 2
            
            # Set initial item tooltips
            self.update_dropdown_item_tooltips()
            
        except Exception as e:
            print(f"QOLS: Error setting up dropdown tooltips: {e}")
    
    def update_dropdown_item_tooltips(self):
        """Update tooltips for individual dropdown items - native QGIS styling only.""" 
        try:
            # Reduce logging frequency - only log when layers change
            current_runway_count = self.runwayLayerCombo.count()
            current_threshold_count = self.thresholdLayerCombo.count()
            
            # Only proceed if layer counts have changed
            if not hasattr(self, '_last_runway_count'):
                self._last_runway_count = 0
                self._last_threshold_count = 0
            
            if (current_runway_count == self._last_runway_count and 
                current_threshold_count == self._last_threshold_count):
                return  # No changes, skip update
            
            print(f"QOLS: Updating tooltips - Runway: {current_runway_count}, Threshold: {current_threshold_count}")
            self._last_runway_count = current_runway_count
            self._last_threshold_count = current_threshold_count
            
            # Force update tooltips using multiple methods for maximum compatibility
            try:
                # Update runway combo tooltips - focus on tooltip data only
                runway_model = self.runwayLayerCombo.model()
                for i in range(self.runwayLayerCombo.count()):
                    layer = self.runwayLayerCombo.layer(i)
                    if layer:
                        geom_type = self.get_geometry_type_name(layer)
                        feature_count = layer.featureCount()
                        tooltip = f"Layer: {layer.name()}\nType: {geom_type}\nFeatures: {feature_count}"
                        
                        # Method 1: Set via model data (most reliable for QgsMapLayerComboBox)
                        index = runway_model.index(i, 0)
                        runway_model.setData(index, tooltip, Qt.ToolTipRole)
                        
                        # Method 2: Set via item data (backup method)
                        try:
                            self.runwayLayerCombo.setItemData(i, tooltip, Qt.ToolTipRole)
                        except:
                            pass
                
                # Update threshold combo tooltips - focus on tooltip data only
                threshold_model = self.thresholdLayerCombo.model()
                for i in range(self.thresholdLayerCombo.count()):
                    layer = self.thresholdLayerCombo.layer(i)
                    if layer:
                        geom_type = self.get_geometry_type_name(layer)
                        feature_count = layer.featureCount()
                        tooltip = f"Layer: {layer.name()}\nType: {geom_type}\nFeatures: {feature_count}"
                        
                        # Method 1: Set via model data (most reliable for QgsMapLayerComboBox)
                        index = threshold_model.index(i, 0)
                        threshold_model.setData(index, tooltip, Qt.ToolTipRole)
                        
                        # Method 2: Set via item data (backup method)
                        try:
                            self.thresholdLayerCombo.setItemData(i, tooltip, Qt.ToolTipRole)
                        except:
                            pass
                
                # Force view refresh to ensure tooltips are applied
                try:
                    self.runwayLayerCombo.view().update()
                    self.thresholdLayerCombo.view().update()
                except:
                    pass
                
                print("QOLS: Tooltips updated successfully")
                
            except Exception as e:
                print(f"QOLS: Error in tooltip update details: {e}")
                
        except Exception as e:
            print(f"QOLS: Error updating dropdown item tooltips: {e}")
            import traceback
            traceback.print_exc()
    
    def get_geometry_type_name(self, layer):
        """Get readable geometry type name."""
        try:
            geom_type = layer.geometryType()
            if geom_type == 0:  # QgsWkbTypes.PointGeometry
                return "Point"
            elif geom_type == 1:  # QgsWkbTypes.LineGeometry
                return "LineString"
            elif geom_type == 2:  # QgsWkbTypes.PolygonGeometry
                return "Polygon"
            else:
                return "Unknown"
        except:
            return "Unknown"
    
    def eventFilter(self, obj, event):
        """Handle events for dropdown hover tooltips - Native QGIS styling only."""
        try:
            # Check if this is a mouse move event in one of our dropdown views
            if event.type() == event.MouseMove:
                # Get the view that received the event
                if hasattr(self, 'runwayLayerCombo') and hasattr(self, 'thresholdLayerCombo'):
                    if obj == self.runwayLayerCombo.view() or obj == self.thresholdLayerCombo.view():
                        # Get the item under the mouse
                        index = obj.indexAt(event.pos())
                        if index.isValid():
                            # Get the layer for this index
                            combo = self.runwayLayerCombo if obj == self.runwayLayerCombo.view() else self.thresholdLayerCombo
                            layer = combo.layer(index.row())
                            if layer:
                                geom_type = self.get_geometry_type_name(layer)
                                feature_count = layer.featureCount()
                                tooltip = f"Layer: {layer.name()}\nType: {geom_type}\nFeatures: {feature_count}"
                                
                                # Method 1: Set tooltip on the view (native QGIS style)
                                obj.setToolTip(tooltip)
                                
                                # Method 2: Force show tooltip at mouse position (native QGIS style)
                                QToolTip.showText(event.globalPos(), tooltip, obj)
                                
                            return False  # Let the event propagate normally
                        else:
                            # Mouse not over an item, hide tooltip
                            obj.setToolTip("")
                            QToolTip.hideText()
                            
        except Exception as e:
            print(f"QOLS: Error in eventFilter: {e}")
            
        # Call the base implementation for all other events
        return super().eventFilter(obj, event)

    def setup_enhanced_combos(self):
        """Setup enhanced combo boxes with minimal styling."""
        try:
            print("QOLS: Setting up enhanced combo styling")
            
            # Note: Tooltips are handled by setup_dropdown_tooltips() for individual items
            # No need to set combo-level tooltips as they override item tooltips
            
            # Apply minimal styling - solo indicadores de color, resto nativo
            minimal_combo_style = """
                /* Styling mínimo - mantener apariencia nativa de QGIS */
                QgsMapLayerComboBox {
                    border: 1px solid #bdc3c7;
                    border-radius: 4px;
                    padding: 2px 4px;
                    font-size: 9pt;
                    background-color: white;
                }
                
                QgsMapLayerComboBox:hover {
                    border-color: #3498db;
                    background-color: #f8f9fa;
                }
                
                /* Tooltip styling for visibility */
                QToolTip {
                    background-color: #ffffcc;
                    color: #000000;
                    border: 1px solid #cccccc;
                    padding: 5px;
                    border-radius: 3px;
                    font-size: 10pt;
                }
                
                /* Solo indicadores de color para diferenciación */
                QgsMapLayerComboBox#runwayLayerCombo {
                    border-left: 3px solid #3498db;
                }
                
                QgsMapLayerComboBox#thresholdLayerCombo {
                    border-left: 3px solid #e67e22;
                }
            """
            
            # Apply the minimal styling
            self.runwayLayerCombo.setStyleSheet(minimal_combo_style)
            self.thresholdLayerCombo.setStyleSheet(minimal_combo_style)
            
            print("QOLS: Minimal combo styling applied successfully")
            
        except Exception as e:
            print(f"QOLS: Error setting up enhanced combos: {e}")

    def update_selection_info(self):
        """Update selection information in real-time with improved individual feedback."""
        try:
            print("QOLS: update_selection_info called")
            runway_layer = self.runwayLayerCombo.currentLayer()
            threshold_layer = self.thresholdLayerCombo.currentLayer()
            
            use_runway_selected = self.useSelectedRunwayCheckBox.isChecked()
            use_threshold_selected = self.useSelectedThresholdCheckBox.isChecked()
            
            print(f"QOLS: runway_layer = {runway_layer.name() if runway_layer else 'None'}")
            print(f"QOLS: threshold_layer = {threshold_layer.name() if threshold_layer else 'None'}")
            
            # Update runway info
            if runway_layer:
                runway_selected = len(runway_layer.selectedFeatures())
                runway_total = runway_layer.featureCount()
                
                if use_runway_selected:
                    if runway_selected > 0:
                        runway_info = f"• Using {runway_selected} of {runway_total} selected"
                        runway_status = f"Selected ({runway_selected})"
                    else:
                        runway_info = f"! No features selected"
                        runway_status = f"No selection"
                else:
                    runway_info = f"• All {runway_total} features"
                    runway_status = f"All ({runway_total})"
            else:
                runway_info = "x No layer selected"
                runway_status = "No layer"
            
            # Update threshold info
            if threshold_layer:
                threshold_selected = len(threshold_layer.selectedFeatures())
                threshold_total = threshold_layer.featureCount()
                
                if use_threshold_selected:
                    if threshold_selected > 0:
                        threshold_info = f"• Using {threshold_selected} of {threshold_total} selected"
                        threshold_status = f"Selected ({threshold_selected})"
                    else:
                        threshold_info = f"! No features selected"
                        threshold_status = f"No selection"
                else:
                    threshold_info = f"• All {threshold_total} features"
                    threshold_status = f"All ({threshold_total})"
            else:
                threshold_info = "x No layer selected"
                threshold_status = "No layer"
            print(f"QOLS: runway_status = {runway_status}")
            print(f"QOLS: threshold_status = {threshold_status}")
            
            # Individual status icons for each layer (using beautiful emojis for live status)
            if "All" in runway_status:
                runway_icon = "⚠️"  # Warning for "All" - caution about using all features
            elif "Selected" in runway_status:
                runway_icon = "✅"  # Success for "Selected" - recommended approach
            else:
                runway_icon = "❌"
            
            if "All" in threshold_status:
                threshold_icon = "⚠️"  # Warning for "All" - caution about using all features
            elif "Selected" in threshold_status:
                threshold_icon = "✅"  # Success for "Selected" - recommended approach
            else:
                threshold_icon = "❌"
            
            combined_status = f"Status: Runway: {runway_icon} {runway_status} | Threshold: {threshold_icon} {threshold_status}"
            
            try:
                self.selectionInfoLabel.setText(combined_status)
                print(f"QOLS: selectionInfoLabel updated: {combined_status}")
            except Exception as e:
                print(f"QOLS: Error updating selectionInfoLabel: {e}")
            
            # Update dropdown tooltips with current layer info
            self.update_dropdown_item_tooltips()
            
            print("QOLS: update_selection_info completed successfully")
            
        except Exception as e:
            print(f"QOLS: Error in update_selection_info: {e}")
            import traceback
            traceback.print_exc()
            
            # Fallback text in case of error
            try:
                self.selectionInfoLabel.setText("! Status update error - check console")
            except:
                pass

    def update_takeoff_defaults_from_code(self):
        """Apply default values from the ICAO table for Take-Off based on code.
        If user has already typed values, do not override their inputs; only fill when empty.
    El ancho final por defecto se toma de la tabla del código y es editable por el usuario.
        """
        try:
            if not hasattr(self, 'spin_code_takeoff'):
                return
            code_value = self.get_code_value('spin_code_takeoff')

            # Table values per code
            table = {
                1: {
                    'inner_edge': 60.0,
                    'distance_from_runway_end': 30.0,
                    'divergence_pct': 10.0,
                    'final_width': 380.0,
                    'length': 1600.0,
                    'slope_pct': 5.0,
                },
                2: {
                    'inner_edge': 80.0,
                    'distance_from_runway_end': 60.0,
                    'divergence_pct': 10.0,
                    'final_width': 580.0,
                    'length': 2500.0,
                    'slope_pct': 4.0,
                },
                3: {
                    'inner_edge': 180.0,
                    'distance_from_runway_end': 60.0,
                    'divergence_pct': 12.5,
                    'final_width': 1800.0,
                    'length': 15000.0,
                    'slope_pct': 2.0,
                },
                4: {
                    'inner_edge': 180.0,
                    'distance_from_runway_end': 60.0,
                    'divergence_pct': 12.5,
                    'final_width': 1800.0,
                    'length': 15000.0,
                    'slope_pct': 2.0,
                },
            }

            t = table.get(code_value)
            if not t:
                return

            # Helper to set QLineEdit text, optionally only when empty
            def set_value(widget_name: str, value: float, only_when_empty: bool = False):
                w = getattr(self, widget_name, None)
                if not w:
                    return
                current = w.text() if hasattr(w, 'text') else ''
                if (only_when_empty and (current is None or current.strip() == '')) or (not only_when_empty):
                    w.setText(f"{value:.1f}")

            # On code change, apply ALL defaults from table (user can edit afterwards)
            set_value('spin_widthDep_takeoff', t['inner_edge'])
            set_value('spin_divergence_takeoff', t['divergence_pct'])
            set_value('spin_startDistance_takeoff', t['distance_from_runway_end'])
            set_value('spin_surfaceLength_takeoff', t['length'])
            set_value('spin_slope_takeoff', t['slope_pct'])

            # Update max width por defecto del código (editable)
            if hasattr(self, 'spin_maxWidthDep_takeoff') and self.spin_maxWidthDep_takeoff:
                self.spin_maxWidthDep_takeoff.setText(f"{t['final_width']:.1f}")

            print(f"QOLS: Applied Take-Off defaults from table for code {code_value}")
        except Exception as e:
            print(f"QOLS: Error applying Take-Off defaults: {e}")


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

    def toggle_transitional_direction(self):
        """Toggle transitional runway direction between normal and rotated."""
        self.transitional_direction_normal = not self.transitional_direction_normal
        self.update_transitional_direction_button()

    def update_transitional_direction_button(self):
        """Update the transitional direction button text and style."""
        if self.transitional_direction_normal:
            self.button_rotate_transitional.setText("🔄 Normal Runway Direction")
            self.button_rotate_transitional.setChecked(False)
        else:
            self.button_rotate_transitional.setText("🔄 Inverted Runway Direction")
            self.button_rotate_transitional.setChecked(True)

    def on_tab_changed(self, index):
        """Handle tab changes to ensure defaults are set properly."""
        try:
            # Get the current tab name
            current_tab = self.scriptTabWidget.widget(index)
            if current_tab:
                tab_name = current_tab.objectName()
                print(f"QOLS: Tab changed to: {tab_name}")
                
                # Reinitialize defaults for Transitional tab specifically
                if 'transitional' in tab_name.lower():
                    print("QOLS: Transitional tab selected - ensuring defaults are set")
                    # Force set defaults again (helpful for widget visibility issues)
                    QTimer.singleShot(100, self.force_transitional_defaults)
                    
        except Exception as e:
            print(f"QOLS: Error in tab change handler: {e}")

    def force_transitional_defaults(self):
        """Force set Transitional Surface default values."""
        try:
            print("QOLS: Force setting Transitional Surface defaults")
            
            # Transitional Surface default values (from original script)
            transitional_defaults = {
                'spin_widthApp_transitional': '280.00',
                'spin_Z0_transitional': '2548.00',
                'spin_ZE_transitional': '2546.50',
                'spin_ARPH_transitional': '2548.00',
                'spin_IHSlope_transitional': '33.30',
                'spin_Tslope_transitional': '14.30'
            }
            
            # Force set each value using setText for QLineEdit widgets
            for widget_name, default_value in transitional_defaults.items():
                try:
                    widget = getattr(self, widget_name, None)
                    if widget and hasattr(widget, 'setText'):
                        widget.setText(default_value)
                        print(f"QOLS: Set {widget_name} = {default_value}")
                    elif widget and hasattr(widget, 'setValue'):
                        widget.setValue(float(default_value))
                        print(f"QOLS: Set {widget_name} = {default_value} (setValue)")
                    else:
                        print(f"QOLS: Widget {widget_name} not found or no setText/setValue")
                except Exception as e:
                    print(f"QOLS: Error setting {widget_name}: {e}")
                
            # Set code and type (these are QComboBox)
            try:
                self.set_code_value('spin_code_transitional', 4)
                print("QOLS: Set code = 4")
            except Exception as e:
                print(f"QOLS: Error setting code: {e}")
                
            try:
                self.combo_rwyClassification_transitional.setCurrentText('Precision Approach CAT I')
                print("QOLS: Set typeAPP = CAT I")
            except AttributeError as e:
                print(f"QOLS: combo_rwyClassification_transitional not found: {e}")
                
            print("QOLS: Transitional defaults forced successfully")
            
        except Exception as e:
            print(f"QOLS: Error forcing transitional defaults: {e}")

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
            
            print(f"QOLS DEBUG: current_tab_index = {current_tab_index}")
            print(f"QOLS DEBUG: surface_type = '{surface_type}'")
            print(f"QOLS DEBUG: surface_type type = {type(surface_type)}")
            print(f"QOLS DEBUG: surface_type repr = {repr(surface_type)}")
            
            # Get parameters based on current tab
            if surface_type == "Approach Surface":
                # Determine direction and map elevations accordingly
                s_value = 0 if self.direction_start_to_end else -1
                z0_ui = self.get_numeric_value('spin_Z0')  # UI-labeled Start Elevation (m)
                ze_ui = self.get_numeric_value('spin_ZE')  # UI-labeled End Elevation (m)

                # For calculations, Z0 should always represent the starting end for the selected direction
                if s_value == 0:  # Start → End
                    Z0_calc = z0_ui
                    ZE_calc = ze_ui
                else:  # End → Start
                    Z0_calc = ze_ui
                    ZE_calc = z0_ui

                specific_params = {
                    'code': self.get_code_value('spin_code'),  # QComboBox
                    'rwyClassification': self.combo_rwyClassification.currentText(),
                    'widthApp': self.get_numeric_value('spin_widthApp'),
                    'Z0': Z0_calc,
                    'ZE': ZE_calc,
                    'ARPH': self.get_numeric_value('spin_ARPH'),
                    'L1': self.get_numeric_value('spin_L1'),
                    'L2': self.get_numeric_value('spin_L2'),
                    'LH': self.get_numeric_value('spin_LH'),
                    's': s_value
                }
            elif surface_type == "Conical":
                specific_params = {
                    'radius': self.get_numeric_value('spin_L_conical'),        # Distance L is the radius
                    'height': self.get_numeric_value('spin_height_conical')    # Height for 3D polygon
                }
            elif surface_type == "Inner Horizontal":
                specific_params = {
                    'radius': self.get_numeric_value('spin_L_inner'),          # Distance L is the radius
                    'height': self.get_numeric_value('spin_height_inner')      # Height for 3D polygon
                }
            elif surface_type == "Outer Horizontal":
                specific_params = {
                    'code': self.get_code_value('spin_code_outer'),  # QComboBox
                    'radius': float(self.spin_radius_outer.text() or "0"),  # QLineEdit
                    'height': float(self.spin_height_outer.text() or "0")   # QLineEdit
                }
            elif surface_type == "Take-Off Surface":
                print(f"QOLS DEBUG: Collecting Take-off Surface parameters...")
                print(f"QOLS DEBUG: spin_code_takeoff.currentText() = {self.spin_code_takeoff.currentText()}")
                # Take-Off RWY Classification removed from UI; no debug for it
                print(f"QOLS DEBUG: spin_widthDep_takeoff.text() = {self.spin_widthDep_takeoff.text()}")
                print(f"QOLS DEBUG: spin_maxWidthDep_takeoff.text() = {self.spin_maxWidthDep_takeoff.text()}")
                print(f"QOLS DEBUG: spin_divergence_takeoff.text() = {getattr(self, 'spin_divergence_takeoff', None).text() if hasattr(self, 'spin_divergence_takeoff') else 'N/A'}")
                print(f"QOLS DEBUG: spin_startDistance_takeoff.text() = {getattr(self, 'spin_startDistance_takeoff', None).text() if hasattr(self, 'spin_startDistance_takeoff') else 'N/A'}")
                print(f"QOLS DEBUG: spin_surfaceLength_takeoff.text() = {getattr(self, 'spin_surfaceLength_takeoff', None).text() if hasattr(self, 'spin_surfaceLength_takeoff') else 'N/A'}")
                print(f"QOLS DEBUG: spin_slope_takeoff.text() = {getattr(self, 'spin_slope_takeoff', None).text() if hasattr(self, 'spin_slope_takeoff') else 'N/A'}")
                # IMC checkbox eliminado; no aplica log
                
                code_value = self.get_code_value('spin_code_takeoff')
                # Determine default maxWidthDep per code (editable)
                default_max_width = 1800 if code_value in [3,4] else float(self.spin_maxWidthDep_takeoff.text() or "1800")
                # Allow user override via spin_maxWidthDep_takeoff if provided
                user_max_width_text = self.spin_maxWidthDep_takeoff.text() if hasattr(self, 'spin_maxWidthDep_takeoff') else ""
                max_width_dep = float(user_max_width_text) if user_max_width_text not in ["", None] else default_max_width

                specific_params = {
                    'code': code_value,  # QComboBox
                    'widthApp': 150,  # Remains constant for take-off width near origin
                    'widthDep': float(self.spin_widthDep_takeoff.text() or "0"),     # QLineEdit
                    'maxWidthDep': max_width_dep, # Default from code; user-editable
                    'CWYLength': float(self.spin_CWYLength_takeoff.text() or "0"),   # QLineEdit (clearway length)
                    'Z0': float(self.spin_Z0_takeoff.text() or "0"),                 # QLineEdit
                    'ZE': 2546.5,  # Fixed or could be derived; kept as-is per current logic
                    # Newly exposed parameters
                    'divergencePct': float(self.spin_divergence_takeoff.text() or "12.5") if hasattr(self, 'spin_divergence_takeoff') else 12.5,
                    'startDistance': float(self.spin_startDistance_takeoff.text() or "60") if hasattr(self, 'spin_startDistance_takeoff') else 60.0,
                    'surfaceLength': float(self.spin_surfaceLength_takeoff.text() or "15000") if hasattr(self, 'spin_surfaceLength_takeoff') else 15000.0,
                    'slopePct': float(self.spin_slope_takeoff.text() or "2.0") if hasattr(self, 'spin_slope_takeoff') else 2.0
                }
                print(f"QOLS DEBUG: Take-off Surface specific_params = {specific_params}")
            elif surface_type == "Transitional Surface" or surface_type == "Transitional":
                # Note: Using correct transitional surface widget names
                # IMPORTANT: For transitional, use the specific rotation button instead of general direction
                s_value = 0 if self.transitional_direction_normal else -1  # s = 0 for normal, s = -1 for rotated
                
                print(f"QOLS DEBUG: Transitional rotation button normal={self.transitional_direction_normal}, s={s_value}")
                
                specific_params = {
                    'code': self.get_code_value('spin_code_transitional'),  # QComboBox
                    'rwyClassification': self.combo_rwyClassification_transitional.currentText(),
                    'widthApp': float(self.spin_widthApp_transitional.text() or "0"),  # QLineEdit
                    'Z0': float(self.spin_Z0_transitional.text() or "0"),              # QLineEdit
                    'ZE': float(self.spin_ZE_transitional.text() or "0"),              # QLineEdit
                    'ARPH': float(self.spin_ARPH_transitional.text() or "0"),          # QLineEdit
                    'IHSlope': float(self.spin_IHSlope_transitional.text() or "0") / 100.0,  # QLineEdit, convert % to decimal
                    'Tslope': float(self.spin_Tslope_transitional.text() or "0") / 100.0,   # QLineEdit, convert % to decimal
                    's': s_value  # Special parameter for transitional runway direction
                }
                print(f"QOLS DEBUG: Transitional Surface specific_params = {specific_params}")
            elif surface_type == "OFZ":
                specific_params = {
                    'code': self.get_code_value('spin_code_ofz'),  # QComboBox
                    'rwyClassification': self.combo_rwyClassification_ofz.currentText(),
                    'width': float(self.spin_width_ofz.text() or "0"),
                    'Z0': float(self.spin_Z0_ofz.text() or "0"),
                    'ZE': float(self.spin_ZE_ofz.text() or "0"),
                    'ARPH': float(self.spin_ARPH_ofz.text() or "0"),
                    'IHSlope': float(self.spin_IHSlope_ofz.text() or "0") / 100.0  # Convert percentage to decimal
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
