"""New OLS concept dock widget — minimal stub for issue #113.

Provides :class:`NewOlsDockWidget` with the OFS/OES defaults methods used in tests
and referenced by existing signal connections.  Full dock-widget UI (toolbar button,
separate panel) is deferred to issue #111.
"""
from qgis.PyQt.QtCore import pyqtSlot
from ..surfaces.new_ols_approach import get_new_ols_approach_defaults
from .. import logger


class NewOlsDockWidget:
    """New OLS concept dock widget (OFS Approach + OES placeholder)."""

    def get_numeric_value(self, widget_name):
        """Return float value from a QLineEdit widget, or 0.0 if missing/invalid."""
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
        """Set numeric value in a QLineEdit or QDoubleSpinBox widget."""
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
        """Populate OFS Approach fields from ICAO Tables 4-1/4-2 (New OLS #108)."""
        try:
            rwy_type = self.combo_rwyType_ofs.currentText()
            adg = self.combo_adg_ofs.currentText()
            runway_width_m = self.get_numeric_value('spin_rwyWidth_ofs')
            d = get_new_ols_approach_defaults(rwy_type, adg, runway_width_m)
            self.set_numeric_value('spin_distThr_ofs',    d['distance_from_threshold_m'])
            self.set_numeric_value('spin_innerEdge_ofs',  d['inner_edge_m'])
            self.set_numeric_value('spin_divergence_ofs', d['divergence_pct'])
            self.set_numeric_value('spin_length_ofs',     d['length_m'])
            self.set_numeric_value('spin_slope_ofs',      d['slope_pct'])
        except Exception as e:
            logger.warning(f"Unhandled error: {e}")

    @pyqtSlot()
    def apply_oes_transitional_defaults(self):
        """OES is TO BE DEVELOPED — no defaults to populate."""
        pass
