"""New OLS dock widget — standalone panel for the New OLS concept.

Handles the OFS (Obstacle Free Surface) Approach and OES (Obstacle
Evaluation Surface) Transitional calculations per ICAO Annex 14.
Runs as an independent dock widget with its own toolbar button.
"""
import os
import traceback
from ..surfaces.new_ols_approach import get_new_ols_approach_defaults
from ..surfaces.new_ols_transitional import get_new_ols_transitional_defaults
from ..surface_types import SurfaceType
from .. import logger
from qgis.PyQt import uic
from qgis.PyQt.QtCore import pyqtSignal, pyqtSlot, QRegularExpression
from qgis.PyQt.QtGui import QRegularExpressionValidator
from qgis.PyQt.QtWidgets import (
    QApplication, QComboBox, QDialog, QDockWidget,
    QLabel, QLineEdit, QMessageBox, QTextBrowser, QToolTip, QVBoxLayout,
)
from ..compat import EVENT_MOUSE_MOVE, TOOLTIP_ROLE, MSG_INFO, MSG_CRITICAL
from qgis.core import QgsMapLayerProxyModel, QgsProject, QgsWkbTypes, QgsVectorLayer

FORM_CLASS, _ = uic.loadUiType(os.path.join(
    os.path.dirname(__file__), 'new_ols_panel.ui'))


