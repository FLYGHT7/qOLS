# -*- coding: utf-8 -*-
"""
qols/parameters_inspector.py — store/inspect a surface's input parameters (#118).

Extends what qpansopy already ships (`Q_Pansopy/parameters_inspector_dialog.py`
+ `Q_Pansopy/utils.py`): every surface-generation script stores the full set
of inputs that produced a feature as a JSON string in a `parameters` field,
and registers a QGIS layer action ("view parameters as HTML Table") so a
user can right-click a feature — in the attribute table or a canvas
Identify Features result — and see a themeable HTML table of exactly what
produced it, without redoing the calculation. Renders via QWebEngineView
when available, falling back to a QTextBrowser popup otherwise (QtWebEngine
is an optional, heavy Qt add-on not bundled with every QGIS install).

Two helpers not present in qpansopy (which leaves this per-script) centralize
what every qOLS script needs:
    build_parameters_json('Approach Surface', {...})   -> JSON string
    add_parameters_field(layer)                        -> idempotent QgsField add

Usage inside a surface-generation script (exec()-dispatched, but this is a
normal importable module — absolute imports resolve independently of the
exec() globals dict):
    from qols.parameters_inspector import (
        build_parameters_json, add_parameters_field, register_parameters_action,
    )
    params_json = build_parameters_json('Approach Surface', {...})
    add_parameters_field(v_layer)
    # ...set feature.setAttributes([..., params_json]) for every feature...
    register_parameters_action(v_layer)
    QgsProject.instance().addMapLayers([v_layer])
"""
from __future__ import annotations

import datetime
import html
import json
import re

from qgis.core import QgsAction, QgsField, QgsProject, QgsVectorLayer
from qgis.PyQt.QtCore import QMimeData, QObject, QVariant, pyqtSlot
from qgis.PyQt.QtWidgets import (
    QApplication, QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QTextBrowser, QVBoxLayout,
)

from .compat import ACTION_TYPE_GENERIC_PYTHON

# QtWebEngineWidgets/QtWebChannel are optional, heavy Qt components (bundled
# separately from base PyQt -- e.g. `python-pyqt6-webengine` on Arch/CachyOS)
# that aren't guaranteed to be installed alongside QGIS. Fall back to a
# QTextBrowser-based popup (no live JS theme toggle, but still dark by
# default) rather than crashing every "view parameters as HTML Table" action
# for users who lack them.
try:
    from qgis.PyQt.QtWebChannel import QWebChannel
    from qgis.PyQt.QtWebEngineWidgets import QWebEngineView
    _WEBENGINE_AVAILABLE = True
except ImportError:
    QWebChannel = None
    QWebEngineView = None
    _WEBENGINE_AVAILABLE = False

__all__ = [
    "build_parameters_json",
    "add_parameters_field",
    "register_parameters_action",
    "show_parameters_inspector",
    "show_web_popup",
    "resolve_inspector_title",
    "format_parameters_table",
    "collect_project_parameter_sections",
    "show_project_parameters_table",
]


# ---------------------------------------------------------------------------
# Storing parameters on a layer/feature
# ---------------------------------------------------------------------------

def build_parameters_json(calculation_type: str, params: dict) -> str:
    """Build the JSON string stored in every feature's 'parameters' field.

    Merges *calculation_type* and a 'generated_at' ISO timestamp into
    *params* so every stored blob is self-describing (used by
    resolve_inspector_title() to pick a popup title, and useful when
    reviewing a project long after the surface was calculated).
    """
    payload = dict(params)
    payload['calculation_type'] = calculation_type
    payload['generated_at'] = datetime.datetime.now().isoformat(timespec='seconds')
    return json.dumps(payload)


def add_parameters_field(layer) -> None:
    """Add a 'parameters' (String) field to *layer* if it doesn't already
    have one. Idempotent — safe to call from scripts that build a layer's
    fields incrementally or in a loop."""
    if layer.fields().indexOf('parameters') != -1:
        return
    layer.dataProvider().addAttributes([QgsField('parameters', QVariant.String)])
    layer.updateFields()


# ---------------------------------------------------------------------------
# "Copy to Word" plain-text/HTML table (ported from qpansopy's utils.py)
# ---------------------------------------------------------------------------

_PARAM_LABEL_ACRONYMS = {
    'IAS', 'ISA', 'PDG', 'TNA', 'MSA', 'CWY', 'DER', 'THR', 'OAS', 'FAP',
    'MOC', 'VPA', 'OCH', 'RDH', 'ILS', 'KML', 'CRS', 'W', 'ARPH', 'ADG',
}

