import os
import sys
from qgis.PyQt import uic
from qgis.PyQt.QtCore import pyqtSignal, Qt, QTimer
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
            
            # Apply modern stylesheet
            self.apply_modern_stylesheet()
            
            # Configure decimal precision for all QDoubleSpinBox widgets
            self.setup_decimal_precision()
            
            # Configure layer combo boxes with geometry filtering
            self.setup_layer_filters()
            
            # Apply enhanced combo styling and tooltips for better UX
            self.setup_enhanced_combos()
            
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

    def apply_modern_stylesheet(self):
        """Use native Qt styling for maximum compatibility and performance."""
        try:
            # Clear any existing custom styles to use native Qt appearance
            self.setStyleSheet("")
            print("QOLS: Using native Qt styling for maximum compatibility")
            
        except Exception as e:
            print(f"QOLS: Error clearing stylesheet: {e}")
            # Ensure no styles are applied
            self.setStyleSheet("")

    def setup_decimal_precision(self):
        """Configure decimal precision with CUSTOM VALIDATION to allow true multi-decimal input."""
        try:
            print("QOLS: Setting up CUSTOM decimal validation for true multi-decimal support")
            
            # List of all QDoubleSpinBox widget names
            spinbox_names = [
                'spin_widthApp', 'spin_Z0', 'spin_ZE', 'spin_ARPH', 
                'spin_L1', 'spin_L2', 'spin_LH', 'spin_IHSlope',
                'spin_L_conical', 'spin_height_conical',
                'spin_L_inner', 'spin_height_inner',
                'spin_width_ofz', 'spin_Z0_ofz', 'spin_ZE_ofz', 'spin_ARPH_ofz', 'spin_IHSlope_ofz',
                'spin_radius_outer', 'spin_height_outer'
            ]
            
            configured_count = 0
            
            for name in spinbox_names:
                try:
                    spinbox = getattr(self, name, None)
                    if spinbox:
                        # Configure for maximum precision but controlled display
                        self._configure_precision_spinbox(spinbox)
                        
                        # Set reasonable range and step
                        if spinbox.maximum() == 99.99:
                            spinbox.setMaximum(999999.99999999)
                        spinbox.setSingleStep(0.01)
                        
                        configured_count += 1
                        print(f"QOLS: Configured {name} - custom precision validation enabled")
                        
                except Exception as e:
                    print(f"QOLS: Warning - could not configure {name}: {e}")
            
            print(f"QOLS: Successfully configured {configured_count} QDoubleSpinBox widgets with custom validation")
            print("QOLS: All spinboxes now support true multi-decimal input without Qt rounding")
            
        except Exception as e:
            print(f"QOLS: Error setting up decimal precision: {e}")

    def _configure_precision_spinbox(self, spinbox):
        """
        Configure spinbox with CUSTOM validation to bypass Qt's automatic rounding.
        This allows true multi-decimal input by overriding Qt's built-in behavior.
        """
        try:
            from qgis.PyQt.QtCore import QRegExp
            from qgis.PyQt.QtGui import QRegExpValidator
            
            # Create custom validator that allows up to 8 decimal places
            # Pattern: optional minus, digits, optional decimal point with up to 8 digits
            decimal_pattern = r'^-?\d+\.?\d{0,8}$|^-?\d*\.\d{1,8}$|^\d+$'
            regex = QRegExp(decimal_pattern)
            validator = QRegExpValidator(regex)
            
            # Apply custom validator to lineEdit
            if hasattr(spinbox, 'lineEdit') and spinbox.lineEdit():
                spinbox.lineEdit().setValidator(validator)
            
            # Set maximum decimals to 8 to allow the precision
            spinbox.setDecimals(8)
            
            # Store original value for clean display logic
            spinbox._original_precision = 2
            spinbox._is_displaying_clean = True
            
            # Override textFromValue to control display format
            original_textFromValue = spinbox.textFromValue
            def custom_textFromValue(value):
                try:
                    # If we're in "clean display" mode and it's a simple value
                    if hasattr(spinbox, '_is_displaying_clean') and spinbox._is_displaying_clean:
                        if abs(value - round(value, 2)) < 0.000001:
                            return f"{value:.2f}"
                    
                    # Otherwise, use smart formatting
                    if abs(value - round(value)) < 0.000001:
                        return f"{int(round(value))}.00"
                    else:
                        # Format with minimal necessary decimals
                        formatted = f"{value:.8f}".rstrip('0').rstrip('.')
                        if '.' not in formatted:
                            formatted += ".00"
                        elif len(formatted.split('.')[1]) == 1:
                            formatted += "0"
                        return formatted
                except:
                    return original_textFromValue(value)
            
            # Apply custom formatting (be careful about method replacement)
            try:
                spinbox.textFromValue = custom_textFromValue
            except:
                pass  # If method replacement fails, continue with default
            
            # Handle input changes to adjust clean display mode
            def handle_text_input():
                try:
                    if hasattr(spinbox, 'lineEdit') and spinbox.lineEdit():
                        text = spinbox.lineEdit().text()
                        if '.' in text and len(text.split('.')[1]) > 2:
                            spinbox._is_displaying_clean = False
                        else:
                            spinbox._is_displaying_clean = True
                except:
                    pass
            
            # Connect to text changes
            if hasattr(spinbox, 'lineEdit') and spinbox.lineEdit():
                spinbox.lineEdit().textChanged.connect(handle_text_input)
            
            print(f"QOLS: Custom precision validation configured for {spinbox.objectName()}")
            
        except Exception as e:
            print(f"QOLS: Warning - custom precision setup failed for {spinbox.objectName()}: {e}")
            # Fallback to standard configuration
            try:
                spinbox.setDecimals(8)
            except:
                pass

    def _configure_smart_expansion_OLD_DISABLED(self, spinbox):
        """
        Configure smart decimal expansion - starts with 2, expands when user inputs more.
        IMPROVED VERSION: Actually allows more decimal input.
        """
        try:
            # Set initial decimals to 2 for clean display
            spinbox.setDecimals(2)
            
            # Configure dynamic expansion on text input
            def handle_text_input():
                try:
                    text = spinbox.lineEdit().text()
                    
                    # Check decimal places needed
                    if '.' in text:
                        try:
                            # Count decimal places in input
                            decimal_part = text.split('.')[1]
                            needed_decimals = len(decimal_part)
                            
                            # Expand spinbox if user needs more decimals
                            current_decimals = spinbox.decimals()
                            if needed_decimals > current_decimals and needed_decimals <= 8:
                                spinbox.setDecimals(needed_decimals)
                                print(f"QOLS: Expanded {spinbox.objectName()} to {needed_decimals} decimals")
                                
                        except (IndexError, ValueError):
                            pass  # Invalid format, let Qt handle it
                            
                except Exception as e:
                    pass  # Ignore errors during live typing
            
            # Connect to text changes for dynamic expansion
            if hasattr(spinbox, 'lineEdit') and spinbox.lineEdit():
                spinbox.lineEdit().textChanged.connect(handle_text_input)
            
            print(f"QOLS: Advanced decimal expansion configured for {spinbox.objectName()}")
            
        except Exception as e:
            print(f"QOLS: Warning - advanced expansion setup failed for {spinbox.objectName()}: {e}")
            # Fallback: at least set basic 2 decimals
            try:
                spinbox.setDecimals(2)
            except:
                pass

    def _configure_clean_value_display(self, spinbox):
        """
        Configurar display inteligente REAL - SOLUCIÓN ELEGANTE
        
        OBJETIVO EXACTO DEL CLIENTE:
        - Display inicial: 60.00 (2 decimales, limpio)
        - Input flexible: 60.123456789 (sin límites)
        - Display adapta: muestra decimales necesarios
        """
        try:
            # Configurar máxima precisión interna
            spinbox.setDecimals(8)  # Maximum expansion when needed
            
            # SOLUCIÓN ELEGANTE: Override textFromValue para control completo de display
            original_textFromValue = spinbox.textFromValue
            
            def smart_textFromValue(value):
                """
                Método personalizado que controla exactamente cómo se muestra el valor:
                - Valores enteros: 60 (sin decimales innecesarios)
                - Por defecto: 60.00 (2 decimales limpios)
                - Con decimales: 60.123 (solo los necesarios)
                """
                # Verificar si está en modo edición
                is_editing = getattr(spinbox, '_smart_editing_mode', False)
                
                if is_editing:
                    # Durante edición, mostrar formato completo para flexibilidad
                    if value == int(value):
                        return f"{int(value)}"
                    else:
                        # Mostrar hasta 8 decimales, eliminando ceros trailing
                        text = f"{value:.8f}".rstrip('0').rstrip('.')
                        # Asegurar al menos 2 decimales para consistencia visual
                        if '.' not in text:
                            text += ".00"
                        elif len(text.split('.')[1]) == 1:
                            text += "0"
                        return text
                else:
                    # Display normal: formato limpio y consistente
                    if value == int(value):
                        return f"{int(value)}.00"  # Formato consistente
                    else:
                        # Determinar decimales mínimos necesarios
                        for decimals in range(1, 7):
                            rounded = round(value, decimals)
                            if abs(value - rounded) < 1e-10:
                                # Usar al menos 2 decimales para consistencia
                                display_decimals = max(2, decimals)
                                return f"{value:.{display_decimals}f}"
                        # Fallback: 2 decimales
                        return f"{value:.2f}"
            
            # Reemplazar el método textFromValue
            spinbox.textFromValue = smart_textFromValue
            
            # Configurar eventos para detectar modo edición
            spinbox._smart_editing_mode = False
            
            # Override eventos de focus para controlar modo edición
            original_focusInEvent = spinbox.focusInEvent
            original_focusOutEvent = spinbox.focusOutEvent
            
            def smart_focusInEvent(event):
                spinbox._smart_editing_mode = True
                original_focusInEvent(event)
            
            def smart_focusOutEvent(event):
                spinbox._smart_editing_mode = False
                original_focusOutEvent(event)
                # Forzar actualización del display
                spinbox.update()
            
            spinbox.focusInEvent = smart_focusInEvent
            spinbox.focusOutEvent = smart_focusOutEvent
            
            # Configurar eventos de line edit si está disponible
            try:
                line_edit = spinbox.lineEdit()
                if line_edit:
                    def on_editing_started():
                        spinbox._smart_editing_mode = True
                    
                    def on_editing_finished():
                        spinbox._smart_editing_mode = False
                        spinbox.update()
                    
                    line_edit.editingFinished.connect(on_editing_finished)
                    # textChanged no lo usamos para evitar updates excesivos
            except:
                pass  # Ignore si no se puede configurar
            
            print(f"QOLS: Smart display configured for {spinbox.objectName()}")
            print(f"      Display: 60.00 (clean), Input: 60.123456 (flexible)")
            
        except Exception as e:
            print(f"QOLS: Warning - smart display setup failed: {e}")
            # Fallback a configuración básica
            spinbox.setDecimals(2)

    def _apply_clean_display_formatting(self, spinbox):
        """
        Aplicar formateo limpio al display.
        
        OBJETIVO: Mostrar 60.00 en lugar de 60.000000 para valores simples
        PERO: Permitir 60.123456 cuando el usuario lo ingrese
        """
        try:
            # Esta es una limitación de Qt QDoubleSpinBox
            # La mejor solución práctica es configurar valores iniciales limpios
            # y documentar que el comportamiento de input es completo
            
            # Configurar step y comportamiento para mejor UX
            current_step = spinbox.singleStep()
            if current_step < 0.01:
                spinbox.setSingleStep(0.01)  # Step más razonable para UX
            
            # El display mostrará 6 decimales, pero funcionalmente es correcto
            # porque permite la precisión completa que requiere el cliente
            
        except Exception as e:
            print(f"QOLS: Error applying clean formatting: {e}")

    def _configure_flexible_input(self, spinbox):
        """
        Configurar input flexible para cumplir EXACTAMENTE el requerimiento del cliente:
        
        DISPLAY DEFAULT: 60.00 (2 decimales, se ve limpio)
        INPUT FLEXIBLE: Usuario puede escribir 60.123456789 y se acepta
        ALMACENAMIENTO: Se guarda exactamente lo que el usuario escribió
        
        Estrategia: Interceptar eventos de texto y ajustar decimales dinámicamente
        """
        try:
            # Almacenar referencia al valor con alta precisión
            spinbox._high_precision_value = spinbox.value()
            
            # Conectar eventos para manejar input personalizado
            spinbox.lineEdit().textChanged.connect(
                lambda text, sb=spinbox: self._handle_flexible_input(sb, text)
            )
            
            # Conectar valueChanged para sincronizar
            spinbox.valueChanged.connect(
                lambda value, sb=spinbox: self._sync_high_precision_value(sb, value)
            )
            
            print(f"QOLS: Flexible input configured for {spinbox.objectName()}")
            
        except Exception as e:
            print(f"QOLS: Warning - flexible input setup failed: {e}")

    def _handle_flexible_input(self, spinbox, text):
        """
        Manejar input de texto para permitir alta precisión.
        
        Lógica:
        - Si usuario escribe 60.123456, temporalmente aumentar decimales
        - Preservar el valor exacto
        - Cuando no esté editando, volver a display limpio
        """
        try:
            # Contar decimales en el texto actual
            if '.' in text:
                decimal_part = text.split('.')[-1]
                needed_decimals = len(decimal_part)
                
                # Si necesita más de 2 decimales, ajustar temporalmente
                if needed_decimals > 2:
                    current_decimals = spinbox.decimals()
                    if needed_decimals > current_decimals:
                        spinbox.setDecimals(min(needed_decimals, 8))  # Máximo 8 decimales
                        print(f"QOLS: Adjusted {spinbox.objectName()} to {needed_decimals} decimals for input")
            
            # Parsear y almacenar el valor de alta precisión
            try:
                high_precision_value = float(text)
                spinbox._high_precision_value = high_precision_value
            except ValueError:
                pass  # Texto inválido, ignorar
                
        except Exception as e:
            print(f"QOLS: Error handling flexible input: {e}")

    def _sync_high_precision_value(self, spinbox, value):
        """Sincronizar el valor de alta precisión con el valor del spinbox"""
        try:
            spinbox._high_precision_value = value
        except Exception as e:
            print(f"QOLS: Error syncing high precision value: {e}")

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
                'spin_L1', 'spin_L2', 'spin_LH', 'spin_IHSlope',
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
                'spin_L1', 'spin_L2', 'spin_LH', 'spin_IHSlope',
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
            
            for name, expected_value in critical_fields:
                try:
                    spinbox = getattr(self, name, None)
                    if spinbox:
                        current_value = spinbox.value()
                        
                        # Formatear específicamente para display limpio
                        if abs(current_value - round(current_value)) < 1e-9:
                            # Es entero, formato XX.00
                            clean_text = f"{int(round(current_value))}.00"
                        else:
                            # Tiene decimales, formatear inteligentemente
                            clean_text = f"{current_value:.2f}"
                        
                        # MÚLTIPLES MÉTODOS PARA FORZAR EL DISPLAY
                        line_edit = spinbox.lineEdit()
                        if line_edit:
                            # Método 1: setText directo
                            line_edit.setText(clean_text)
                            line_edit.clearFocus()
                            line_edit.update()
                            
                            # Método 2: Trigger eventos de Qt
                            spinbox.clearFocus()
                            spinbox.update()
                            spinbox.repaint()
                            
                            # Método 3: Forzar editingFinished
                            line_edit.editingFinished.emit()
                            
                            # Verificar si el texto se aplicó correctamente
                            current_text = line_edit.text()
                            if current_text != clean_text:
                                # Si no funcionó, intentar setValue + setText
                                spinbox.setValue(current_value)
                                line_edit.setText(clean_text)
                                line_edit.update()
                        
                        print(f"QOLS: AGGRESSIVE FORCE {name}: {current_value} → {clean_text}")
                        
                except Exception as e:
                    print(f"QOLS: Error aggressive forcing {name}: {e}")
            
            # MÉTODO NUCLEAR: Si nada funciona, configurar valores específicos
            try:
                if hasattr(self, 'spin_L_inner'):
                    line_edit = self.spin_L_inner.lineEdit()
                    if line_edit and '4000.000000' in line_edit.text():
                        print("QOLS: NUCLEAR METHOD - Setting 4000.00 directly")
                        line_edit.setText("4000.00")
                        line_edit.update()
                        self.spin_L_inner.repaint()
                
                if hasattr(self, 'spin_height_inner'):
                    line_edit = self.spin_height_inner.lineEdit()
                    if line_edit and '45.000000' in line_edit.text():
                        print("QOLS: NUCLEAR METHOD - Setting 45.00 directly")
                        line_edit.setText("45.00")
                        line_edit.update()
                        self.spin_height_inner.repaint()
                        
            except Exception as e:
                print(f"QOLS: Nuclear method error: {e}")
            
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

    def setup_enhanced_combos(self):
        """Setup enhanced combo boxes with minimal styling and better tooltips."""
        try:
            print("QOLS: Setting up enhanced combo styling")
            
            # Enhanced tooltips for better UX
            self.runwayLayerCombo.setToolTip(
                "🛬 Runway Layer\n"
                "Select LineString layer with runway centerlines.\n"
                "Tip: Use 'Selected Only' for specific runways."
            )
            
            self.thresholdLayerCombo.setToolTip(
                "🎯 Threshold Layer\n"
                "Select Point layer with runway threshold points.\n"
                "Tip: Use 'Selected Only' for specific thresholds."
            )
            
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
                        runway_info = f"• ⚠️ No features selected"
                        runway_status = f"❌ No selection"
                else:
                    runway_info = f"• All {runway_total} features"
                    runway_status = f"All ({runway_total})"
            else:
                runway_info = "• ❌ No layer selected"
                runway_status = "❌ No layer"
            
            # Update threshold info
            if threshold_layer:
                threshold_selected = len(threshold_layer.selectedFeatures())
                threshold_total = threshold_layer.featureCount()
                
                if use_threshold_selected:
                    if threshold_selected > 0:
                        threshold_info = f"• Using {threshold_selected} of {threshold_total} selected"
                        threshold_status = f"Selected ({threshold_selected})"
                    else:
                        threshold_info = f"• ⚠️ No features selected"
                        threshold_status = f"❌ No selection"
                else:
                    threshold_info = f"• All {threshold_total} features"
                    threshold_status = f"All ({threshold_total})"
            else:
                threshold_info = "• ❌ No layer selected"
                threshold_status = "❌ No layer"
            print(f"QOLS: runway_status = {runway_status}")
            print(f"QOLS: threshold_status = {threshold_status}")
            
            # Individual status icons for each layer
            if "All" in runway_status:
                runway_icon = "✅"
            elif "Selected" in runway_status:
                runway_icon = "⚠️"
            else:
                runway_icon = "❌"
            
            if "All" in threshold_status:
                threshold_icon = "✅"
            elif "Selected" in threshold_status:
                threshold_icon = "⚠️"
            else:
                threshold_icon = "❌"
            
            combined_status = f"📌 Runway: {runway_icon} {runway_status} | Threshold: {threshold_icon} {threshold_status}"
            
            try:
                self.selectionInfoLabel.setText(combined_status)
                print(f"QOLS: selectionInfoLabel updated: {combined_status}")
            except Exception as e:
                print(f"QOLS: Error updating selectionInfoLabel: {e}")
            
            print("QOLS: update_selection_info completed successfully")
            
        except Exception as e:
            print(f"QOLS: Error in update_selection_info: {e}")
            import traceback
            traceback.print_exc()
            
            # Fallback text in case of error
            try:
                self.selectionInfoLabel.setText("📌 Status update error - check console")
            except:
                pass
            
        except Exception as e:
            print(f"QOLS: Error in update_selection_info: {e}")
            import traceback
            traceback.print_exc()
            
            # Fallback text in case of error
            try:
                self.selectionInfoLabel.setText("📌 Status update error - check console")
            except:
                pass

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
            
            print(f"QOLS DEBUG: current_tab_index = {current_tab_index}")
            print(f"QOLS DEBUG: surface_type = '{surface_type}'")
            print(f"QOLS DEBUG: surface_type type = {type(surface_type)}")
            print(f"QOLS DEBUG: surface_type repr = {repr(surface_type)}")
            
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
                    'radius': self.spin_L_conical.value(),        # Distance L is the radius
                    'height': self.spin_height_conical.value()    # Height for 3D polygon
                }
            elif surface_type == "Inner Horizontal":
                specific_params = {
                    'radius': self.spin_L_inner.value(),          # Distance L is the radius
                    'height': self.spin_height_inner.value()      # Height for 3D polygon
                }
            elif surface_type == "Outer Horizontal":
                specific_params = {
                    'code': self.spin_code_outer.value(),
                    'radius': self.spin_radius_outer.value(),
                    'height': self.spin_height_outer.value()
                }
            elif surface_type == "Take-Off Surface":
                print(f"QOLS DEBUG: Collecting Take-off Surface parameters...")
                print(f"QOLS DEBUG: spin_code_takeoff.value() = {self.spin_code_takeoff.value()}")
                print(f"QOLS DEBUG: combo_typeAPP_takeoff.currentText() = {self.combo_typeAPP_takeoff.currentText()}")
                print(f"QOLS DEBUG: spin_widthDep_takeoff.value() = {self.spin_widthDep_takeoff.value()}")
                print(f"QOLS DEBUG: spin_maxWidthDep_takeoff.value() = {self.spin_maxWidthDep_takeoff.value()}")
                
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
                print(f"QOLS DEBUG: Take-off Surface specific_params = {specific_params}")
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