class NewOlsDockWidget(QDockWidget, FORM_CLASS):
    closingPlugin = pyqtSignal()
    calculateClicked = pyqtSignal()
    closeClicked = pyqtSignal()

    _WIDGET_DEFAULTS: dict = {
        # OFS Approach
        'spin_rwyWidth_ofs':         45.0,
        'spin_distThr_ofs':          60.0,
        'spin_innerEdge_ofs':       155.0,
        'spin_divergence_ofs':       10.0,
        'spin_length_ofs':         4500.0,
        'spin_slope_ofs':            3.33,
        'spin_Z0_ofs':            2548.0,
        'spin_ZE_ofs':            2546.5,
        'spin_ARPH_ofs':          2548.0,
        'spin_contour_interval_ofs': 10.0,
        # OES Transitional
        'spin_widthApp_oes':        155.0,
        'spin_Z0_oes':            2548.0,
        'spin_ZE_oes':            2546.5,
        'spin_ARPH_oes':          2548.0,
        'spin_slope_oes':            20.0,
    }

    combo_rwyType_ofs: QComboBox
    combo_adg_ofs: QComboBox
    spin_rwyWidth_ofs: QLineEdit
    spin_distThr_ofs: QLineEdit
    spin_innerEdge_ofs: QLineEdit
    spin_divergence_ofs: QLineEdit
    spin_length_ofs: QLineEdit
    spin_slope_ofs: QLineEdit
    spin_Z0_ofs: QLineEdit
    spin_ZE_ofs: QLineEdit
    spin_ARPH_ofs: QLineEdit
    spin_contour_interval_ofs: QLineEdit
    spin_widthApp_oes: QLineEdit
    spin_Z0_oes: QLineEdit
    spin_ZE_oes: QLineEdit
    spin_ARPH_oes: QLineEdit
    spin_slope_oes: QLineEdit
    runwaySelectionStatusLabel: QLabel
    thresholdSelectionStatusLabel: QLabel

    def __init__(self, iface, parent=None):
        super(NewOlsDockWidget, self).__init__(parent)
        self.iface = iface
        self.connected_runway_layer = None
        self.connected_threshold_layer = None
        self._runway_selection_slot = None
        self._threshold_selection_slot = None
        self._last_runway_count = 0
        self._last_threshold_count = 0
        self._connections: list = []

        try:
            self.setupUi(self)
            self.setup_numeric_lineedit_validation()
            self.setup_layer_filters()
            self.setup_enhanced_combos()
            self.setup_dropdown_tooltips()

            self.useSelectedRunwayCheckBox.setChecked(False)
            self.useSelectedThresholdCheckBox.setChecked(False)

            try:
                self._connect(self.combo_rwyType_ofs.currentIndexChanged,
                              self.apply_ofs_approach_defaults)
                self._connect(self.combo_adg_ofs.currentIndexChanged,
                              self.apply_ofs_approach_defaults)
                self._connect(self.spin_rwyWidth_ofs.editingFinished,
                              self.apply_ofs_approach_defaults)
                self._connect(self.btn_adg_help.clicked, self._show_adg_help_dialog)
            except Exception as e:
                logger.warning(f"Could not connect New OLS OFS defaults handlers: {e}")

            try:
                self.apply_ofs_approach_defaults()
                self.apply_oes_transitional_defaults()
            except Exception as e:
                logger.warning(f"Could not apply initial New OLS defaults: {e}")

            self._connect(self.useSelectedRunwayCheckBox.toggled, self.update_selection_info)
            self._connect(self.useSelectedThresholdCheckBox.toggled, self.update_selection_info)
            self._connect(self.runwayLayerCombo.layerChanged, self.update_selection_info)
            self._connect(self.thresholdLayerCombo.layerChanged, self.update_selection_info)
            self._connect(self.runwayLayerCombo.layerChanged, self.connect_layer_selection_signals)
            self._connect(self.thresholdLayerCombo.layerChanged, self.connect_layer_selection_signals)
            self._connect(self.runwayLayerCombo.layerChanged, self.validate_layer_change)
            self._connect(self.thresholdLayerCombo.layerChanged, self.validate_layer_change)

            self._connect(self.calculateButton.clicked, self.on_calculate_clicked)
            self._connect(self.cancelButton.clicked, self.on_close_clicked)
            self._connect(self.directionButton.clicked, self.toggle_direction)

            self.direction_start_to_end = True
            self.update_direction_button()
            self.update_selection_info()

            try:
                self.connect_layer_selection_signals()
            except Exception as e:
                logger.warning(f"Unhandled error: {e}")

        except Exception as e:
            logger.error(f"Error in NewOlsDockWidget.__init__: {e}\n{traceback.format_exc()}")
            raise

    def setup_numeric_lineedit_validation(self):
        lineedit_names = [
            'spin_rwyWidth_ofs', 'spin_distThr_ofs', 'spin_innerEdge_ofs',
            'spin_divergence_ofs', 'spin_length_ofs', 'spin_slope_ofs',
            'spin_Z0_ofs', 'spin_ZE_ofs', 'spin_ARPH_ofs', 'spin_contour_interval_ofs',
            'spin_widthApp_oes', 'spin_Z0_oes', 'spin_ZE_oes', 'spin_ARPH_oes', 'spin_slope_oes',
        ]
        decimal_pattern = r'^-?\d*(?:\.\d*)?$'
        validator = QRegularExpressionValidator(QRegularExpression(decimal_pattern))
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

    def _configure_smart_formatting(self, lineedit):
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

    def setup_layer_filters(self):
        try:
            self.runwayLayerCombo.setFilters(QgsMapLayerProxyModel.VectorLayer)
            self.runwayLayerCombo.setExceptedLayerList([])
            self.runwayLayerCombo.setShowCrs(False)
            self.runwayLayerCombo.setAllowEmptyLayer(False)
            self.thresholdLayerCombo.setFilters(QgsMapLayerProxyModel.VectorLayer)
            self.thresholdLayerCombo.setExceptedLayerList([])
            self.thresholdLayerCombo.setShowCrs(False)
            self.thresholdLayerCombo.setAllowEmptyLayer(False)
            self.apply_geometry_filters()
            self._connect(QgsProject.instance().layersAdded, self.apply_geometry_filters)
            self._connect(QgsProject.instance().layersRemoved, self.apply_geometry_filters)
        except Exception as e:
            logger.warning(f"Unhandled error: {e}")

    def apply_geometry_filters(self):
        try:
            vector_layers = [
                layer for layer in QgsProject.instance().mapLayers().values()
                if isinstance(layer, QgsVectorLayer)
            ]
            runway_excluded = [lyr for lyr in vector_layers if lyr.geometryType() != QgsWkbTypes.LineGeometry]
            threshold_excluded = [lyr for lyr in vector_layers if lyr.geometryType() != QgsWkbTypes.PointGeometry]
            self.runwayLayerCombo.setExceptedLayerList(runway_excluded)
            self.thresholdLayerCombo.setExceptedLayerList(threshold_excluded)
        except Exception as e:
            logger.warning(f"Unhandled error: {e}")

    def setup_enhanced_combos(self):
        try:
            self.runwayLayerCombo.setStyleSheet("")
            self.thresholdLayerCombo.setStyleSheet("")
        except Exception as e:
            logger.warning(f"Unhandled error: {e}")

    def setup_dropdown_tooltips(self):
        try:
            self._connect(QgsProject.instance().layersAdded, self.update_dropdown_item_tooltips)
            self._connect(QgsProject.instance().layersRemoved, self.update_dropdown_item_tooltips)
            self._connect(self.runwayLayerCombo.layerChanged, self.update_dropdown_item_tooltips)
            self._connect(self.thresholdLayerCombo.layerChanged, self.update_dropdown_item_tooltips)
            try:
                runway_view = self.runwayLayerCombo.view()
                threshold_view = self.thresholdLayerCombo.view()
                runway_view.setMouseTracking(True)
                threshold_view.setMouseTracking(True)
                runway_view.installEventFilter(self)
                threshold_view.installEventFilter(self)
            except Exception as e:
                logger.warning(f"Unhandled error: {e}")
            self.update_dropdown_item_tooltips()
        except Exception as e:
            logger.warning(f"Unhandled error: {e}")

    def update_dropdown_item_tooltips(self):
        try:
            current_runway_count = self.runwayLayerCombo.count()
            current_threshold_count = self.thresholdLayerCombo.count()
            if (current_runway_count == self._last_runway_count
                    and current_threshold_count == self._last_threshold_count):
                return
            self._last_runway_count = current_runway_count
            self._last_threshold_count = current_threshold_count
            try:
                runway_model = self.runwayLayerCombo.model()
                for i in range(self.runwayLayerCombo.count()):
                    layer = self.runwayLayerCombo.layer(i)
                    if layer:
                        tooltip = (f"Layer: {layer.name()}\n"
                                   f"Type: {self.get_geometry_type_name(layer)}\n"
                                   f"Features: {layer.featureCount()}")
                        runway_model.setData(runway_model.index(i, 0), tooltip, TOOLTIP_ROLE)
                        try:
                            self.runwayLayerCombo.setItemData(i, tooltip, TOOLTIP_ROLE)
                        except (AttributeError, TypeError):
                            pass
                threshold_model = self.thresholdLayerCombo.model()
                for i in range(self.thresholdLayerCombo.count()):
                    layer = self.thresholdLayerCombo.layer(i)
                    if layer:
                        tooltip = (f"Layer: {layer.name()}\n"
                                   f"Type: {self.get_geometry_type_name(layer)}\n"
                                   f"Features: {layer.featureCount()}")
                        threshold_model.setData(threshold_model.index(i, 0), tooltip, TOOLTIP_ROLE)
                        try:
                            self.thresholdLayerCombo.setItemData(i, tooltip, TOOLTIP_ROLE)
                        except (AttributeError, TypeError):
                            pass
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
        try:
            geom_type = layer.geometryType()
            if geom_type == QgsWkbTypes.PointGeometry:
                return "Point"
            elif geom_type == QgsWkbTypes.LineGeometry:
                return "LineString"
            elif geom_type == QgsWkbTypes.PolygonGeometry:
                return "Polygon"
            return "Unknown"
        except Exception:
            return "Unknown"

    def get_layer_geometry_info(self, layer):
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
            return f"Unknown ({geom_type})"
        except Exception as e:
            return f"Error: {e}"

    def eventFilter(self, obj, event):
        try:
            if event.type() == EVENT_MOUSE_MOVE:
                if obj in (self.runwayLayerCombo.view(), self.thresholdLayerCombo.view()):
                    index = obj.indexAt(event.pos())
                    if index.isValid():
                        is_runway = obj == self.runwayLayerCombo.view()
                        combo = self.runwayLayerCombo if is_runway else self.thresholdLayerCombo
                        layer = combo.layer(index.row())
                        if layer:
                            tooltip = (f"Layer: {layer.name()}\n"
                                       f"Type: {self.get_geometry_type_name(layer)}\n"
                                       f"Features: {layer.featureCount()}")
                            obj.setToolTip(tooltip)
                            try:
                                _gpos = event.globalPosition().toPoint()
                            except AttributeError:
                                _gpos = event.globalPos()
                            QToolTip.showText(_gpos, tooltip, obj)
                        return False
                    else:
                        obj.setToolTip("")
                        QToolTip.hideText()
        except Exception as e:
            logger.warning(f"Unhandled error: {e}")
        return super().eventFilter(obj, event)

    def get_numeric_value(self, widget_name):
        try:
            widget = getattr(self, widget_name, None)
            if widget and hasattr(widget, 'text'):
                text = widget.text().strip()
                if text:
                    return float(text)
            return 0.0
        except (ValueError, AttributeError):
            return 0.0

    def set_numeric_value(self, widget_name, value):
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
        except Exception as e:
            logger.warning(f"Could not set value for {widget_name}: {e}")

    @pyqtSlot()
    def apply_ofs_approach_defaults(self):
        """Populate OFS Approach fields from ICAO Tables 4-1/4-2."""
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
        """Populate OES Transitional fields. OES width tracks the OFS inner edge."""
        try:
            d = get_new_ols_transitional_defaults()
            self.set_numeric_value('spin_slope_oes', d['slope_pct'])
            inner_edge_widget = getattr(self, 'spin_innerEdge_ofs', None)
            if inner_edge_widget and hasattr(inner_edge_widget, 'text'):
                try:
                    inner_val = float(inner_edge_widget.text() or "155")
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
        """Validate that required layers are selected with correct geometry types."""
        try:
            if not self._validate_project_crs():
                return False

            runway_layer = self.runwayLayerCombo.currentLayer()
            threshold_layer = self.thresholdLayerCombo.currentLayer()

            if not runway_layer:
                self.show_error_message(
                    "No Runway Layer Centerline Selected!\n\n"
                    "Please select a Runway Layer Centerline from the dropdown.\n"
                    "The layer must contain LINE geometry (runway lines)."
                )
                return False

            if not threshold_layer:
                self.show_error_message(
                    "No Threshold Layer Selected!\n\n"
                    "Please select a threshold layer from the dropdown.\n"
                    "The layer must contain POINT geometry (threshold points)."
                )
                return False

            if not isinstance(runway_layer, QgsVectorLayer):
                self.show_error_message(
                    f"Invalid Runway Layer Centerline Object!\n\n"
                    f"Selected object is not a valid vector layer: {type(runway_layer)}"
                )
                return False

            if not isinstance(threshold_layer, QgsVectorLayer):
                self.show_error_message(
                    f"Invalid Threshold Layer Object!\n\n"
                    f"Selected object is not a valid vector layer: {type(threshold_layer)}"
                )
                return False

            project_layers = list(QgsProject.instance().mapLayers().values())
            if runway_layer not in project_layers:
                self.show_error_message(
                    f"Runway Layer Centerline Not Found!\n\n"
                    f"Layer '{runway_layer.name()}' is no longer in the project."
                )
                return False

            if threshold_layer not in project_layers:
                self.show_error_message(
                    f"Threshold Layer Not Found!\n\n"
                    f"Layer '{threshold_layer.name()}' is no longer in the project."
                )
                return False

            if not runway_layer.isValid():
                self.show_error_message(
                    f"Corrupted Runway Layer Centerline!\n\n"
                    f"Layer '{runway_layer.name()}' is invalid or corrupted."
                )
                return False

            if not threshold_layer.isValid():
                self.show_error_message(
                    f"Corrupted Threshold Layer!\n\n"
                    f"Layer '{threshold_layer.name()}' is invalid or corrupted."
                )
                return False

            if runway_layer.geometryType() != QgsWkbTypes.LineGeometry:
                self.show_error_message(
                    f"Wrong Geometry Type for Runway!\n\n"
                    f"Layer: '{runway_layer.name()}'\n"
                    f"Current geometry: {self.get_layer_geometry_info(runway_layer)}\n"
                    f"Required geometry: LINE (runway lines)"
                )
                return False

            if threshold_layer.geometryType() != QgsWkbTypes.PointGeometry:
                self.show_error_message(
                    f"Wrong Geometry Type for Threshold!\n\n"
                    f"Layer: '{threshold_layer.name()}'\n"
                    f"Current geometry: {self.get_layer_geometry_info(threshold_layer)}\n"
                    f"Required geometry: POINT (threshold points)"
                )
                return False

            if runway_layer.featureCount() == 0:
                self.show_error_message(
                    f"Empty Runway Layer Centerline!\n\n"
                    f"Layer '{runway_layer.name()}' contains no features."
                )
                return False

            if threshold_layer.featureCount() == 0:
                self.show_error_message(
                    f"Empty Threshold Layer!\n\n"
                    f"Layer '{threshold_layer.name()}' contains no features."
                )
                return False

            if self.useSelectedRunwayCheckBox.isChecked():
                if len(runway_layer.selectedFeatures()) == 0:
                    self.show_error_message(
                        "No Runway Features Selected!\n\n"
                        "'Use Selected Runway Features' is checked but no features are selected."
                    )
                    return False

            if self.useSelectedThresholdCheckBox.isChecked():
                if len(threshold_layer.selectedFeatures()) == 0:
                    self.show_error_message(
                        "No Threshold Features Selected!\n\n"
                        "'Use Selected Threshold Features' is checked but no features are selected."
                    )
                    return False

            return True

        except Exception as e:
            logger.error(f"validate_layers unexpected error: {e}\n{traceback.format_exc()}")
            self.show_error_message(
                f"Critical Validation Error!\n\n"
                f"An unexpected error occurred during validation:\n{str(e)}"
            )
            return False

    @pyqtSlot()
    def on_calculate_clicked(self):
        try:
            if not self.validate_layers():
                return
            self.show_info_message("Starting calculation...")
            self.calculateClicked.emit()
        except Exception as e:
            self.show_error_message(f"Error starting calculation: {str(e)}")

    @pyqtSlot()
    def on_close_clicked(self):
        try:
            self.closeClicked.emit()
        except Exception as e:
            logger.warning(f"Unhandled error: {e}")

    def get_parameters(self):
        """Collect and return all UI parameters for the currently active OFS/OES tab."""
        try:
            runway_layer = self.runwayLayerCombo.currentLayer()
            threshold_layer = self.thresholdLayerCombo.currentLayer()
            use_runway_selected = self.useSelectedRunwayCheckBox.isChecked()
            use_threshold_selected = self.useSelectedThresholdCheckBox.isChecked()
            direction = 0 if self.direction_start_to_end else -1

            ofs_oes_index = self.newOlsTabWidget.currentIndex()
            if ofs_oes_index == 0:
                surface_type = SurfaceType.NEW_OLS_OFS_APPROACH
                s_value = direction
                z0_ui = self.get_numeric_value('spin_Z0_ofs')
                ze_ui = self.get_numeric_value('spin_ZE_ofs')
                z0_calc, ze_calc = (z0_ui, ze_ui) if s_value == 0 else (ze_ui, z0_ui)
                specific_params = {
                    'rwy_type': self.combo_rwyType_ofs.currentText(),
                    'adg': self.combo_adg_ofs.currentText(),
                    'runway_width_m': self.get_numeric_value('spin_rwyWidth_ofs'),
                    'distance_from_threshold_m': self.get_numeric_value('spin_distThr_ofs'),
                    'inner_edge_m': self.get_numeric_value('spin_innerEdge_ofs'),
                    'divergence_ratio': self.get_numeric_value('spin_divergence_ofs') / 100.0,
                    'length_m': self.get_numeric_value('spin_length_ofs'),
                    'slope_pct': self.get_numeric_value('spin_slope_ofs'),
                    'start_elevation_m': z0_calc,
                    'end_elevation_m': ze_calc,
                    'arp_elevation_m': self.get_numeric_value('spin_ARPH_ofs'),
                    'direction': s_value,
                    'contour_interval_m': int(round(self.get_numeric_value('spin_contour_interval_ofs'))),
                }
            else:
                surface_type = SurfaceType.NEW_OLS_OES_TRANSITIONAL
                s_value = direction
                specific_params = {
                    'width_m': self.get_numeric_value('spin_widthApp_oes'),
                    'start_elevation_m': self.get_numeric_value('spin_Z0_oes'),
                    'highest_thr_elev_m': self.get_numeric_value('spin_ARPH_oes'),
                    'slope_pct': self.get_numeric_value('spin_slope_oes'),
                    'cap_height_m': 60.0,
                    'approach_slope_pct': self.get_numeric_value('spin_slope_ofs'),
                    'divergence_ratio': self.get_numeric_value('spin_divergence_ofs') / 100.0,
                    'distance_from_threshold_m': self.get_numeric_value('spin_distThr_ofs'),
                    'direction': s_value,
                }

            return {
                'surface_type': surface_type,
                'runway_layer': runway_layer,
                'threshold_layer': threshold_layer,
                'use_runway_selected': use_runway_selected,
                'use_threshold_selected': use_threshold_selected,
                'direction': direction,
                'specific_params': specific_params,
            }

        except Exception as e:
            self.show_error_message(f"Error collecting parameters: {str(e)}")
            return None

    def toggle_direction(self):
        self.direction_start_to_end = not self.direction_start_to_end
        self.update_direction_button()

    def update_direction_button(self):
        if self.direction_start_to_end:
            self.directionButton.setText("Direction: Start to End")
        else:
            self.directionButton.setText("Direction: End to Start")

    @pyqtSlot()
    def update_selection_info(self):
        try:
            runway_layer = self.runwayLayerCombo.currentLayer()
            threshold_layer = self.thresholdLayerCombo.currentLayer()
            use_runway_selected = self.useSelectedRunwayCheckBox.isChecked()
            use_threshold_selected = self.useSelectedThresholdCheckBox.isChecked()

            if runway_layer:
                runway_selected = len(runway_layer.selectedFeatures())
                runway_total = runway_layer.featureCount()
                if use_runway_selected:
                    runway_status = f"Selected ({runway_selected})" if runway_selected > 0 else "No selection"
                else:
                    runway_status = f"All ({runway_total})"
            else:
                runway_status = "No layer"

            if threshold_layer:
                threshold_selected = len(threshold_layer.selectedFeatures())
                threshold_total = threshold_layer.featureCount()
                if use_threshold_selected:
                    threshold_status = f"Selected ({threshold_selected})" if threshold_selected > 0 else "No selection"
                else:
                    threshold_status = f"All ({threshold_total})"
            else:
                threshold_status = "No layer"

            _is_dark = QApplication.palette().window().color().lightness() < 128
            _c_warn = "#FFA726" if _is_dark else "#E65100"
            _c_ok = "#66BB6A" if _is_dark else "#2E7D32"
            _c_err = "#EF5350" if _is_dark else "#C62828"
            _base_style = "font-weight: bold; font-size: 11px;"

            if "All" in runway_status:
                runway_icon, runway_style = "⚠", f"QLabel {{ color: {_c_warn}; {_base_style} }}"
            elif "Selected" in runway_status:
                runway_icon, runway_style = "✔", f"QLabel {{ color: {_c_ok}; {_base_style} }}"
            else:
                runway_icon, runway_style = "✘", f"QLabel {{ color: {_c_err}; {_base_style} }}"

            if "All" in threshold_status:
                threshold_icon, threshold_style = "⚠", f"QLabel {{ color: {_c_warn}; {_base_style} }}"
            elif "Selected" in threshold_status:
                threshold_icon, threshold_style = "✔", f"QLabel {{ color: {_c_ok}; {_base_style} }}"
            else:
                threshold_icon, threshold_style = "✘", f"QLabel {{ color: {_c_err}; {_base_style} }}"

            try:
                self.runwaySelectionStatusLabel.setText(f"{runway_icon} {runway_status}")
                self.runwaySelectionStatusLabel.setStyleSheet(runway_style)
                self.thresholdSelectionStatusLabel.setText(f"{threshold_icon} {threshold_status}")
                self.thresholdSelectionStatusLabel.setStyleSheet(threshold_style)
            except Exception as e:
                logger.warning(f"Unhandled error: {e}")

            self.update_dropdown_item_tooltips()

        except Exception as e:
            logger.error(f"update_selection_info failed: {e}\n{traceback.format_exc()}")
            try:
                self.runwaySelectionStatusLabel.setText("❌ Error")
                self.thresholdSelectionStatusLabel.setText("❌ Error")
            except (AttributeError, RuntimeError):
                pass

    def validate_layer_change(self):
        try:
            runway_layer = self.runwayLayerCombo.currentLayer()
            threshold_layer = self.thresholdLayerCombo.currentLayer()
            if runway_layer and runway_layer.geometryType() != QgsWkbTypes.LineGeometry:
                self.show_error_message(
                    f"Invalid Runway Layer Centerline!\n"
                    f"'{runway_layer.name()}' contains {self.get_layer_geometry_info(runway_layer)} geometry.\n"
                    f"Runway Layer Centerline must contain LINE geometry."
                )
                self.runwayLayerCombo.setLayer(None)
                return
            if threshold_layer and threshold_layer.geometryType() != QgsWkbTypes.PointGeometry:
                self.show_error_message(
                    f"Invalid Threshold Layer!\n"
                    f"'{threshold_layer.name()}' contains {self.get_layer_geometry_info(threshold_layer)} geometry.\n"
                    f"Threshold layer must contain POINT geometry."
                )
                self.thresholdLayerCombo.setLayer(None)
                return
            self.update_selection_info()
        except Exception as e:
            logger.warning(f"Unhandled error: {e}")

    @pyqtSlot()
    def connect_layer_selection_signals(self):
        self.disconnect_layer_selection_signals()
        try:
            runway_layer = self.runwayLayerCombo.currentLayer()
            threshold_layer = self.thresholdLayerCombo.currentLayer()
            if runway_layer and isinstance(runway_layer, QgsVectorLayer):
                self._runway_selection_slot = lambda *_: self.update_selection_info()
                runway_layer.selectionChanged.connect(self._runway_selection_slot)
                self.connected_runway_layer = runway_layer
            else:
                self._runway_selection_slot = None
            if threshold_layer and isinstance(threshold_layer, QgsVectorLayer):
                self._threshold_selection_slot = lambda *_: self.update_selection_info()
                threshold_layer.selectionChanged.connect(self._threshold_selection_slot)
                self.connected_threshold_layer = threshold_layer
            else:
                self._threshold_selection_slot = None
        except Exception as e:
            logger.warning(f"Unhandled error: {e}")

    def disconnect_layer_selection_signals(self):
        try:
            if self.connected_runway_layer and self._runway_selection_slot:
                try:
                    self.connected_runway_layer.selectionChanged.disconnect(self._runway_selection_slot)
                except RuntimeError:
                    pass
                self.connected_runway_layer = None
                self._runway_selection_slot = None
            if self.connected_threshold_layer and self._threshold_selection_slot:
                try:
                    self.connected_threshold_layer.selectionChanged.disconnect(self._threshold_selection_slot)
                except RuntimeError:
                    pass
                self.connected_threshold_layer = None
                self._threshold_selection_slot = None
        except Exception as e:
            logger.warning(f"Unhandled error: {e}")

    def show_info_message(self, message):
        self.iface.messageBar().pushMessage("New OLS Info", message, level=MSG_INFO, duration=3)

    def show_error_message(self, message):
        self.iface.messageBar().pushMessage("New OLS Error", message, level=MSG_CRITICAL, duration=5)

    def _connect(self, signal, slot):
        signal.connect(slot)
        self._connections.append((signal, slot))

    def closeEvent(self, event):
        try:
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