_PARAM_LABEL_OVERRIDES: dict = {}


def _humanize_param_label(key):
    """Turn a raw parameters-dict key (snake_case or camelCase, sometimes
    with aviation acronyms) into a readable label, e.g. 'widthApp' ->
    'Width App', 'ARPH' -> 'ARPH', 'rule_set' -> 'Rule Set'."""
    override = _PARAM_LABEL_OVERRIDES.get(key)
    if override:
        return override

    spaced = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', str(key)).replace('_', ' ')
    words = []
    for word in spaced.split():
        words.append(word.upper() if word.upper() in _PARAM_LABEL_ACRONYMS else word.capitalize())
    return ' '.join(words)


def format_parameters_table(title, params_dict, as_html=False):
    """Format a flat parameters dict as a standalone table — plain text by
    default, an HTML `<table>` (Word-pasteable) when as_html=True."""
    entries = [(key, value) for key, value in params_dict.items()]

    if as_html:
        parts = [
            '<table border="1" cellpadding="4" cellspacing="0"'
            ' style="border-collapse: collapse; font-family: Calibri, Arial, sans-serif; font-size: 11pt;">',
            f'<tr style="background-color:#000000;color:#FFFFFF;font-weight:bold;text-align:center;">'
            f'<th colspan="2">{html.escape(str(title))}</th></tr>',
            '<tr style="background-color:#FFFFFF;font-weight:bold;">'
            '<td>Parameter</td><td>Value</td></tr>',
        ]
        for key, value in entries:
            parts.append(
                '<tr style="background-color:#FFFFFF;">'
                f'<td>{html.escape(_humanize_param_label(key))}</td>'
                f'<td style="text-align:right;">{html.escape(str(value))}</td></tr>'
            )
        parts.append('</table>')
        return ''.join(parts)

    table = f"{title}\n{'=' * 50}\n\n"
    table += "PARAMETER                    VALUE\n"
    table += "-" * 50 + "\n"
    for key, value in entries:
        table += f"{_humanize_param_label(key):<28} {value}\n"
    return table


# ---------------------------------------------------------------------------
# HTML popup page (ported from qpansopy's parameters_inspector_dialog.py)
# ---------------------------------------------------------------------------

# Reached from a QGIS layer action, which is triggered per-click rather than
# tracked by any caller -- keep open QWebEngineView popups alive here (keyed
# by id(view)), otherwise PyQt garbage-collects them the moment
# show_parameters_inspector()/show_web_popup() returns.
_open_views: dict = {}

