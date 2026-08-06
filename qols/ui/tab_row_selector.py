"""qols/ui/tab_row_selector.py — two-row tab-bar compatibility shim (#123).

The classic panel's tab bar (qols_panel_base.ui, ``scriptTabWidget``)
outgrew a single row of tabs — with 6 entries it overflowed horizontally,
requiring a scroll arrow to reach the later ones. Stock Qt has no
built-in multi-row tab layout, so the ``.ui`` file now uses two plain
``QTabBar``s (native look, no custom styling) stacked vertically, each
holding half the tabs, driving a shared ``QStackedWidget``
(``scriptTabStack``).

``TwoRowTabSelector`` presents a ``QTabWidget``-compatible surface
(``currentIndex()``, ``tabText(i)``, ``widget(i)``, a
``currentChanged(int)`` signal) backed by that two-bar+stack pair, so the
existing ``self.scriptTabWidget``-based call sites in dockwidget.py need
no changes beyond constructing this shim once and assigning it to
``self.scriptTabWidget``.

Each ``QTabBar`` keeps its own native ``currentIndex`` independently of
the other — nothing in Qt makes two separate ``QTabBar``s mutually
exclusive. The shim listens to both bars' native ``currentChanged``
signals and, whenever one bar reports a real selection, deselects the
other bar via ``setCurrentIndex(-1)`` (a normal, supported QTabBar state
meaning "no current tab") — guarded by a ``_syncing`` flag so that
programmatic deselection doesn't itself get mistaken for a user action.
"""
from __future__ import annotations

from typing import Sequence

from qgis.PyQt.QtCore import QObject, pyqtSignal


class TwoRowTabSelector(QObject):
    """QTabWidget-compatible shim over two QTabBar rows + a QStackedWidget.

    ``bars`` and ``stack_indices_per_bar`` must be given in the same
    order (one entry per row): ``stack_indices_per_bar[i][j]`` is the
    ``stack`` page index that ``bars[i]``'s tab ``j`` should show.
    ``tab_texts`` gives the label for each stack index, in stack order —
    used for ``tabText()`` instead of reading back from a bar, so it
    doesn't depend on which bar currently owns a given stack index.
    """

    currentChanged = pyqtSignal(int)

    def __init__(
        self,
        bars: Sequence,
        stack_indices_per_bar: Sequence[Sequence[int]],
        tab_texts: Sequence[str],
        stack,
        parent=None,
    ):
        super().__init__(parent)
        if len(bars) != len(stack_indices_per_bar):
            raise ValueError("bars and stack_indices_per_bar must have the same length")
        for bar, row in zip(bars, stack_indices_per_bar):
            if bar.count() != len(row):
                raise ValueError(
                    f"bar has {bar.count()} tabs but its row maps {len(row)} stack indices"
                )
        total_tabs = sum(len(row) for row in stack_indices_per_bar)
        if total_tabs != stack.count() or len(tab_texts) != stack.count():
            raise ValueError(
                f"tab/page count mismatch: {total_tabs} mapped tabs, "
                f"{len(tab_texts)} labels, {stack.count()} pages"
            )
        self._bars = list(bars)
        self._rows = [list(row) for row in stack_indices_per_bar]
        self._tab_texts = list(tab_texts)
        self._stack = stack
        self._current_index = -1
        self._syncing = False
        for bar_index, bar in enumerate(self._bars):
            bar.currentChanged.connect(lambda tab_index, bi=bar_index: self._on_bar_changed(bi, tab_index))
        self._activate(0, emit=False)

    def _find_bar_and_tab(self, stack_index: int):
        for bar_index, row in enumerate(self._rows):
            if stack_index in row:
                return bar_index, row.index(stack_index)
        return None, None

    def _activate(self, stack_index: int, emit: bool) -> None:
        owner_bar, owner_tab = self._find_bar_and_tab(stack_index)
        self._syncing = True
        try:
            for bar_index, bar in enumerate(self._bars):
                bar.setCurrentIndex(owner_tab if bar_index == owner_bar else -1)
        finally:
            self._syncing = False
        self._current_index = stack_index
        self._stack.setCurrentIndex(stack_index)
        if emit:
            self.currentChanged.emit(stack_index)

    def _on_bar_changed(self, bar_index: int, tab_index: int) -> None:
        if self._syncing or tab_index < 0:
            return
        stack_index = self._rows[bar_index][tab_index]
        if stack_index == self._current_index:
            return
        self._activate(stack_index, emit=True)

    # -- QTabWidget-compatible read API --------------------------------

    def currentIndex(self) -> int:
        return self._current_index

    def widget(self, index: int):
        if 0 <= index < len(self._tab_texts):
            return self._stack.widget(index)
        return None

    def tabText(self, index: int) -> str:
        if 0 <= index < len(self._tab_texts):
            return self._tab_texts[index]
        return ""

    def setCurrentIndex(self, index: int) -> None:
        if 0 <= index < len(self._tab_texts) and index != self._current_index:
            self._activate(index, emit=True)
