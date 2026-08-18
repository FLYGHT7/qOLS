"""qols/kml_export/dialog.py — KML export UI (#153).

Replaces ols_2_kml_v8.py's ``get_global_options_dialog`` (a function
returning a large tuple, with manual per-call PyQt5/PyQt6 enum shims) with
a proper ``QDialog`` subclass using ``qols/compat.py`` constants, matching
the pattern of the existing ``RulesSettingsDialog``
(``qols/ui/settings_dialog.py``) — a plain modal dialog, no dockwidget
``_connect()`` teardown needed since nothing outlives ``exec()``.
"""
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ..compat import BTN_CANCEL, BTN_OK, BTN_ROLE_ACTION
from .exporter import AUTOMATIC_FIELD_OPTION, get_last_output_dir

__all__ = ["KmlExportOptionsDialog", "resolve_output_conflict"]


class KmlExportOptionsDialog(QDialog):
    """Prompts once for all KML export options: output folder, label field,
    subfolder grouping, HTML popup theme, and densification interval."""

    def __init__(self, layer_count: int, field_names, parent=None):
        super().__init__(parent)
        plural = 's' if layer_count != 1 else ''
        self.setWindowTitle(f"Batch KML Options ({layer_count} Selected Layer{plural})")
        self.setModal(True)

        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Output Folder:"))
        dir_layout = QHBoxLayout()
        self._line_dir = QLineEdit(get_last_output_dir())
        btn_browse = QPushButton("Browse...")
        btn_browse.clicked.connect(self._select_folder)
        dir_layout.addWidget(self._line_dir)
        dir_layout.addWidget(btn_browse)
        layout.addLayout(dir_layout)

        layout.addWidget(QLabel("Label Field (Google Earth Layer Tree):"))
        self._combo_field = QComboBox()
        self._combo_field.addItems([AUTOMATIC_FIELD_OPTION] + list(field_names))
        layout.addWidget(self._combo_field)

        self._chk_group = QCheckBox("Group features into subfolders based on label field value")
        self._chk_group.setToolTip(
            "Creates a KML folder for each unique label value and groups "
            "corresponding individual features inside it.")
        layout.addWidget(self._chk_group)

        layout.addWidget(QLabel("HTML Popup Theme:"))
        self._combo_theme = QComboBox()
        self._combo_theme.addItems(["Dark", "Light"])
        layout.addWidget(self._combo_theme)

        layout.addWidget(QLabel("Densification Interval (meters):"))
        self._spin_densify = QDoubleSpinBox()
        self._spin_densify.setRange(0.1, 100000.0)
        self._spin_densify.setValue(50.0)
        self._spin_densify.setDecimals(1)
        self._spin_densify.setSuffix(" m")
        layout.addWidget(self._spin_densify)

        buttons = QDialogButtonBox(BTN_OK | BTN_CANCEL)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _select_folder(self):
        chosen = QFileDialog.getExistingDirectory(self, "Select Output Directory", self._line_dir.text())
        if chosen:
            self._line_dir.setText(chosen)

    def output_dir(self) -> str:
        return self._line_dir.text().strip() or get_last_output_dir()

    def label_field(self) -> str:
        return self._combo_field.currentText()

    def group_by_label(self) -> bool:
        return self._chk_group.isChecked()

    def theme(self) -> str:
        return self._combo_theme.currentText()

    def densify_interval(self) -> float:
        return self._spin_densify.value()


def resolve_output_conflict(parent, existing_path: str):
    """Prompts Overwrite / Choose New Name / Skip Layer for an existing output file.

    Returns ``("overwrite", None)``, ``("rename", new_path)``, or
    ``("skip", None)``. Buttons are compared by object identity rather than
    by ``StandardButton``/``ButtonRole`` value, avoiding any PyQt5/PyQt6
    enum-shim ambiguity.
    """
    msg_box = QMessageBox(parent)
    msg_box.setWindowTitle("File Exists")
    msg_box.setText(f"Output file exists:\n{existing_path}\n\nWhat would you like to do?")
    # "Overwrite" needs no button reference: anything that isn't Rename/Skip
    # (including Overwrite itself, or the box being dismissed) falls through below.
    msg_box.addButton("Overwrite", BTN_ROLE_ACTION)
    btn_rename = msg_box.addButton("Choose New Name", BTN_ROLE_ACTION)
    btn_skip = msg_box.addButton("Skip Layer", BTN_ROLE_ACTION)
    msg_box.exec()
    clicked = msg_box.clickedButton()

    if clicked is btn_skip:
        return "skip", None
    if clicked is btn_rename:
        new_path, _ = QFileDialog.getSaveFileName(
            parent, "Select Output Path", existing_path, "KML Files (*.kml)")
        return ("rename", new_path) if new_path else ("skip", None)
    return "overwrite", None