_PAGE_TEMPLATE = """<html>
<head>
<style>
    html, body {
        font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
        margin: 0; padding: 0; height: 100vh;
        overflow-x: hidden; overflow-y: auto; box-sizing: border-box;
        transition: background-color 0.2s, color 0.2s;
    }
    ::-webkit-scrollbar { width: 14px; background-color: rgba(0, 0, 0, 0.05); }
    ::-webkit-scrollbar-track { background-color: rgba(0, 0, 0, 0.1); border-radius: 4px; }
    .light-theme ::-webkit-scrollbar-thumb { background-color: #64748b; border: 2px solid #f4f6f9; border-radius: 6px; }
    .dark-theme ::-webkit-scrollbar-thumb { background-color: #38bdf8; border: 2px solid #0f172a; border-radius: 6px; }
    ::-webkit-scrollbar-thumb:hover { background-color: #0076a3 !important; }
    .dark-theme ::-webkit-scrollbar-thumb:hover { background-color: #f8fafc !important; }

    body.light-theme { background-color: #f4f6f9; color: #333333; }
    .light-theme .layer-title { color: #1e293b; }
    .light-theme h3 { color: #1e293b; border-bottom: 2px solid #e2e8f0; }
    .light-theme .section-title { color: #475569; }
    .light-theme .table-card { background: #ffffff; border: 1px solid #e2e8f0; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); }
    .light-theme th { background-color: #0f172a; color: #ffffff; border-bottom: 2px solid #1e293b; }
    .light-theme td { border-bottom: 1px solid #f1f5f9; color: #475569; }
    .light-theme tr:nth-child(even) td { background-color: #f8fafc; }
    .light-theme tr:hover td { background-color: #f1f5f9; color: #0f172a; }
    .light-theme td b { color: #1e293b; }
    .light-theme .word-btn { background-color: #ffffff; border: 1px solid #cbd5e1; color: #1e293b; }
    .light-theme .word-btn:hover { background-color: #f1f5f9; }

    body.dark-theme { background-color: #0f172a; color: #cbd5e1; }
    .dark-theme .layer-title { color: #f8fafc; }
    .dark-theme h3 { color: #f8fafc; border-bottom: 2px solid #1e293b; }
    .dark-theme .section-title { color: #94a3b8; }
    .dark-theme .table-card { background: #1e293b; border: 1px solid #334155; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.3); }
    .dark-theme th { background-color: #020617; color: #38bdf8; border-bottom: 2px solid #334155; }
    .dark-theme td { border-bottom: 1px solid #334155; color: #94a3b8; }
    .dark-theme tr:nth-child(even) td { background-color: #1e293b; }
    .dark-theme tr:nth-child(odd) td { background-color: #111827; }
    .dark-theme tr:hover td { background-color: #334155; color: #f8fafc; }
    .dark-theme td b { color: #f1f5f9; }
    .dark-theme .word-btn { background-color: #1e293b; border: 1px solid #475569; color: #f8fafc; }
    .dark-theme .word-btn:hover { background-color: #334155; }

    #main-container { padding: 24px; display: flex; flex-direction: column; position: relative; }
    .layer-title { font-size: 20px; font-weight: 600; margin-bottom: 2px; padding-right: 180px; }
    h3 { margin: 0 0 16px 0; font-size: 20px; font-weight: 600; padding-bottom: 8px; }
    .section-title { margin: 20px 0 8px 0; font-size: 13px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }
    .table-card { border-radius: 8px; overflow: hidden; transition: background 0.2s, border 0.2s; }
    table { width: 100%; border-collapse: collapse; text-align: left; }
    th, td { padding: 14px 18px; font-size: 14px; line-height: 1.5; word-break: break-all; }
    th { font-weight: 600; text-transform: uppercase; font-size: 12px; letter-spacing: 0.05em; width: 35%; }
    td b { font-weight: 500; }
    .controls-wrapper { position: absolute; top: 22px; right: 24px; display: flex; align-items: center; gap: 16px; }
    .word-btn { padding: 4px 10px; font-size: 12px; font-weight: 500; border-radius: 4px; cursor: pointer; display: flex; align-items: center; gap: 6px; transition: background-color 0.2s; }
    .theme-switch-wrapper { display: flex; align-items: center; gap: 8px; font-size: 12px; font-weight: 500; }
    .theme-switch { display: inline-block; height: 20px; position: relative; width: 36px; }
    .theme-switch input { display:none; }
    .slider { background-color: #cbd5e1; bottom: 0; cursor: pointer; left: 0; position: absolute; right: 0; top: 0; transition: .2s; border-radius: 20px; }
    .slider:before { background-color: white; bottom: 3px; content: ""; height: 14px; left: 3px; position: absolute; transition: .2s; width: 14px; border-radius: 50%; }
    input:checked + .slider { background-color: #38bdf8; }
    input:checked + .slider:before { transform: translateX(16px); }
</style>
<!-- Include the internal Qt WebChannel Script framework to link JS with Python Backend -->
<script src="qrc:///qtwebchannel/qwebchannel.js"></script>
</head>
<body class="dark-theme">
    <div id="main-container">
        <div class="layer-title">__QOLS_TITLE__</div>
        <h3>Feature Parameters</h3>

        <div class="controls-wrapper">
            <button class="word-btn" onclick="triggerNativeCopy()">Copy to Word</button>
            <div class="theme-switch-wrapper">
                <span id="theme-label">Dark Mode</span>
                <label class="theme-switch" for="checkbox">
                    <input type="checkbox" id="checkbox" checked />
                    <div class="slider"></div>
                </label>
            </div>
        </div>

__QOLS_SECTIONS__
    </div>

    <script>
        let backendBridge;
        // Establish runtime links with the PyQt backend bridge container channels
        new QWebChannel(qt.webChannelTransport, function (channel) {
            backendBridge = channel.objects.pyBridge;
        });

        const toggleSwitch = document.querySelector('#checkbox');
        const themeLabel = document.querySelector('#theme-label');

        toggleSwitch.addEventListener('change', (e) => {
            if (e.target.checked) {
                document.body.className = 'dark-theme';
                themeLabel.textContent = 'Dark Mode';
            } else {
                document.body.className = 'light-theme';
                themeLabel.textContent = 'Light Mode';
            }
        }, false);

        function triggerNativeCopy() {
            if (backendBridge) {
                backendBridge.copyToClipboard();
                const btn = document.querySelector('.word-btn');
                const originalText = btn.innerHTML;
                btn.innerHTML = '✔ Copied!';
                setTimeout(() => { btn.innerHTML = originalText; }, 1500);
            }
        }
    </script>
</body>
</html>
"""


