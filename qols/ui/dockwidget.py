"""qOLS dock-widget UI layer.

Contains :class:`QolsDockWidget`, the main panel that users see inside
QGIS.  Responsible for:

* Rendering the tabbed parameter form (Approach, OFZ, Transitional,
  Inner Horizontal + Conical, Outer Horizontal, Take-Off).
* Computing ICAO / rule-set default values and populating the form fields.
* Collecting typed parameter values and returning them for script dispatch.

Business logic (ICAO table lookups, rule-set merging) lives in
:mod:`qols.surfaces.icao`, :mod:`qols.surfaces.approach`, and
:mod:`qols.rules.manager`.
"""
import os
import traceback
from dataclasses import dataclass
from ..surfaces.icao import (
    get_conical_defaults as icao_get_conical_defaults,
    get_inner_horizontal_defaults as icao_get_inner_horizontal_defaults,
    get_takeoff_defaults as icao_get_takeoff_defaults,
)
from ..rules import manager as rule_mgr
from ..surfaces.approach import get_approach_defaults as icao_get_approach_defaults
from ..surface_types import SurfaceType
from .. import logger  # CR-01
from qgis.PyQt import uic
from qgis.PyQt.QtCore import pyqtSignal, pyqtSlot, QRegularExpression
from qgis.PyQt.QtGui import QRegularExpressionValidator
from qgis.PyQt.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QDockWidget,
    QLabel, QLineEdit, QMessageBox, QTextBrowser, QToolTip, QVBoxLayout,
)
from ..compat import EVENT_MOUSE_MOVE, TOOLTIP_ROLE, MSG_INFO, MSG_CRITICAL
from qgis.core import QgsMapLayerProxyModel, QgsProject, QgsWkbTypes, QgsVectorLayer

# Load the UI file
FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'qols_panel_base.ui'))


@dataclass
class _ApproachState:
    """Bundled output of apply_approach_defaults_from_selection.

    Stored as a single atomic assignment so partially-updated state is impossible.
    """
    divergence_ratio:    float = 0.15
    slope1:             float = 0.02
    slope2:             float = 0.025
    threshold_offset_m: float = 60.0


