"""Properties inspector for selected controls."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QScrollArea,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from juce_theme_studio.core.controls import Control
from juce_theme_studio.core.sprites import SpriteConfig
from juce_theme_studio.core.types import SpriteLayout


class PropertiesPanel(QWidget):
    properties_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._control: Control | None = None
        self._block = False

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        self._form = QFormLayout(container)

        self._name = QLineEdit()
        self._name.editingFinished.connect(self._emit_change)
        self._form.addRow("Name", self._name)

        self._type_label = QLabel()
        self._form.addRow("Type", self._type_label)

        self._x = QSpinBox()
        self._x.setRange(-10000, 10000)
        self._x.valueChanged.connect(self._on_bounds_changed)
        self._y = QSpinBox()
        self._y.setRange(-10000, 10000)
        self._y.valueChanged.connect(self._on_bounds_changed)
        self._w = QSpinBox()
        self._w.setRange(1, 10000)
        self._w.valueChanged.connect(self._on_bounds_changed)
        self._h = QSpinBox()
        self._h.setRange(1, 10000)
        self._h.valueChanged.connect(self._on_bounds_changed)
        self._form.addRow("X", self._x)
        self._form.addRow("Y", self._y)
        self._form.addRow("Width", self._w)
        self._form.addRow("Height", self._h)

        self._aspect = QCheckBox("Lock aspect ratio")
        self._aspect.toggled.connect(self._emit_change)
        self._form.addRow(self._aspect)

        self._label_text = QLineEdit()
        self._label_text.editingFinished.connect(self._emit_change)
        self._form.addRow("Label text", self._label_text)

        # Sprite settings
        sprite_box = QGroupBox("Sprite Sheet")
        sprite_form = QFormLayout(sprite_box)
        self._sprite_layout = QComboBox()
        for sl in SpriteLayout:
            self._sprite_layout.addItem(sl.value.replace("_", " ").title(), sl.value)
        self._sprite_layout.currentIndexChanged.connect(self._on_sprite_changed)
        sprite_form.addRow("Layout", self._sprite_layout)

        self._frame_count = QSpinBox()
        self._frame_count.setRange(1, 256)
        self._frame_count.valueChanged.connect(self._on_sprite_changed)
        sprite_form.addRow("Frame count", self._frame_count)

        self._frame_w = QSpinBox()
        self._frame_w.setRange(1, 2048)
        self._frame_w.valueChanged.connect(self._on_sprite_changed)
        self._frame_h = QSpinBox()
        self._frame_h.setRange(1, 2048)
        self._frame_h.valueChanged.connect(self._on_sprite_changed)
        sprite_form.addRow("Frame W", self._frame_w)
        sprite_form.addRow("Frame H", self._frame_h)

        self._start_angle = QDoubleSpinBox()
        self._start_angle.setRange(-360, 360)
        self._start_angle.valueChanged.connect(self._on_sprite_changed)
        self._end_angle = QDoubleSpinBox()
        self._end_angle.setRange(-360, 360)
        self._end_angle.valueChanged.connect(self._on_sprite_changed)
        sprite_form.addRow("Start angle", self._start_angle)
        sprite_form.addRow("End angle", self._end_angle)

        self._form.addRow(sprite_box)

        # Mapping
        map_box = QGroupBox("JUCE Mapping")
        map_form = QFormLayout(map_box)
        self._juce_class = QLineEdit()
        self._juce_class.editingFinished.connect(self._emit_change)
        self._cpp_var = QLineEdit()
        self._cpp_var.editingFinished.connect(self._emit_change)
        self._param_id = QLineEdit()
        self._param_id.editingFinished.connect(self._emit_change)
        map_form.addRow("JUCE class", self._juce_class)
        map_form.addRow("C++ variable", self._cpp_var)
        map_form.addRow("Parameter ID", self._param_id)
        self._form.addRow(map_box)

        # Preview
        preview_box = QGroupBox("Preview")
        preview_form = QFormLayout(preview_box)
        self._preview_value = QDoubleSpinBox()
        self._preview_value.setRange(0.0, 1.0)
        self._preview_value.setSingleStep(0.01)
        self._preview_value.valueChanged.connect(self._on_preview_changed)
        preview_form.addRow("Value", self._preview_value)
        self._preview_on = QCheckBox("On / Active")
        self._preview_on.toggled.connect(self._on_preview_changed)
        preview_form.addRow(self._preview_on)
        self._form.addRow(preview_box)

        scroll.setWidget(container)
        layout = QVBoxLayout(self)
        layout.addWidget(scroll)
        self._placeholder = QLabel("Select a control to edit properties.")
        layout.addWidget(self._placeholder)

    def set_control(self, control: Control | None) -> None:
        self._control = control
        self._block = True
        if control is None:
            self._placeholder.setVisible(True)
            self._block = False
            return
        self._placeholder.setVisible(False)
        self._name.setText(control.name)
        self._type_label.setText(control.control_type.value)
        self._x.setValue(control.x)
        self._y.setValue(control.y)
        self._w.setValue(control.width)
        self._h.setValue(control.height)
        self._aspect.setChecked(control.aspect_locked)
        self._label_text.setText(control.label_text)
        self._juce_class.setText(control.mapping.juce_class)
        self._cpp_var.setText(control.mapping.cpp_variable)
        self._param_id.setText(control.mapping.parameter_id)
        self._preview_value.setValue(control.preview_value)
        self._preview_on.setChecked(control.preview_on)

        sc = control.sprite_config
        if sc:
            idx = self._sprite_layout.findData(sc.layout.value)
            self._sprite_layout.setCurrentIndex(max(0, idx))
            self._frame_count.setValue(sc.frame_count)
            self._frame_w.setValue(sc.frame_width)
            self._frame_h.setValue(sc.frame_height)
            self._start_angle.setValue(sc.start_angle_deg)
            self._end_angle.setValue(sc.end_angle_deg)
        self._block = False

    def _on_bounds_changed(self) -> None:
        if self._block or not self._control:
            return
        self._control.x = self._x.value()
        self._control.y = self._y.value()
        self._control.width = self._w.value()
        self._control.height = self._h.value()
        self._emit_change()

    def _on_sprite_changed(self) -> None:
        if self._block or not self._control:
            return
        if self._control.sprite_config is None:
            self._control.sprite_config = SpriteConfig()
        sc = self._control.sprite_config
        sc.layout = SpriteLayout(self._sprite_layout.currentData())
        sc.frame_count = self._frame_count.value()
        sc.frame_width = self._frame_w.value()
        sc.frame_height = self._frame_h.value()
        sc.start_angle_deg = self._start_angle.value()
        sc.end_angle_deg = self._end_angle.value()
        self._emit_change()

    def _on_preview_changed(self) -> None:
        if self._block or not self._control:
            return
        self._control.preview_value = self._preview_value.value()
        self._control.preview_on = self._preview_on.isChecked()
        self._emit_change()

    def _emit_change(self) -> None:
        if self._block or not self._control:
            return
        self._control.name = self._name.text()
        self._control.aspect_locked = self._aspect.isChecked()
        self._control.label_text = self._label_text.text()
        self._control.mapping.juce_class = self._juce_class.text()
        self._control.mapping.cpp_variable = self._cpp_var.text()
        self._control.mapping.parameter_id = self._param_id.text()
        self.properties_changed.emit()