def _format_value(value):
    return json.dumps(value) if isinstance(value, (dict, list)) else str(value)


def _build_rows_html(flat_params):
    rows = []
    for key, value in flat_params.items():
        rows.append(
            f"<tr><td><b>{html.escape(str(key))}</b></td>"
            f"<td>{html.escape(_format_value(value))}</td></tr>"
        )
    return "".join(rows)


def _build_section_html(section_title, flat_params, show_heading):
    heading = f'<h4 class="section-title">{html.escape(section_title)}</h4>' if show_heading else ''
    rows = _build_rows_html(flat_params)
    return (
        f'{heading}<div class="table-card"><table>'
        f'<tr><th>Parameter</th><th>Value</th></tr>{rows}</table></div>'
    )


def _build_page_html(title, sections):
    """sections: list of (section_title, flat_params_dict) pairs. A single
    section renders with no sub-heading; multiple sections each get their
    own labelled table-card."""
    show_heading = len(sections) > 1
    sections_html = "".join(
        _build_section_html(section_title, flat_params, show_heading)
        for section_title, flat_params in sections
    )
    page = _PAGE_TEMPLATE.replace("__QOLS_TITLE__", html.escape(title))
    page = page.replace("__QOLS_SECTIONS__", sections_html)
    return page


class ClipboardBridge(QObject):
    """JS-callable bridge (via QWebChannel) that copies a clean, Word-pasteable
    HTML table to the native clipboard -- QWebEngineView content runs in a
    separate process/sandbox, so JS can't touch the OS clipboard directly."""

    def __init__(self, sections):
        super().__init__()
        self._sections = sections

    @pyqtSlot()
    def copyToClipboard(self):
        multi = len(self._sections) > 1
        html_parts = []
        text_parts = []
        for section_title, flat_params in self._sections:
            html_parts.append(format_parameters_table(section_title, flat_params, as_html=True))
            text_parts.append(format_parameters_table(section_title, flat_params, as_html=False))
        mime = QMimeData()
        mime.setHtml("<div>" + "<br>".join(html_parts) + "</div>" if multi else html_parts[0])
        mime.setText("\n\n".join(text_parts))
        QApplication.clipboard().setMimeData(mime)


def show_web_popup(title, sections):
    """Show a Parameters Inspector popup for one or more (section_title,
    flat_params_dict) pairs. Non-modal; kept alive in _open_views until the
    window is closed. Uses QWebEngineView when available (dark-mode-by-
    default with a live toggle), falling back to a QTextBrowser popup
    otherwise."""
    if _WEBENGINE_AVAILABLE:
        return _show_webengine_popup(title, sections)
    return _show_textbrowser_popup(title, sections)


def _show_webengine_popup(title, sections):
    page_html = _build_page_html(title, sections)

    view = QWebEngineView()
    bridge = ClipboardBridge(sections)
    channel = QWebChannel(view.page())
    view.page().setWebChannel(channel)
    channel.registerObject("pyBridge", bridge)

    view.setHtml(page_html)
    view.setWindowTitle(title)

    screen = view.screen().geometry()
    max_width = int(screen.width() / 3)
    max_height = int(screen.height() * 0.75)
    view.resize(max_width, max_height)

    def _fit_to_content(_ok=None):
        view.page().runJavaScript(
            "document.getElementById('main-container').offsetHeight",
            lambda rendered_height: view.resize(max_width, min(int(rendered_height) + 12, max_height))
        )

    view.loadFinished.connect(_fit_to_content)

    key = id(view)
    _open_views[key] = (view, bridge, channel)
    view.destroyed.connect(lambda: _open_views.pop(key, None))

    view.show()
    return view


# ---------------------------------------------------------------------------
# QTextBrowser fallback (no QtWebEngine available): a static render of the
# same data, dark-by-default. QTextBrowser can't run JavaScript, so the
# light/dark toggle and "Copy to Word" are plain QPushButtons instead of the
# JS/QWebChannel-driven controls in the WebEngine version.
# ---------------------------------------------------------------------------

