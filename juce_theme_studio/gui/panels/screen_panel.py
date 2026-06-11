"""Screen / canvas settings inspector."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from juce_theme_studio.core.manifest import Screen


class ScreenPanel(QWidget):
    screen_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        box = QGroupBox("Screen Settings")
        form = QFormLayout(box)

        self._name = QLineEdit()
        self._name.editingFinished.connect(self._emit)
        form.addRow("Name", self._name)

        self._component = QLineEdit()
        self._component.setReadOnly(True)
        form.addRow("JUCE component", self._component)

        self._width = QSpinBox()
        self._width.setRange(100, 10000)
        self._width.valueChanged.connect(self._on_size)
        self._height = QSpinBox()
        self._height.setRange(100, 10000)
        self._height.valueChanged.connect(self._on_size)
        form.addRow("Canvas width", self._width)
        form.addRow("Canvas height", self._height)

        layout.addWidget(box)
        self._placeholder = QLabel("Select a screen to edit canvas settings.")
        layout.addWidget(self._placeholder)
        layout.addStretch()

        self._screen: Screen | None = None
        self._previous_name = ""
        self._block = False

    def set_screen(self, screen: Screen | None) -> None:
        self._screen = screen
        self._block = True
        if screen is None:
            self._placeholder.setVisible(True)
            self._block = False
            return
        self._placeholder.setVisible(False)
        self._previous_name = screen.name
        self._name.setText(screen.name)
        self._component.setText(screen.juce_component or "(manual)")
        self._width.setValue(screen.canvas_width)
        self._height.setValue(screen.canvas_height)
        self._block = False

    def _on_size(self) -> None:
        if self._block or not self._screen:
            return
        self._screen.canvas_width = self._width.value()
        self._screen.canvas_height = self._height.value()
        self._emit()

    def _emit(self) -> None:
        if self._block or not self._screen:
            return
        new_name = self._name.text()
        if new_name != self._previous_name:
            for ctrl in self._screen.controls:
                if ctrl.mapping.screen_name == self._previous_name:
                    ctrl.mapping.screen_name = new_name
            self._previous_name = new_name
        self._screen.name = new_name
        self.screen_changed.emit()
