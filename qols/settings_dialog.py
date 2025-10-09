import os
from qgis.PyQt import QtWidgets, QtCore
from qgis.PyQt.QtCore import Qt, QUrl
from qgis.PyQt.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QComboBox, QPushButton, QDialogButtonBox
from qgis.PyQt.QtGui import QDesktopServices

from . import rules_manager as rule_mgr


class RulesSettingsDialog(QDialog):
    """Simple settings dialog to manage the active Rule Set.

    Provides:
    - Active Rule Set selector (persisted via QSettings)
    - Reload rule files button
    - Open rules folder button
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("QOLS Settings")
        self.setModal(True)
        self._rules_dir = os.path.join(os.path.dirname(__file__), 'rules')

        self._build_ui()
        self._load_rule_sets()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        # Active Rule Set selector
        row = QHBoxLayout()
        row.addWidget(QLabel("Active Rule Set:"))
        self.combo = QComboBox()
        self.combo.setMinimumWidth(260)
        row.addWidget(self.combo, 1)
        layout.addLayout(row)

        # Utility buttons
        util_row = QHBoxLayout()
        self.btn_reload = QPushButton("Reload Rule Files")
        self.btn_reload.clicked.connect(self._on_reload)
        util_row.addWidget(self.btn_reload)

        self.btn_open_folder = QPushButton("Open Rules Folder")
        self.btn_open_folder.clicked.connect(self._on_open_folder)
        util_row.addWidget(self.btn_open_folder)

        util_row.addStretch(1)
        layout.addLayout(util_row)

        # Dialog buttons
        self.buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.setLayout(layout)

    def _load_rule_sets(self):
        # Populate combo from rules
        registry = rule_mgr.list_rule_sets()
        names = sorted(list(registry.keys()))
        self.combo.clear()
        self.combo.addItems(names)
        # Select current active if available
        active = rule_mgr.get_active_rule_set_name()
        if active and active in names:
            self.combo.setCurrentText(active)
        elif names:
            # If nothing active, select first for display
            self.combo.setCurrentIndex(0)

    def _on_reload(self):
        rule_mgr.reload_rules()
        self._load_rule_sets()

    def _on_open_folder(self):
        try:
            if os.name == 'nt' and hasattr(os, 'startfile'):
                os.startfile(self._rules_dir)  # type: ignore[attr-defined]
            else:
                QDesktopServices.openUrl(QUrl.fromLocalFile(self._rules_dir))
        except Exception:
            pass

    def selected_rule_set(self):
        return self.combo.currentText().strip() if self.combo.currentText() else None