_FALLBACK_PALETTES = {
    'dark': {
        'bg': '#0f172a', 'title_fg': '#f8fafc', 'h3_fg': '#f8fafc', 'h3_border': '#1e293b',
        'section_fg': '#94a3b8', 'card_border': '#334155',
        'th_bg': '#020617', 'th_fg': '#38bdf8',
        'row_even': '#1e293b', 'row_odd': '#111827', 'td_border': '#334155',
        'key_fg': '#f1f5f9', 'value_fg': '#94a3b8',
    },
    'light': {
        'bg': '#f4f6f9', 'title_fg': '#1e293b', 'h3_fg': '#1e293b', 'h3_border': '#e2e8f0',
        'section_fg': '#475569', 'card_border': '#e2e8f0',
        'th_bg': '#0f172a', 'th_fg': '#ffffff',
        'row_even': '#ffffff', 'row_odd': '#f8fafc', 'td_border': '#f1f5f9',
        'key_fg': '#1e293b', 'value_fg': '#475569',
    },
}


def _build_fallback_rows_html(flat_params, palette):
    rows = []
    for idx, (key, value) in enumerate(flat_params.items()):
        bg = palette['row_even'] if idx % 2 == 0 else palette['row_odd']
        rows.append(
            f'<tr>'
            f'<td style="background-color:{bg}; color:{palette["key_fg"]}; padding:10px; '
            f'border-bottom:1px solid {palette["td_border"]};"><b>{html.escape(str(key))}</b></td>'
            f'<td style="background-color:{bg}; color:{palette["value_fg"]}; padding:10px; '
            f'border-bottom:1px solid {palette["td_border"]};">{html.escape(_format_value(value))}</td></tr>'
        )
    return "".join(rows)


def _build_fallback_section_html(section_title, flat_params, show_heading, palette):
    heading = (
        f'<h4 style="color:{palette["section_fg"]}; text-transform:uppercase; font-size:12px; '
        f'letter-spacing:0.05em; margin:20px 0 8px 0;">{html.escape(section_title)}</h4>'
    ) if show_heading else ''
    rows = _build_fallback_rows_html(flat_params, palette)
    header_style = (
        f'background-color:{palette["th_bg"]}; color:{palette["th_fg"]}; padding:12px; text-align:left; '
        'text-transform:uppercase; font-size:12px;'
    )
    return (
        f'{heading}<table style="width:100%; border-collapse:collapse; '
        f'border:1px solid {palette["card_border"]}; border-radius:8px;">'
        f'<tr><th style="{header_style}">Parameter</th><th style="{header_style}">Value</th></tr>'
        f'{rows}</table>'
    )


def _build_fallback_page_html(title, sections, theme='dark'):
    palette = _FALLBACK_PALETTES[theme]
    show_heading = len(sections) > 1
    sections_html = "".join(
        _build_fallback_section_html(section_title, flat_params, show_heading, palette)
        for section_title, flat_params in sections
    )
    return (
        f'<body style="background-color:{palette["bg"]}; color:{palette["value_fg"]}; '
        'font-family:\'Segoe UI\',Arial,sans-serif; padding:4px;">'
        f'<h3 style="color:{palette["h3_fg"]}; border-bottom:2px solid {palette["h3_border"]}; '
        'padding-bottom:8px; margin-top:0;">Feature Parameters</h3>'
        f'{sections_html}</body>'
    )


class _FallbackParametersDialog(QDialog):
    """Static QTextBrowser popup used when QtWebEngine isn't installed.
    Ships its own native (non-JS) light/dark toggle button."""

    def __init__(self, title, sections, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(520, 360)
        self._sections = sections
        self._title = title
        self._theme = 'dark'

        layout = QVBoxLayout(self)

        header_row = QHBoxLayout()
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 16px; font-weight: 600; color: #f8fafc;")
        header_row.addWidget(title_label)
        header_row.addStretch()
        copy_btn = QPushButton("Copy to Word")
        copy_btn.clicked.connect(self._copy_to_word)
        header_row.addWidget(copy_btn)
        self._theme_btn = QPushButton()
        self._theme_btn.clicked.connect(self._toggle_theme)
        header_row.addWidget(self._theme_btn)
        layout.addLayout(header_row)

        self._browser = QTextBrowser(self)
        layout.addWidget(self._browser)

        button_row = QHBoxLayout()
        button_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.close)
        button_row.addWidget(close_btn)
        layout.addLayout(button_row)

        self._render()

    def _render(self):
        palette = _FALLBACK_PALETTES[self._theme]
        self._theme_btn.setText("🌙 Dark Mode" if self._theme == 'dark' else "☀ Light Mode")
        self._browser.setStyleSheet(
            f"QTextBrowser {{ background-color: {palette['bg']}; border: 1px solid {palette['card_border']}; }}"
        )
        self._browser.setHtml(_build_fallback_page_html(self._title, self._sections, self._theme))

    def _toggle_theme(self):
        self._theme = 'light' if self._theme == 'dark' else 'dark'
        self._render()

    def _copy_to_word(self):
        ClipboardBridge(self._sections).copyToClipboard()


