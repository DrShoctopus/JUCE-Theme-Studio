"""Layer tree for screen controls."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from juce_theme_studio.core.controls import Control
from juce_theme_studio.core.manifest import Screen


class LayersPanel(QWidget):
    selection_changed = Signal(str)
    layer_order_changed = Signal()
    visibility_changed = Signal()
    lock_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        self._tree = QTreeWidget()
        self._tree.setHeaderLabels(["Layer", "Type"])
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._tree.itemSelectionChanged.connect(self._on_selection)
        layout.addWidget(self._tree)

        btn_row = QHBoxLayout()
        self._up_btn = QPushButton("↑")
        self._down_btn = QPushButton("↓")
        self._vis_btn = QPushButton("Hide/Show")
        self._lock_btn = QPushButton("Lock")
        self._up_btn.clicked.connect(lambda: self._move_layer(-1))
        self._down_btn.clicked.connect(lambda: self._move_layer(1))
        self._vis_btn.clicked.connect(self._toggle_visibility)
        self._lock_btn.clicked.connect(self._toggle_lock)
        btn_row.addWidget(self._up_btn)
        btn_row.addWidget(self._down_btn)
        btn_row.addWidget(self._vis_btn)
        btn_row.addWidget(self._lock_btn)
        layout.addLayout(btn_row)

        self._screen: Screen | None = None
        self._items: dict[str, QTreeWidgetItem] = {}

    def set_screen(self, screen: Screen | None) -> None:
        self._screen = screen
        self._tree.clear()
        self._items.clear()
        if screen is None:
            return
        for control in sorted(screen.controls, key=lambda c: c.z_index, reverse=True):
            item = QTreeWidgetItem([control.name, control.control_type.value])
            item.setData(0, Qt.ItemDataRole.UserRole, control.id)
            if not control.visible:
                item.setForeground(0, Qt.GlobalColor.gray)
            if control.locked:
                item.setIcon(0, QIcon())
            self._tree.addTopLevelItem(item)
            self._items[control.id] = item

    def select_control(self, control_id: str | None) -> None:
        self._tree.blockSignals(True)
        self._tree.clearSelection()
        if control_id and control_id in self._items:
            self._items[control_id].setSelected(True)
        self._tree.blockSignals(False)

    def _on_selection(self) -> None:
        items = self._tree.selectedItems()
        if items:
            cid = items[0].data(0, Qt.ItemDataRole.UserRole)
            self.selection_changed.emit(cid)

    def _current_control(self) -> Control | None:
        items = self._tree.selectedItems()
        if not items or not self._screen:
            return None
        cid = items[0].data(0, Qt.ItemDataRole.UserRole)
        for c in self._screen.controls:
            if c.id == cid:
                return c
        return None

    def _move_layer(self, direction: int) -> None:
        control = self._current_control()
        if not control or not self._screen:
            return
        controls = sorted(self._screen.controls, key=lambda c: c.z_index)
        idx = next(i for i, c in enumerate(controls) if c.id == control.id)
        new_idx = idx + direction
        if new_idx < 0 or new_idx >= len(controls):
            return
        controls[idx], controls[new_idx] = controls[new_idx], controls[idx]
        for i, c in enumerate(controls):
            c.z_index = i
        self.set_screen(self._screen)
        self.select_control(control.id)
        self.layer_order_changed.emit()

    def _toggle_visibility(self) -> None:
        control = self._current_control()
        if control:
            control.visible = not control.visible
            self.set_screen(self._screen)
            self.select_control(control.id)
            self.visibility_changed.emit()

    def _toggle_lock(self) -> None:
        control = self._current_control()
        if control:
            control.locked = not control.locked
            self.set_screen(self._screen)
            self.select_control(control.id)
            self.lock_changed.emit()
