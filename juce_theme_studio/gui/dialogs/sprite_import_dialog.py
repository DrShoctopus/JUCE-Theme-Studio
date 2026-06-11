"""Configure sprite sheet after import."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QSpinBox,
    QVBoxLayout,
)

from juce_theme_studio.core.sprites import SpriteConfig, detect_sprite_grid
from juce_theme_studio.core.types import SpriteLayout


class SpriteImportDialog(QDialog):
    def __init__(self, image_path: Path, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Sprite Sheet Configuration")
        fw, fh, fc, cols = detect_sprite_grid(image_path)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._layout = QComboBox()
        for sl in SpriteLayout:
            self._layout.addItem(sl.value.replace("_", " ").title(), sl)
        form.addRow("Layout", self._layout)

        self._frame_w = QSpinBox()
        self._frame_w.setRange(1, 2048)
        self._frame_w.setValue(fw)
        self._frame_h = QSpinBox()
        self._frame_h.setRange(1, 2048)
        self._frame_h.setValue(fh)
        self._frame_count = QSpinBox()
        self._frame_count.setRange(1, 256)
        self._frame_count.setValue(fc)
        self._columns = QSpinBox()
        self._columns.setRange(1, 64)
        self._columns.setValue(cols)

        form.addRow("Frame width", self._frame_w)
        form.addRow("Frame height", self._frame_h)
        form.addRow("Frame count", self._frame_count)
        form.addRow("Columns (grid)", self._columns)

        layout.addLayout(form)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def sprite_config(self) -> SpriteConfig:
        layout = self._layout.currentData()
        return SpriteConfig(
            layout=layout,
            frame_width=self._frame_w.value(),
            frame_height=self._frame_h.value(),
            frame_count=self._frame_count.value(),
            columns=self._columns.value(),
            rows=max(1, self._frame_count.value() // max(1, self._columns.value())),
        )