class QolsDockWidget(QDockWidget, FORM_CLASS):
    closingPlugin = pyqtSignal()
    calculateClicked = pyqtSignal()
    closeClicked = pyqtSignal()

    # Single source of truth for numeric widget defaults (CR-06).
    # All three methods that set initial/reset values read from here.
    _WIDGET_DEFAULTS: dict = {
        # Approach
        'spin_widthApp':              280.0,
        'spin_Z0':                   2548.0,
        'spin_ZE':                   2546.5,
        'spin_ARPH':                 2548.0,
        'spin_L1':                   3000.0,
        'spin_L2':                   3600.0,
        'spin_LH':                   8400.0,
        # Inner Horizontal + Conical
        'spin_L_conical':            6000.0,
        'spin_height_conical':         60.0,
        'spin_L_inner':              4000.0,
        'spin_height_inner':           45.0,
        # OFZ
        'spin_width_ofz':             120.0,
        'spin_Z0_ofz':               2548.0,
        'spin_ZE_ofz':               2546.5,
        'spin_ARPH_ofz':             2548.0,
        'spin_IHSlope_ofz':            33.3,
        # Outer Horizontal
        'spin_radius_outer':        15000.0,
        'spin_height_outer':          150.0,
        # Take-Off
        'spin_widthDep_takeoff':      180.0,
        'spin_maxWidthDep_takeoff':  1800.0,
        'spin_CWYLength_takeoff':       0.0,
        'spin_Z0_takeoff':           2548.0,
        # Transitional
        'spin_widthApp_transitional': 280.0,
        'spin_Z0_transitional':      2548.0,
        'spin_ZE_transitional':      2546.5,
        'spin_ARPH_transitional':    2548.0,
        'spin_Tslope_transitional':    14.3,
    }

    # Widgets declared in qols_panel_base.ui, guaranteed available after setupUi() (R-04)
    spin_code_takeoff: QComboBox
    check_finalWidth1800_takeoff: QCheckBox
    combo_rwyClassification: QComboBox
    spin_code: QComboBox
    combo_rwyClassification_ofz: QComboBox
    spin_code_ofz: QComboBox
    combo_rwyClassification_inner_conical: QComboBox
    spin_code_inner_conical: QComboBox
    spin_conical_slope: QLineEdit
    spin_height_conical: QLineEdit
    spin_L_inner: QLineEdit
    spin_L_conical: QLineEdit
    combo_rwyClassification_transitional: QComboBox
    spin_code_transitional: QComboBox
    # Additional widgets guaranteed by setupUi() (R-04)
    label_not_applicable_ofz: QLabel
    spin_IHSlope_ofz: QLineEdit
    spin_maxWidthDep_takeoff: QLineEdit
    runwaySelectionStatusLabel: QLabel
    thresholdSelectionStatusLabel: QLabel

    def __init__(self, iface, parent=None):
        """Constructor with enhanced error handling and layer management."""
        super(QolsDockWidget, self).__init__(parent)
        self.iface = iface

        # Track connected layers for selection signals (Issue #59)
        self.connected_runway_layer = None
        self.connected_threshold_layer = None
        # Lambda slots stored for proper selectionChanged disconnection (Issue #105)
        self._runway_selection_slot = None
        self._threshold_selection_slot = None
        # State tracking for dropdown tooltip optimization (BUG-05)
        self._last_runway_count = 0
        self._last_threshold_count = 0
        # Tracked signal connections for clean teardown in closeEvent (R-05)
        self._connections: list = []
        # Cached approach defaults — always exists so get_parameters() never needs getattr fallback
        self._approach_state: _ApproachState = _ApproachState()

        try:
            self.setupUi(self)

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
                self._connect(self.spin_code_takeoff.currentIndexChanged, self.update_takeoff_defaults_from_code)
                self._connect(self.spin_code_takeoff.currentIndexChanged, self.update_takeoff_final_width_controls)
                self._connect(self.check_finalWidth1800_takeoff.toggled, self.on_final_width_checkbox_toggled)
            except Exception as e:
                logger.warning(f"Could not connect Take-Off code change handler: {e}")

            self.useSelectedRunwayCheckBox.setChecked(False)
            self.useSelectedThresholdCheckBox.setChecked(False)

            self.initialize_all_numeric_defaults()
            self.update_takeoff_final_width_controls()

            try:
                self._connect(self.combo_rwyClassification.currentIndexChanged,
                              self.apply_approach_defaults_from_selection)
                self._connect(self.spin_code.currentIndexChanged,
                              self.apply_approach_defaults_from_selection)
            except Exception as e:
                logger.warning(f"Could not connect Approach defaults handlers: {e}")

            try:
                self._connect(self.combo_rwyClassification_ofz.currentIndexChanged,
                              self.update_ofz_visibility)
                self._connect(self.combo_rwyClassification_ofz.currentIndexChanged,
                              self.apply_ofz_defaults_from_selection)
                self._connect(self.spin_code_ofz.currentIndexChanged,
                              self.apply_ofz_defaults_from_selection)
            except Exception as e:
                logger.warning(f"Could not connect OFZ visibility handler: {e}")

            try:
                self.combo_rwyClassification_inner_conical.setCurrentText('Precision Approach CAT I')
                self.set_code_value('spin_code_inner_conical', 4)
                self._wire_combined_inner_conical_defaults()
                self.apply_combined_inner_conical_defaults_from_selection()
            except Exception as e:
                logger.warning(f"Could not initialize RWY/Code defaults for Conical/Inner: {e}")

            try:
                self._connect(self.spin_conical_slope.editingFinished, self.recalculate_conical_radius)
                self._connect(self.spin_height_conical.editingFinished, self.recalculate_conical_radius)
                self._connect(self.spin_L_inner.editingFinished, self.recalculate_conical_radius)
            except Exception as e:
                logger.warning(f"Could not connect conical radius recalculation signals: {e}")

            try:
                self._connect(self.combo_rwyClassification_transitional.currentIndexChanged,
                              self.apply_transitional_defaults_from_selection)
                self._connect(self.spin_code_transitional.currentIndexChanged,
                              self.apply_transitional_defaults_from_selection)
            except Exception as e:
                logger.warning(f"Could not connect Transitional defaults handlers: {e}")

            try:
                self._apply_all_defaults()
            except Exception as e:
                logger.warning(f"Could not apply initial defaults: {e}")

            # Connect signals for real-time feedback (tracked for clean closeEvent teardown)
            self._connect(self.useSelectedRunwayCheckBox.toggled, self.update_selection_info)
            self._connect(self.useSelectedThresholdCheckBox.toggled, self.update_selection_info)
            self._connect(self.runwayLayerCombo.layerChanged, self.update_selection_info)
            self._connect(self.thresholdLayerCombo.layerChanged, self.update_selection_info)

            # Connect to layer changes for selection signal management (Issue #59)
            self._connect(self.runwayLayerCombo.layerChanged, self.connect_layer_selection_signals)
            self._connect(self.thresholdLayerCombo.layerChanged, self.connect_layer_selection_signals)

            # SAFETY: Connect to layer combo changes for immediate validation
            self._connect(self.runwayLayerCombo.layerChanged, self.validate_layer_change)
            self._connect(self.thresholdLayerCombo.layerChanged, self.validate_layer_change)

            # Connect signals
            self._connect(self.calculateButton.clicked, self.on_calculate_clicked)
            self._connect(self.cancelButton.clicked, self.on_close_clicked)
            self._connect(self.directionButton.clicked, self.toggle_direction)
            self._connect(self.button_rotate_transitional.clicked, self.toggle_transitional_direction)

            # Connect tab change to reinitialize defaults (helpful for widget visibility)
            self._connect(self.scriptTabWidget.currentChanged, self.on_tab_changed)

            # Set initial direction
            self.direction_start_to_end = True
            self.transitional_direction_normal = True  # True = normal (s=0), False = rotated (s=-1)

            # Update direction buttons and initial selection info
            self.update_direction_button()
            self.update_transitional_direction_button()
            self.update_selection_info()

            # Apply initial OFZ visibility state after UI setup
            try:
                self.update_ofz_visibility()
            except Exception as e:
                logger.warning(f"Unhandled error: {e}")

            # Initialize selection signal connections (Issue #59)
            try:
                self.connect_layer_selection_signals()
            except Exception as e:
                logger.warning(f"Unhandled error: {e}")

            # Update active rule set label (if present)
            try:
                self.update_active_rule_set_label()
            except Exception as e:
                logger.warning(f"Unhandled error: {e}")

        except Exception as e:
            logger.error(f"Error in QolsDockWidget.__init__: {e}\n{traceback.format_exc()}")
            raise

    def update_active_rule_set_label(self):
        try:
            label = getattr(self, 'activeRuleSetLabel', None)
            if not label:
                return
            name = rule_mgr.get_active_rule_set_name() or 'ICAO (built-in)'
            label.setText(name)
        except Exception as e:
            logger.error(f"Error updating active rule set label: {e}")

    def setup_numeric_lineedit_validation(self):
        """Configure numeric input validation for all QLineEdit widgets (formerly QDoubleSpinBox)."""
        try:
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
                'spin_ARPH_transitional', 'spin_Tslope_transitional',
            ]

            # Allow unlimited decimals; optional sign and decimal part
            decimal_pattern = r'^-?\d*(?:\.\d*)?$'
            regex = QRegularExpression(decimal_pattern)
            validator = QRegularExpressionValidator(regex)

            for name in lineedit_names:
                try:
                    lineedit = getattr(self, name, None)
                    if lineedit and hasattr(lineedit, 'setText'):
                        lineedit.setValidator(validator)
                        v = self._WIDGET_DEFAULTS.get(name, 0.0)
                        text = f"{int(round(v))}.00" if abs(v - round(v)) < 1e-6 else f"{v:.2f}"
                        lineedit.setText(text)
                        self._configure_smart_formatting(lineedit)
                except Exception as e:
                    logger.warning(f"Unhandled error: {e}")

        except Exception as e:
            logger.warning(f"Unhandled error: {e}")

    def _configure_smart_formatting(self, lineedit):
        """Smart formatting for QLineEdit: show clean 2-decimals for simple values."""
        def format_on_focus_out():
            text = lineedit.text().strip()
            if not text:
                return
            try:
                value = float(text)
                if abs(value - round(value)) < 1e-6:
                    lineedit.setText(f"{int(round(value))}.00")
                elif abs(value - round(value, 2)) < 1e-6:
                    lineedit.setText(f"{value:.2f}")
            except ValueError:
                lineedit.setText('0.00')

        try:
            lineedit.editingFinished.connect(format_on_focus_out)
        except Exception as e:
            logger.warning(f"Smart formatting setup failed for {lineedit.objectName()}: {e}")

    def initialize_all_numeric_defaults(self):
        """Initialize default values for all numeric surface widgets from _WIDGET_DEFAULTS."""
        try:
            for widget_name, default_value in self._WIDGET_DEFAULTS.items():
                self.set_numeric_value(widget_name, default_value)
            # Default checkbox checked
            self.check_finalWidth1800_takeoff.setChecked(True)
        except Exception as e:
            logger.warning(f"Unhandled error: {e}")

        # Non-numeric widget initialisation
        try:
            self.set_code_value('spin_code_transitional', 4)
            try:
                self.combo_rwyClassification_transitional.setCurrentText('Precision Approach CAT I')
            except AttributeError:
                pass
        except Exception as e:
            logger.warning(f"Unhandled error: {e}")

        # Code dropdowns
        try:
            # Initialize code dropdowns
            self.set_code_value('spin_code', 4)
            self.set_code_value('spin_code_ofz', 4)
            self.set_code_value('spin_code_takeoff', 4)
            self.set_code_value('spin_code_outer', 4)
            # Apply defaults from table for initial Take-Off code
            try:
                self.update_takeoff_defaults_from_code()
            except Exception as e:
                logger.warning(f"Unhandled error: {e}")

            # Initialize RWY Classification dropdowns
            try:
                self.combo_rwyClassification.setCurrentText('Precision Approach CAT I')
            except AttributeError:
                pass

            try:
                self.combo_rwyClassification_ofz.setCurrentText('Precision Approach CAT I')
            except AttributeError:
                pass

        except Exception as e:
            logger.warning(f"Unhandled error: {e}")

    def refresh_defaults(self) -> None:
        """Public hook for plugin.py to call after a rule-set change (CR-07)."""
        self._apply_all_defaults()

    def _apply_all_defaults(self) -> None:
        """Unified defaults initialisation (M-04).

        Called once from ``__init__`` after ``setupUi()`` has run so that
        *all* surface tabs are seeded with consistent ICAO / rule-set values in
        a single, predictable pass.

        Order matters: combined Inner+Conical must be applied *after* the
        individual Approach/OFZ/Transitional passes so the computed conical
        radius is based on the already-populated inner-horizontal value.
        """
        self.apply_approach_defaults_from_selection()
        self.apply_ofz_defaults_from_selection()
        self.apply_transitional_defaults_from_selection()
        self.apply_combined_inner_conical_defaults_from_selection()

    def _wire_combined_inner_conical_defaults(self):
        """Connect change signals to apply defaults when RWY/Code change in combined tab."""
        try:
            self._connect(self.combo_rwyClassification_inner_conical.currentIndexChanged,
                          self.apply_combined_inner_conical_defaults_from_selection)
            self._connect(self.spin_code_inner_conical.currentIndexChanged,
                          self.apply_combined_inner_conical_defaults_from_selection)
        except Exception as e:
            logger.warning(f"Unhandled error: {e}")

    # ICAO Table-based defaults for Combined Inner Horizontal & Conical
    @pyqtSlot()
    def apply_combined_inner_conical_defaults_from_selection(self):
        """Apply defaults to both Inner Horizontal and Conical using shared classification/code.

        Uses :meth:`_get_merged_defaults` (R-01) to keep the rule/ICAO merge logic DRY.
        """
        try:
            rwy = self.combo_rwyClassification_inner_conical.currentText()
            code = self.get_code_value('spin_code_inner_conical')

            # --- Inner Horizontal defaults (R-01) ---
            inner_defaults = self._get_merged_defaults(
                rule_mgr.get_inner_horizontal_defaults,
                icao_get_inner_horizontal_defaults,
                rwy, code,
            )
            self.set_numeric_value('spin_L_inner', inner_defaults.get('radius_m', 4000.0))
            self.set_numeric_value('spin_height_inner', inner_defaults.get('height_m', 45.0))

            # --- Conical defaults (R-01) ---
            # con_rule kept separately so we can distinguish rule-supplied radius_m from ICAO fallback.
            con_rule = rule_mgr.get_conical_defaults(rwy, code)
            conical_defaults = self._get_merged_defaults(
                rule_mgr.get_conical_defaults,
                icao_get_conical_defaults,
                rwy, code,
            )
            self.set_numeric_value('spin_height_conical', conical_defaults.get('height_m', 60.0))

            # Slope: rule-supplied value wins; fall back to 5 %
            slope_pct = conical_defaults.get('slope_pct', 5.0) or 5.0
            self.set_numeric_value('spin_conical_slope', slope_pct)

            # If the active rule supplies an explicit radius, apply it directly and skip recalc.
            # We use con_rule (not the merged dict) so we don't mistake the ICAO 6000 m fallback
            # for an intentional rule value.
            con_rule_radius = con_rule.get('radius_m') if con_rule else None
            if con_rule_radius is not None:
                self.set_numeric_value('spin_L_conical', con_rule_radius)
                skip_recalc = True
            else:
                skip_recalc = False

            # Recalculate conical radius from height/slope+inner unless the rule provided one
            if not skip_recalc:
                self.recalculate_conical_radius()

        except Exception as e:
            logger.warning(f"Unhandled error: {e}")

    # Issue #51: Hide OFZ parameters when RWY Classification is Non-instrument or Non-precision approach
    def update_ofz_visibility(self):
        try:
            classification = self.combo_rwyClassification_ofz.currentText().strip()
            not_applicable = classification in [
                'Non-instrument',
                'Non-precision approach'
            ]

            param_widgets = [
                'label_code_ofz', 'spin_code_ofz',
                'label_width_ofz', 'spin_width_ofz',
                'label_Z0_ofz', 'spin_Z0_ofz',
                'label_ZE_ofz', 'spin_ZE_ofz',
                'label_ARPH_ofz', 'spin_ARPH_ofz',
                'label_IHSlope_ofz', 'spin_IHSlope_ofz'
            ]

            # Show/hide parameter widgets
            for name in param_widgets:
                w = getattr(self, name, None)
                if w:
                    w.setVisible(not not_applicable)

            # Show/hide notice label
            self.label_not_applicable_ofz.setVisible(not_applicable)

        except Exception as e:
            logger.warning(f"Unhandled error: {e}")

    # Issue #59: Dynamic selection signal management for true live status
    @pyqtSlot()
    def connect_layer_selection_signals(self):
        """Connect to selectionChanged signals of current layers for live status updates."""
        try:
            # Disconnect from previously connected layers
            self.disconnect_layer_selection_signals()

            runway_layer = self.runwayLayerCombo.currentLayer()
            threshold_layer = self.thresholdLayerCombo.currentLayer()

            # Connect to Runway Layer Centerline selection changes.
            # Lambda wrapper discards the 3 args emitted by selectionChanged so the
            # 0-arg update_selection_info slot is called correctly in both Qt5 and Qt6.
            if runway_layer and isinstance(runway_layer, QgsVectorLayer):
                self._runway_selection_slot = lambda *_: self.update_selection_info()
                runway_layer.selectionChanged.connect(self._runway_selection_slot)
                self.connected_runway_layer = runway_layer
            else:
                self._runway_selection_slot = None

            # Connect to threshold layer selection changes
            if threshold_layer and isinstance(threshold_layer, QgsVectorLayer):
                self._threshold_selection_slot = lambda *_: self.update_selection_info()
                threshold_layer.selectionChanged.connect(self._threshold_selection_slot)
                self.connected_threshold_layer = threshold_layer
            else:
                self._threshold_selection_slot = None

        except Exception as e:
            logger.warning(f"Unhandled error: {e}")

    def disconnect_layer_selection_signals(self):
        """Disconnect from previously connected layer selection signals."""
        try:
            if self.connected_runway_layer and self._runway_selection_slot:
                try:
                    self.connected_runway_layer.selectionChanged.disconnect(
                        self._runway_selection_slot
                    )
                except RuntimeError:
                    pass  # Signal might not be connected
                self.connected_runway_layer = None
                self._runway_selection_slot = None

            if self.connected_threshold_layer and self._threshold_selection_slot:
                try:
                    self.connected_threshold_layer.selectionChanged.disconnect(
                        self._threshold_selection_slot
                    )
                except RuntimeError:
                    pass  # Signal might not be connected
                self.connected_threshold_layer = None
                self._threshold_selection_slot = None

        except Exception as e:
            logger.warning(f"Unhandled error: {e}")

    @pyqtSlot()
    def recalculate_conical_radius(self):
        """Compute Conical Radius = Height / Slope + Inner Horizontal Radius.
        Slope entered as percent. Falls back safely if fields missing.
        """
        try:
            height = self.get_numeric_value('spin_height_conical')
            slope_pct = self.get_numeric_value('spin_conical_slope')
            slope = slope_pct / 100.0 if slope_pct else 0.05
            inner_radius = self.get_numeric_value('spin_L_inner')
            if slope <= 0:
                # Avoid division by zero; leave radius untouched
                return
            computed_radius = height / slope + inner_radius
            self.set_numeric_value('spin_L_conical', computed_radius)
        except Exception as e:
            logger.warning(f"Unhandled error: {e}")

    # Approach defaults (rules-aware)
    @pyqtSlot()
    def apply_approach_defaults_from_selection(self):
        try:
            rwy = self.combo_rwyClassification.currentText()
            code = self.get_code_value('spin_code')
            rd = rule_mgr.get_approach_defaults(rwy, code)
            if rd is None:
                d = icao_get_approach_defaults(rwy, code)
            else:
                base = icao_get_approach_defaults(rwy, code)
                d = dict(base)
                if 'width_m' in rd:
                    d['width_m'] = rd['width_m']
                if 'threshold_offset_m' in rd:
                    d['threshold_offset_m'] = rd['threshold_offset_m']
                if 'divergence_ratio' in rd:
                    d['divergence_ratio'] = rd['divergence_ratio']
                if 'L1_m' in rd:
                    d['L1_m'] = rd['L1_m']
                if 'slope1_ratio' in rd:
                    d['first_section_slope'] = rd['slope1_ratio']
                if 'L2_m' in rd:
                    d['L2_m'] = rd['L2_m']
                if 'slope2_ratio' in rd:
                    d['second_section_slope'] = rd['slope2_ratio']
                if 'LH_m' in rd:
                    d['LH_m'] = rd['LH_m']
            # Always override when classification/code changes
            self.set_numeric_value('spin_widthApp', d['width_m'])
            self.set_numeric_value('spin_L1', d['L1_m'])
            self.set_numeric_value('spin_L2', d['L2_m'])
            self.set_numeric_value('spin_LH', d['LH_m'])
            self._approach_state = _ApproachState(
                divergence_ratio=d['divergence_ratio'],
                slope1=d['first_section_slope'],
                slope2=d['second_section_slope'],
                threshold_offset_m=d['threshold_offset_m'],
            )
        except Exception as e:
            logger.warning(f"Unhandled error: {e}")

    @pyqtSlot()
    def apply_transitional_defaults_from_selection(self):
        try:
            rwy = self.combo_rwyClassification_transitional.currentText()
            code = self.get_code_value('spin_code_transitional')
            rd = rule_mgr.get_transitional_defaults(rwy, code)
            if rd and 'slope_pct' in rd:
                self.set_numeric_value('spin_Tslope_transitional', rd['slope_pct'])
        except Exception as e:
            logger.warning(f"Unhandled error: {e}")

    # ------------------------------------------------------------------
    # New OLS concept defaults (#107-#109)
    # ------------------------------------------------------------------

    @pyqtSlot()
    def apply_ofs_approach_defaults(self):
        """Populate OFS Approach fields from ICAO Tables 4-1/4-2 (New OLS #108)."""
        try:
            rwy_type = self.combo_rwyType_ofs.currentText()
            adg = self.combo_adg_ofs.currentText()
            try:
                rwy_width = float(self.spin_rwyWidth_ofs.text() or "45")
            except ValueError:
                rwy_width = 45.0
            d = get_new_ols_approach_defaults(rwy_type, adg, rwy_width)
            self.set_numeric_value('spin_distThr_ofs', d['distance_from_threshold_m'])
            self.set_numeric_value('spin_innerEdge_ofs', d['inner_edge_m'])
            self.set_numeric_value('spin_divergence_ofs', d['divergence_pct'])
            self.set_numeric_value('spin_length_ofs', d['length_m'])
            self.set_numeric_value('spin_slope_ofs', d['slope_pct'])
            self.apply_oes_transitional_defaults()
        except Exception as e:
            logger.warning(f"Unhandled error: {e}")

    @pyqtSlot()
    def apply_oes_transitional_defaults(self):
        """Populate OES Transitional fields (New OLS #109).

        The OES width tracks the OFS Approach inner edge.
        """
        try:
            d = get_new_ols_transitional_defaults()
            self.set_numeric_value('spin_slope_oes', d['slope_pct'])
            inner_edge_text = getattr(self, 'spin_innerEdge_ofs', None)
            if inner_edge_text and hasattr(inner_edge_text, 'text'):
                try:
                    inner_val = float(inner_edge_text.text() or "155")
                    self.set_numeric_value('spin_widthApp_oes', inner_val)
                except ValueError:
                    pass
        except Exception as e:
            logger.warning(f"Unhandled error: {e}")

    @pyqtSlot()
    def _show_adg_help_dialog(self):
        """Show ADG reference table (ICAO Table 1-2) in an HTML dialog."""
        try:
            html = """
<html><body>
<h3 style="margin-bottom:8px">Table 1-2 — Aeroplane Design Group (ADG)</h3>
<p style="font-size:11px">(see 1.8.2) &nbsp; Applicable as of 21 November 2030</p>
<table border="1" cellspacing="0" cellpadding="4" style="border-collapse:collapse;font-size:12px">
 <tr style="background:#444;color:#fff">
  <th>ADG</th>
  <th>Indicated airspeed at threshold</th>
  <th>and</th>
  <th>Wingspan</th>
 </tr>
 <tr><td>I</td><td>Less than 169 km/h (91 kt)</td><td>and</td><td>Up to but not including 24 m</td></tr>
 <tr><td>IIA</td><td>Less than 169 km/h (91 kt)</td><td>and</td><td>24 m up to but not including 36 m</td></tr>
 <tr><td>IIB</td>
 <td>169 km/h (91 kt) up to but not including 224 km/h (121 kt)</td>
 <td>and</td><td>Up to but not including 36 m</td></tr>
 <tr><td>IIC</td>
 <td>224 km/h (121 kt) up to but not including 307 km/h (166 kt)</td>
 <td>and</td><td>Up to but not including 36 m</td></tr>
 <tr><td>III</td><td>Less than 307 km/h (166 kt)</td><td>and</td><td>36 m up to but not including 52 m</td></tr>
 <tr><td>IV</td><td>Less than 307 km/h (166 kt)</td><td>and</td><td>52 m up to but not including 65 m</td></tr>
 <tr><td>V</td><td>Less than 307 km/h (166 kt)</td><td>and</td><td>65 m up to but not including 80 m</td></tr>
</table>
<p style="font-size:11px;margin-top:8px">
<b>Note 1.</b> Detailed specifications on ADG are given in the Airport Services Manual, Part 6.<br>
<b>Note 2.</b> Examples: 161 km/h (87 kt) and wingspan 20 m → ADG I; 307 km/h (166 kt) and wingspan 72 m → ADG IV.
</p>
</body></html>"""
            dlg = QDialog(self)
            dlg.setWindowTitle("ADG Reference Table — ICAO Table 1-2")
            dlg.resize(700, 320)
            browser = QTextBrowser(dlg)
            browser.setHtml(html)
            layout = QVBoxLayout(dlg)
            layout.addWidget(browser)
            dlg.setLayout(layout)
            dlg.exec()  # exec() works in both PyQt5 and PyQt6
        except Exception as e:
            logger.warning(f"Unhandled error in ADG help dialog: {e}")

    @pyqtSlot()
    def apply_ofz_defaults_from_selection(self):
        try:
            rwy = self.combo_rwyClassification_ofz.currentText()
            code = self.get_code_value('spin_code_ofz')
            rd = rule_mgr.get_ofz_defaults(rwy, code)
            if rd is None:
                return
            if 'width_m' in rd:
                self.set_numeric_value('spin_width_ofz', rd['width_m'])
            if 'ih_slope_pct' in rd:
                self.set_numeric_value('spin_IHSlope_ofz', rd['ih_slope_pct'])
            # Cache inner approach / balked landing defaults for OFZ script
            try:
                ia = rule_mgr.get_inner_approach_defaults(rwy, code) or {}
                bl = rule_mgr.get_balked_landing_defaults(rwy, code) or {}
                self._ia_defaults = ia
                self._bl_defaults = bl
            except Exception as e:
                logger.warning(f"Unhandled error: {e}")
        except Exception as e:
            logger.warning(f"Unhandled error: {e}")

    # ------------------------------------------------------------------
    # R-01 — DRY helper: merge rules + ICAO table defaults
    # ------------------------------------------------------------------

    @staticmethod
    def _get_merged_defaults(rule_fn, icao_fn, rwy: str, code: int) -> dict:
        """Return a merged defaults dict: ICAO base overridden by non-None rule values.

        Follows the pattern used throughout ``apply_*_defaults_from_selection``
        methods so that business logic lives in one place:

        1. Fetch full ICAO table row as the base (always available).
        2. Fetch the active rule-set row (may be ``None`` if no rule exists).
        3. Overlay every non-``None`` value from the rules on top of the ICAO
           base so that the rules are additive, never destructive.

        Args:
            rule_fn: Callable matching ``(rwy: str, code: int) -> dict | None``.
                     Typically a ``rule_mgr.get_*_defaults`` function.
            icao_fn: Callable matching ``(rwy: str, code: int) -> dict``.
                     Typically an ``icao_get_*`` function.
            rwy:     Runway classification string (e.g. ``"Precision Approach CAT I"``).
            code:    ICAO aerodrome reference code (1-4).

        Returns:
            Merged dict with ICAO values as fallback and rule values as override.
        """
        icao_d: dict = icao_fn(rwy, code)
        rule_d = rule_fn(rwy, code)
        if rule_d is None:
            return icao_d
        return {**icao_d, **{k: v for k, v in rule_d.items() if v is not None}}

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
                return

            # Handle QComboBox (new code dropdowns)
            if hasattr(widget, 'setCurrentText'):
                widget.setCurrentText(str(value))
                return

            # Handle QSpinBox (legacy code widgets)
            if hasattr(widget, 'setValue'):
                widget.setValue(value)
                return

        except Exception as e:
            logger.warning(f"Unhandled error: {e}")

    def set_numeric_value(self, widget_name, value):
        """Set numeric value in widget - works with both QLineEdit and QDoubleSpinBox."""
        try:
            widget = getattr(self, widget_name, None)
            if widget is None:
                return

            if hasattr(widget, 'setValue'):
                widget.setValue(float(value))
            elif hasattr(widget, 'setText'):
                if isinstance(value, (int, float)):
                    if abs(value - round(value)) < 0.000001:
                        widget.setText(f"{int(round(value))}.00")
                    else:
                        widget.setText(f"{value:.8f}".rstrip('0').rstrip('.'))
                else:
                    widget.setText(str(value))
            else:
                logger.warning(f"Widget {widget_name} has no setValue or setText method")
        except Exception as e:
            logger.warning(f"Could not set value for {widget_name}: {e}")

    def force_clean_display(self):
        """
        Forzar display limpio AGRESIVAMENTE.
        Se ejecuta múltiples veces hasta que funcione.
        """
        try:
            # Subset of _WIDGET_DEFAULTS that are prone to many-decimal display artifacts
            _force_clean_names = (
                'spin_L_conical', 'spin_height_conical', 'spin_L_inner', 'spin_height_inner',
                'spin_widthDep_takeoff', 'spin_maxWidthDep_takeoff', 'spin_CWYLength_takeoff', 'spin_Z0_takeoff',
            )
            for name in _force_clean_names:
                expected_value = self._WIDGET_DEFAULTS[name]
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

                except Exception as e:
                    logger.warning(f"Unhandled error: {e}")

            # Note: Nuclear method section removed - no longer needed since all widgets are QLineEdit

        except Exception as e:
            logger.warning(f"Unhandled error: {e}")

    def setup_layer_filters(self):
        """Configure layer combo boxes with geometry-specific filtering."""
        try:

            # Configure Runway Layer Centerline combo - only show LINE geometry layers
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

            # Connect to layer changes to reapply filters (tracked for closeEvent teardown)
            self._connect(QgsProject.instance().layersAdded, self.apply_geometry_filters)
            self._connect(QgsProject.instance().layersRemoved, self.apply_geometry_filters)

        except Exception as e:
            logger.warning(f"Unhandled error: {e}")

    def apply_geometry_filters(self):
        """Apply geometry-specific filters to layer combo boxes."""
        try:
            # Get all vector layers
            vector_layers = [
                layer for layer in QgsProject.instance().mapLayers().values()
                if isinstance(layer, QgsVectorLayer)
            ]

            # Filter Runway Layer Centerline layers - only show LINE geometry
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

        except Exception as e:
            logger.warning(f"Unhandled error: {e}")

    def setup_dropdown_tooltips(self):
        """Setup enhanced tooltips for dropdown items."""
        try:
            # CR-04: route through _connect() so teardown in closeEvent covers these
            # CR-05: stylesheet is applied once in setup_enhanced_combos; not repeated here
            self._connect(QgsProject.instance().layersAdded, self.update_dropdown_item_tooltips)
            self._connect(QgsProject.instance().layersRemoved, self.update_dropdown_item_tooltips)
            self._connect(self.runwayLayerCombo.layerChanged, self.update_dropdown_item_tooltips)
            self._connect(self.thresholdLayerCombo.layerChanged, self.update_dropdown_item_tooltips)

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
                logger.warning(f"Unhandled error: {e}")

            # Set initial item tooltips
            self.update_dropdown_item_tooltips()

        except Exception as e:
            logger.warning(f"Unhandled error: {e}")

    def update_dropdown_item_tooltips(self):
        """Update tooltips for individual dropdown items - native QGIS styling only."""
        try:
            # Reduce logging frequency - only log when layers change
            current_runway_count = self.runwayLayerCombo.count()
            current_threshold_count = self.thresholdLayerCombo.count()

            # Only proceed if layer counts have changed
            if (current_runway_count == self._last_runway_count
                    and current_threshold_count == self._last_threshold_count):
                return  # No changes, skip update

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
                        runway_model.setData(index, tooltip, TOOLTIP_ROLE)

                        # Method 2: Set via item data (backup method)
                        try:
                            self.runwayLayerCombo.setItemData(i, tooltip, TOOLTIP_ROLE)
                        except (AttributeError, TypeError):
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
                        threshold_model.setData(index, tooltip, TOOLTIP_ROLE)

                        # Method 2: Set via item data (backup method)
                        try:
                            self.thresholdLayerCombo.setItemData(i, tooltip, TOOLTIP_ROLE)
                        except (AttributeError, TypeError):
                            pass

                # Force view refresh to ensure tooltips are applied
                try:
                    self.runwayLayerCombo.view().update()
                    self.thresholdLayerCombo.view().update()
                except AttributeError:
                    pass

            except Exception as e:
                logger.warning(f"Unhandled error: {e}")

        except Exception as e:
            logger.error(f"update_dropdown_item_tooltips failed: {e}\n{traceback.format_exc()}")

    def get_geometry_type_name(self, layer):
        """Get readable geometry type name."""
        try:
            geom_type = layer.geometryType()
            if geom_type == QgsWkbTypes.PointGeometry:
                return "Point"
            elif geom_type == QgsWkbTypes.LineGeometry:
                return "LineString"
            elif geom_type == QgsWkbTypes.PolygonGeometry:
                return "Polygon"
            else:
                return "Unknown"
        except Exception:
            return "Unknown"

    def eventFilter(self, obj, event):
        """Handle events for dropdown hover tooltips - Native QGIS styling only."""
        try:
            # Check if this is a mouse move event in one of our dropdown views
            if event.type() == EVENT_MOUSE_MOVE:
                # Get the view that received the event
                if obj == self.runwayLayerCombo.view() or obj == self.thresholdLayerCombo.view():
                    # Get the item under the mouse
                    index = obj.indexAt(event.pos())
                    if index.isValid():
                        # Get the layer for this index
                        is_runway = obj == self.runwayLayerCombo.view()
                        combo = self.runwayLayerCombo if is_runway else self.thresholdLayerCombo
                        layer = combo.layer(index.row())
                        if layer:
                            geom_type = self.get_geometry_type_name(layer)
                            feature_count = layer.featureCount()
                            tooltip = f"Layer: {layer.name()}\nType: {geom_type}\nFeatures: {feature_count}"

                            # Method 1: Set tooltip on the view (native QGIS style)
                            obj.setToolTip(tooltip)

                            # Method 2: Force show tooltip at mouse position (native QGIS style)
                            try:
                                _gpos = event.globalPosition().toPoint()  # Qt6
                            except AttributeError:
                                _gpos = event.globalPos()                 # Qt5
                            QToolTip.showText(_gpos, tooltip, obj)

                        return False  # Let the event propagate normally
                    else:
                        # Mouse not over an item, hide tooltip
                        obj.setToolTip("")
                        QToolTip.hideText()

        except Exception as e:
            logger.warning(f"Unhandled error: {e}")

        # Call the base implementation for all other events
        return super().eventFilter(obj, event)

    def setup_enhanced_combos(self):
        """Reset combo boxes to default QGIS theme styling (no hardcoded colors)."""
        try:
            # Clear any inline stylesheets so the active QGIS theme (dark/light) owns rendering.
            self.runwayLayerCombo.setStyleSheet("")
            self.thresholdLayerCombo.setStyleSheet("")
        except Exception as e:
            logger.warning(f"Unhandled error: {e}")

    @pyqtSlot()
    def update_selection_info(self):
        """Update selection information in real-time with improved individual feedback."""
        try:
            runway_layer = self.runwayLayerCombo.currentLayer()
            threshold_layer = self.thresholdLayerCombo.currentLayer()

            use_runway_selected = self.useSelectedRunwayCheckBox.isChecked()
            use_threshold_selected = self.useSelectedThresholdCheckBox.isChecked()

            # Update runway info
            if runway_layer:
                runway_selected = len(runway_layer.selectedFeatures())
                runway_total = runway_layer.featureCount()

                if use_runway_selected:
                    if runway_selected > 0:
                        runway_status = f"Selected ({runway_selected})"
                    else:
                        runway_status = "No selection"
                else:
                    runway_status = f"All ({runway_total})"
            else:
                runway_status = "No layer"

            # Update threshold info
            if threshold_layer:
                threshold_selected = len(threshold_layer.selectedFeatures())
                threshold_total = threshold_layer.featureCount()

                if use_threshold_selected:
                    if threshold_selected > 0:
                        threshold_status = f"Selected ({threshold_selected})"
                    else:
                        threshold_status = "No selection"
                else:
                    threshold_status = f"All ({threshold_total})"
            else:
                threshold_status = "No layer"

            # Detect active theme (dark vs light) to pick readable label colors.
            _is_dark = QApplication.palette().window().color().lightness() < 128
            _c_warn = "#FFA726" if _is_dark else "#E65100"  # orange
            _c_ok = "#66BB6A" if _is_dark else "#2E7D32"  # green
            _c_err = "#EF5350" if _is_dark else "#C62828"  # red
            _base_style = "font-weight: bold; font-size: 11px;"

            if "All" in runway_status:
                runway_icon = "⚠"
                runway_style = f"QLabel {{ color: {_c_warn}; {_base_style} }}"
            elif "Selected" in runway_status:
                runway_icon = "✔"
                runway_style = f"QLabel {{ color: {_c_ok}; {_base_style} }}"
            else:
                runway_icon = "✘"
                runway_style = f"QLabel {{ color: {_c_err}; {_base_style} }}"

            if "All" in threshold_status:
                threshold_icon = "⚠"
                threshold_style = f"QLabel {{ color: {_c_warn}; {_base_style} }}"
            elif "Selected" in threshold_status:
                threshold_icon = "✔"
                threshold_style = f"QLabel {{ color: {_c_ok}; {_base_style} }}"
            else:
                threshold_icon = "✘"
                threshold_style = f"QLabel {{ color: {_c_err}; {_base_style} }}"

            # Update per-layer labels
            try:
                self.runwaySelectionStatusLabel.setText(f"{runway_icon} {runway_status}")
                self.runwaySelectionStatusLabel.setStyleSheet(runway_style)
                self.thresholdSelectionStatusLabel.setText(f"{threshold_icon} {threshold_status}")
                self.thresholdSelectionStatusLabel.setStyleSheet(threshold_style)
            except Exception as e:
                logger.warning(f"Unhandled error: {e}")

            # Update dropdown tooltips with current layer info
            self.update_dropdown_item_tooltips()

        except Exception as e:
            logger.error(f"update_selection_info failed: {e}\n{traceback.format_exc()}")

            # Fallback text in case of error
            try:
                self.runwaySelectionStatusLabel.setText("❌ Error")
                self.thresholdSelectionStatusLabel.setText("❌ Error")
            except (AttributeError, RuntimeError):
                pass

    def update_takeoff_defaults_from_code(self):
        """Apply default values from the ICAO table for Take-Off based on code."""
        try:
            code_value = self.get_code_value('spin_code_takeoff')

            # Table values per code — sourced from icao_defaults (Table 5-4)
            t = icao_get_takeoff_defaults(code_value)

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

            # Update max width — default from code table, editable by user
            # If Code 3/4, respect the checkbox setting; otherwise use table value
            if code_value in [3, 4] and self.check_finalWidth1800_takeoff.isChecked():
                self.spin_maxWidthDep_takeoff.setText("1800.0")
            elif code_value in [3, 4] and not self.check_finalWidth1800_takeoff.isChecked():
                self.spin_maxWidthDep_takeoff.setText("1200.0")
            else:
                self.spin_maxWidthDep_takeoff.setText(f"{t['final_width']:.1f}")

            # Update visibility of checkbox control based on code
            self.update_takeoff_final_width_controls()
        except Exception as e:
            logger.warning(f"Unhandled error: {e}")

    def update_takeoff_final_width_controls(self):
        """Show the 1800/1200 checkbox only for Code 3/4 and apply its value to max width if applicable."""
        try:
            code_value = self.get_code_value('spin_code_takeoff')
            is_code_3_4 = code_value in [3, 4]
            self.check_finalWidth1800_takeoff.setVisible(is_code_3_4)
            if is_code_3_4:
                # Apply current checkbox state to max width without overriding user edits elsewhere
                if self.check_finalWidth1800_takeoff.isChecked():
                    self.set_numeric_value('spin_maxWidthDep_takeoff', 1800.0)
                else:
                    self.set_numeric_value('spin_maxWidthDep_takeoff', 1200.0)
        except Exception as e:
            logger.warning(f"Unhandled error: {e}")

    def on_final_width_checkbox_toggled(self, checked: bool):
        """When the checkbox is toggled, update the max width for Code 3/4."""
        try:
            code_value = self.get_code_value('spin_code_takeoff')
            if code_value in [3, 4]:
                self.set_numeric_value('spin_maxWidthDep_takeoff', 1800.0 if checked else 1200.0)
        except Exception as e:
            logger.warning(f"Unhandled error: {e}")

    def validate_layer_change(self):
        """Validate layers immediately when user changes selection."""
        try:
            runway_layer = self.runwayLayerCombo.currentLayer()
            threshold_layer = self.thresholdLayerCombo.currentLayer()

            # Validate Runway Layer Centerline
            if runway_layer:
                if runway_layer.geometryType() != QgsWkbTypes.LineGeometry:
                    geom_type = self.get_layer_geometry_info(runway_layer)
                    self.show_error_message(
                        f"Invalid Runway Layer Centerline!\n"
                        f"'{runway_layer.name()}' contains {geom_type} geometry.\n"
                        f"Runway Layer Centerline must contain LINE geometry (runway lines)."
                    )
                    # Reset to no selection
                    self.runwayLayerCombo.setLayer(None)
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
                    self.thresholdLayerCombo.setLayer(None)
                    return

            # If both layers are valid, update status
            self.update_selection_info()

        except Exception as e:
            logger.warning(f"Unhandled error: {e}")

    def get_layer_geometry_info(self, layer):
        """Get human-readable geometry type information for a layer."""
        try:
            if not isinstance(layer, QgsVectorLayer):
                return "Not a vector layer"

            geom_type = layer.geometryType()

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
            vector_layers = [
                layer for layer in QgsProject.instance().mapLayers().values()
                if isinstance(layer, QgsVectorLayer)
            ]

            summary = []
            summary.append("=== LAYER SUMMARY ===")

            line_layers = []
            point_layers = []
            polygon_layers = []
            other_layers = []

            for layer in vector_layers:
                geom_info = self.get_layer_geometry_info(layer)
                layer_info = f"'{layer.name()}' ({geom_info}, {layer.featureCount()} features)"

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

    @pyqtSlot(int)
    def on_tab_changed(self, index):
        """Handle tab changes to ensure defaults are set properly."""
        try:
            # Get the current tab name
            current_tab = self.scriptTabWidget.widget(index)
            if current_tab:
                tab_name = current_tab.objectName()

                if 'transitional' in tab_name.lower():
                    self.apply_transitional_defaults_from_selection()

        except Exception as e:
            logger.warning(f"Unhandled error: {e}")

    def force_transitional_defaults(self):
        """Force set Transitional Surface default values."""
        try:
            for name, value in self._WIDGET_DEFAULTS.items():
                if 'transitional' in name:
                    try:
                        self.set_numeric_value(name, value)
                    except Exception as e:
                        logger.warning(f"Error setting {name}: {e}")

            # Set code and type (these are QComboBox)
            try:
                self.set_code_value('spin_code_transitional', 4)
            except Exception as e:
                logger.warning(f"Unhandled error: {e}")

            try:
                self.combo_rwyClassification_transitional.setCurrentText('Precision Approach CAT I')
            except AttributeError as e:
                logger.warning(f"Unhandled error: {e}")

        except Exception as e:
            logger.warning(f"Unhandled error: {e}")

    @pyqtSlot()
    def on_calculate_clicked(self):
        """Handle calculate button click with validation."""
        try:

            # Validate layers
            if not self.validate_layers():
                return

            # Show friendly message
            self.show_info_message("Starting calculation...")

            # Emit signal
            self.calculateClicked.emit()

        except Exception as e:
            self.show_error_message(f"Error starting calculation: {str(e)}")

    def _validate_project_crs(self) -> bool:
        """Return True if project CRS is projected; show blocking dialog and return False if geographic."""
        crs = QgsProject.instance().crs()
        if crs.isGeographic():
            QMessageBox.critical(
                self,
                "Projected Coordinate System Required",
                f"The QGIS project is using a geographic (non-projected) coordinate system:\n\n"
                f"  {crs.authid()} — {crs.description()}\n\n"
                f"OLS calculations require a projected CRS that uses metres as units.\n\n"
                f"To fix:\n"
                f"  1. Go to Project → Properties → CRS\n"
                f"  2. Select a projected CRS (e.g. a UTM zone for your area)\n"
                f"  3. Re-run the calculation."
            )
            return False
        return True

    def validate_layers(self):
        """Validate that required layers are selected with correct geometry types - ULTRA ROBUST VERSION."""
        try:
            # CRITICAL CHECK 0: Project CRS must be projected (not geographic/lat-lon)
            if not self._validate_project_crs():
                return False

            runway_layer = self.runwayLayerCombo.currentLayer()
            threshold_layer = self.thresholdLayerCombo.currentLayer()

            # CRITICAL CHECK 1: Ensure layers are selected
            if not runway_layer:
                self.show_error_message(
                    "No Runway Layer Centerline Selected!\n\n"
                    "Please select a Runway Layer Centerline from the dropdown.\n"
                    "The Runway Layer Centerline must contain LINE geometry (runway lines)."
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
                    f"Invalid Runway Layer Centerline Object!\n\n"
                    f"Selected object is not a valid vector layer: {type(runway_layer)}\n"
                    f"Please select a different Runway Layer Centerline."
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
                    f"Runway Layer Centerline Not Found!\n\n"
                    f"Layer '{runway_layer.name()}' is no longer in the project.\n"
                    f"It may have been removed. Please select a different Runway Layer Centerline."
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
                    f"Corrupted Runway Layer Centerline!\n\n"
                    f"Layer '{runway_layer.name()}' is invalid or corrupted.\n"
                    f"Please check the layer source and select a different Runway Layer Centerline."
                )
                return False

            if not threshold_layer.isValid():
                self.show_error_message(
                    f"Corrupted Threshold Layer!\n\n"
                    f"Layer '{threshold_layer.name()}' is invalid or corrupted.\n"
                    f"Please check the layer source and select a different threshold layer."
                )
                return False

            # CRITICAL CHECK 5: Validate Runway Layer Centerline geometry (must be LINE)
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
                    f"Empty Runway Layer Centerline!\n\n"
                    f"Layer '{runway_layer.name()}' contains no features.\n"
                    f"Please select a Runway Layer Centerline with runway line features."
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

            return True

        except Exception as e:
            logger.error(f"validate_layers unexpected error: {e}\n{traceback.format_exc()}")
            self.show_error_message(
                f"Critical Validation Error!\n\n"
                f"An unexpected error occurred during validation:\n{str(e)}\n\n"
                f"Please check the QGIS log for details and try again."
            )
            return False

    def show_info_message(self, message):
        """Show friendly info message to user."""
        self.iface.messageBar().pushMessage("QOLS Info", message, level=MSG_INFO, duration=3)

    def show_error_message(self, message):
        """Show friendly error message to user."""
        self.iface.messageBar().pushMessage("QOLS Error", message, level=MSG_CRITICAL, duration=5)

    @pyqtSlot()
    def on_close_clicked(self):
        """Handle close button click."""
        try:
            self.closeClicked.emit()
        except Exception as e:
            logger.warning(f"Unhandled error: {e}")

    def get_parameters(self):
        """Collect and return all UI parameters for the currently active surface tab.

        Returns a dict suitable for direct injection into the corresponding
        ``scripts/`` entry-point as ``globals()``.

        Direction normalisation (M-05 business-logic note)
        ---------------------------------------------------
        The UI exposes *Start Elevation* (``spin_Z0``) and *End Elevation*
        (``spin_ZE``) relative to the *runway* geometry direction.  When the
        user selects **End → Start**, these roles are physically reversed:
        the geometry traversal begins at the *end* point, so the datum
        elevation for that end must be supplied as Z0 to the calculation
        engine.  Accordingly, *for Approach surfaces only*, this method swaps
        the raw UI values:

        * ``direction_start_to_end`` (``s_value = 0``)  →  Z0_calc = z0_ui, ZE_calc = ze_ui
        * ``not direction_start_to_end`` (``s_value = -1``) →  Z0_calc = ze_ui, ZE_calc = z0_ui

        This swap is *intentional* and must **not** be removed.  Downstream
        scripts expect Z0 to always represent the datum at the computation
        start point.
        """
        try:
            runway_layer = self.runwayLayerCombo.currentLayer()
            threshold_layer = self.thresholdLayerCombo.currentLayer()

            use_runway_selected = self.useSelectedRunwayCheckBox.isChecked()
            use_threshold_selected = self.useSelectedThresholdCheckBox.isChecked()

            # Get direction
            direction = 0 if self.direction_start_to_end else -1

            # Determine surface type from active tab
            current_tab_index = self.scriptTabWidget.currentIndex()
            _tab_text = self.scriptTabWidget.tabText(current_tab_index)
            try:
                surface_type = SurfaceType.from_tab_text(_tab_text)
            except ValueError:
                raise Exception(f"Unknown surface type tab: {_tab_text!r}")

            # Get parameters based on current tab
            if surface_type == SurfaceType.APPROACH:
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

                code_value = self.get_code_value('spin_code')
                rwy_text = self.combo_rwyClassification.currentText()
                width_value = self.get_numeric_value('spin_widthApp')
                arph_value = self.get_numeric_value('spin_ARPH')
                l1_value = self.get_numeric_value('spin_L1')
                l2_value = self.get_numeric_value('spin_L2')
                lh_value = self.get_numeric_value('spin_LH')

                # Provide both legacy and pythonic keys for compatibility
                specific_params = {
                    # Legacy keys (kept)
                    'code': code_value,
                    'rwyClassification': rwy_text,
                    'widthApp': width_value,
                    'Z0': Z0_calc,
                    'ZE': ZE_calc,
                    'ARPH': arph_value,
                    'L1': l1_value,
                    'L2': l2_value,
                    'LH': lh_value,
                    's': s_value,
                    # Pythonic/UI-aligned keys (new)
                    'runway_code': code_value,
                    'rwy_classification': rwy_text,
                    'approach_width_m': width_value,
                    'start_elevation_m': Z0_calc,
                    'end_elevation_m': ZE_calc,
                    'arp_elevation_m': arph_value,
                    'first_section_length_m': l1_value,
                    'second_section_length_m': l2_value,
                    'horizontal_section_length_m': lh_value,
                    'direction': s_value,
                    # Derived approach defaults from last apply_approach_defaults_from_selection call
                    'divergence_ratio': self._approach_state.divergence_ratio,
                    'first_section_slope': self._approach_state.slope1,
                    'second_section_slope': self._approach_state.slope2,
                    'threshold_offset_m': self._approach_state.threshold_offset_m,
                    'contour_interval_m': int(round(self.get_numeric_value('spin_contour_interval')))
                }
            elif surface_type == SurfaceType.CONICAL:
                specific_params = {
                    'radius': self.get_numeric_value('spin_L_conical'),        # Distance L is the radius
                    'height': self.get_numeric_value('spin_height_conical'),   # Height for 3D polygon
                    'code': self.get_code_value('spin_code_inner_conical'),
                    'rwyClassification': self.combo_rwyClassification_inner_conical.currentText()
                }
            elif surface_type == SurfaceType.INNER_HORIZONTAL:
                specific_params = {
                    'radius': self.get_numeric_value('spin_L_inner'),          # Distance L is the radius
                    'height': self.get_numeric_value('spin_height_inner'),     # Height for 3D polygon
                    'code': self.get_code_value('spin_code_inner_conical'),
                    'rwyClassification': self.combo_rwyClassification_inner_conical.currentText()
                }
            elif surface_type == SurfaceType.INNER_CONICAL:
                inner_params = {
                    'radius': self.get_numeric_value('spin_L_inner'),
                    'height': self.get_numeric_value('spin_height_inner'),
                    'code': self.get_code_value('spin_code_inner_conical'),
                    'rwyClassification': self.combo_rwyClassification_inner_conical.currentText(),
                }
                conical_params = {
                    'radius': self.get_numeric_value('spin_L_conical'),
                    'height': self.get_numeric_value('spin_height_conical'),
                    'slope': self.get_numeric_value('spin_conical_slope'),
                    'code': self.get_code_value('spin_code_inner_conical'),
                    'rwyClassification': self.combo_rwyClassification_inner_conical.currentText(),
                }
                specific_params = {
                    'inner_horizontal': inner_params,
                    'conical': conical_params,
                    'combined_execution': True,
                }
            elif surface_type == SurfaceType.OUTER_HORIZONTAL:
                specific_params = {
                    'code': self.get_code_value('spin_code_outer'),
                    'radius': self.get_numeric_value('spin_radius_outer'),
                    'height': self.get_numeric_value('spin_height_outer'),
                }
            elif surface_type == SurfaceType.TAKEOFF:
                code_value = self.get_code_value('spin_code_takeoff')
                # Determine default maxWidthDep per code (editable), honoring checkbox for Code 3/4
                if code_value in [3, 4]:
                    default_max_width = 1800.0 if self.check_finalWidth1800_takeoff.isChecked() else 1200.0
                else:
                    default_max_width = float(self.spin_maxWidthDep_takeoff.text() or "1800")
                # Allow user override via spin_maxWidthDep_takeoff if provided
                user_max_width_text = self.spin_maxWidthDep_takeoff.text()
                max_width_dep = (
                    float(user_max_width_text) if user_max_width_text not in ["", None]
                    else default_max_width
                )

                # Direction parameter like Approach
                s_value = 0 if self.direction_start_to_end else -1

                # Per Issue #64: DER Elevation (Z0) is the datum; set ZE = Z0 to avoid ambiguity.
                specific_params = {
                    'code': code_value,  # QComboBox
                    'widthApp': 150,  # Remains constant for take-off width near origin
                    'widthDep': float(self.spin_widthDep_takeoff.text() or "0"),     # QLineEdit
                    'maxWidthDep': max_width_dep,  # Default from code; user-editable
                    'CWYLength': float(self.spin_CWYLength_takeoff.text() or "0"),   # QLineEdit (clearway length)
                    'Z0': float(self.spin_Z0_takeoff.text() or "0"),                 # DER Elevation (m)
                    'ZE': float(self.spin_Z0_takeoff.text() or "0"),  # ZE = Z0 per Issue #64
                    # Newly exposed parameters
                    'divergencePct': float(self.spin_divergence_takeoff.text() or "12.5"),
                    'startDistance': float(self.spin_startDistance_takeoff.text() or "60"),
                    'surfaceLength': float(self.spin_surfaceLength_takeoff.text() or "15000"),
                    'slopePct': float(self.spin_slope_takeoff.text() or "2.0"),
                    'direction': s_value,
                    'contour_interval_m': int(round(self.get_numeric_value('spin_contour_interval_takeoff')))
                }
            elif surface_type == SurfaceType.TRANSITIONAL:
                # Note: Using correct transitional surface widget names
                # IMPORTANT: For transitional, use the specific rotation button instead of general direction
                s_value = 0 if self.transitional_direction_normal else -1  # s = 0 for normal, s = -1 for rotated

                specific_params = {
                    'code': self.get_code_value('spin_code_transitional'),  # QComboBox
                    'rwyClassification': self.combo_rwyClassification_transitional.currentText(),
                    'widthApp': float(self.spin_widthApp_transitional.text() or "0"),  # QLineEdit
                    'Z0': float(self.spin_Z0_transitional.text() or "0"),              # QLineEdit
                    'ZE': float(self.spin_ZE_transitional.text() or "0"),              # QLineEdit
                    'ARPH': float(self.spin_ARPH_transitional.text() or "0"),          # QLineEdit
                    'Tslope': float(self.spin_Tslope_transitional.text() or "0") / 100.0,  # % → decimal
                    's': s_value  # Special parameter for transitional runway direction
                }
            elif surface_type == SurfaceType.OFZ:
                specific_params = {
                    'code': self.get_code_value('spin_code_ofz'),  # QComboBox
                    'rwyClassification': self.combo_rwyClassification_ofz.currentText(),
                    'width': float(self.spin_width_ofz.text() or "0"),
                    'Z0': float(self.spin_Z0_ofz.text() or "0"),
                    'ZE': float(self.spin_ZE_ofz.text() or "0"),
                    'ARPH': float(self.spin_ARPH_ofz.text() or "0"),
                    'IHSlope': float(self.spin_IHSlope_ofz.text() or "0") / 100.0  # Convert percentage to decimal
                }
                # Inject IA/BL params if available from rules
                try:
                    ia = getattr(self, '_ia_defaults', {}) or {}
                    bl = getattr(self, '_bl_defaults', {}) or {}
                    if ia:
                        specific_params['IA_width'] = ia.get('width_m')
                        specific_params['IA_distance_from_thr'] = ia.get('distance_from_threshold_m')
                        specific_params['IA_length'] = ia.get('length_m')
                        specific_params['IA_slope'] = ia.get('slope_ratio')
                    if bl:
                        specific_params['BL_width'] = bl.get('width_m')
                        specific_params['BL_distance_from_thr'] = bl.get('distance_from_threshold_m')
                        specific_params['BL_divergence'] = bl.get('divergence_ratio')
                        specific_params['BL_slope'] = bl.get('slope_ratio')
                except Exception as e:
                    logger.warning(f"Unhandled error: {e}")
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

            return params

        except Exception as e:
            self.show_error_message(f"Error collecting parameters: {str(e)}")
            return None

    def showEvent(self, event):
        super().showEvent(event)

    def _connect(self, signal, slot):
        """Connect signal to slot and register the pair for teardown in closeEvent."""
        signal.connect(slot)
        self._connections.append((signal, slot))

    def closeEvent(self, event):
        """Handle close event with proper cleanup."""
        try:

            # Disconnect tracked signals to prevent memory leaks
            for sig, slot in list(self._connections):
                try:
                    sig.disconnect(slot)
                except RuntimeError:
                    pass
            self._connections.clear()
            self.disconnect_layer_selection_signals()

            self.closingPlugin.emit()
            event.accept()
        except Exception:
            event.accept()