def _show_textbrowser_popup(title, sections):
    dialog = _FallbackParametersDialog(title, sections)
    key = id(dialog)
    _open_views[key] = dialog
    dialog.finished.connect(lambda _result: _open_views.pop(key, None))
    dialog.show()
    return dialog


# ---------------------------------------------------------------------------
# QGIS layer action wiring
# ---------------------------------------------------------------------------

def resolve_inspector_title(parameters_dict, fallback):
    """Pick a readable popup title: the stored 'calculation_type' if
    present, else *fallback* (e.g. the layer name)."""
    calculation_type = parameters_dict.get('calculation_type') if isinstance(parameters_dict, dict) else None
    subject = calculation_type or fallback
    return f"{subject} — Feature Parameters"


def show_parameters_inspector(layer_id, feature_id):
    """Entry point for the QGIS layer action registered by
    register_parameters_action(). Resolves the feature's stored
    'parameters' JSON and shows it in a Parameters Inspector popup."""
    layer = QgsProject.instance().mapLayer(layer_id)
    if layer is None:
        QMessageBox.warning(None, "Parameters Inspector", "Could not find the source layer.")
        return

    feature = layer.getFeature(feature_id)
    if not feature.isValid():
        QMessageBox.warning(None, "Parameters Inspector", "Could not find the selected feature.")
        return

    raw = feature.attribute('parameters')
    if not raw:
        QMessageBox.information(None, "Parameters Inspector", "This feature has no stored parameters.")
        return

    try:
        parsed = json.loads(raw)
    except (TypeError, ValueError):
        QMessageBox.warning(None, "Parameters Inspector", "The stored parameters could not be parsed as JSON.")
        return

    title = resolve_inspector_title(parsed, layer.name())
    show_web_popup(title, [(layer.name(), parsed)])


def register_parameters_action(layer):
    """Register the 'view parameters as HTML Table' QGIS layer action on
    *layer*, so any feature with a 'parameters' attribute can be inspected
    as a rendered HTML table from the Attribute Table / canvas Identify
    results. Action scopes are set explicitly to Feature and Canvas --
    without this the action is registered but invisible until a user
    manually enables those scopes in Layer Properties > Actions."""
    action_code = (
        "from qols.parameters_inspector import show_parameters_inspector\n"
        "show_parameters_inspector('[% @layer_id %]', [% $id %])"
    )
    action = QgsAction(ACTION_TYPE_GENERIC_PYTHON, "view parameters as HTML Table", action_code)
    action.setActionScopes({'Feature', 'Canvas'})
    layer.actions().addAction(action)


# ---------------------------------------------------------------------------
# Dockwidget "Show Table" button (#118 follow-up)
# ---------------------------------------------------------------------------

def collect_project_parameter_sections():
    """Scan every vector layer in the current project for a 'parameters'
    field and return [(layer_name, params_dict), ...] — one entry per
    layer, using its first feature's stored JSON as representative (every
    feature qOLS writes to a given surface layer shares the same params
    blob). Layers without the field, or with unparsable JSON, are skipped."""
    sections = []
    for layer in QgsProject.instance().mapLayers().values():
        if not isinstance(layer, QgsVectorLayer):
            continue
        if layer.fields().indexOf('parameters') == -1:
            continue
        for feature in layer.getFeatures():
            raw = feature.attribute('parameters')
            if not raw:
                continue
            try:
                sections.append((layer.name(), json.loads(raw)))
            except (TypeError, ValueError):
                pass
            break
    return sections


def show_project_parameters_table():
    """Entry point for the dockwidgets' 'Show Table' button: show every
    calculated surface currently in the project (that has stored
    parameters) as a multi-section HTML table, so a user can review what
    inputs produced them without re-running Calculate."""
    sections = collect_project_parameter_sections()
    if not sections:
        sections = [(
            "No data",
            {'message': 'No calculated surfaces with stored parameters found. Run Calculate first.'},
        )]
    return show_web_popup("qOLS Surfaces — Feature Parameters", sections)
