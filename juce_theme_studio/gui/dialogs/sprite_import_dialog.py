"""Configure sprite sheet after import."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
)

from juce_theme_studio.core.sprite_detect import detect_sprite_sheet, opencv_available
from juce_theme_studio.core.sprites import SpriteConfig
from juce_theme_studio.core.types import SpriteLayout


class SpriteImportDialog(QDialog):
    def __init__(self, image_path: Path, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Sprite Sheet Configuration")
        detected = detect_sprite_sheet(image_path)
        fw = detected.frame_width
        fh = detected.frame_height
        fc = detected.frame_count
        cols = detected.columns

        layout = QVBoxLayout(self)
        method = "OpenCV" if detected.method == "opencv" else "Pillow"
        hint = f"Auto-detected via {method}"
        if not opencv_available():
            hint += " (pip install opencv-python-headless for vision extras)"
        layout.addWidget(QLabel(hint))
        form = QFormLayout()

        self._layout = QComboBox()
        for sl in SpriteLayout:
            self._layout.addItem(sl.value.replace("_", " ").title(), sl)
        slayout = (
            SpriteLayout(detected.layout)
            if detected.layout in {s.value for s in SpriteLayout}
            else SpriteLayout.HORIZONTAL_STRIP
        )
        layout_idx = self._layout.findData(slayout)
        if layout_idx >= 0:
            self._layout.setCurrentIndex(layout_idx)
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

        self._slice_frames = QCheckBox("Slice all frames into asset library")
        self._slice_frames.setChecked(True)
        self._slice_frames.setToolTip(
            "Each frame is saved as a separate image in the asset library."
        )
        layout.addWidget(self._slice_frames)

        self._keep_sheet = QCheckBox("Also keep full sprite sheet in library")
        self._keep_sheet.setChecked(True)
        layout.addWidget(self._keep_sheet)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def slice_into_library(self) -> bool:
        return self._slice_frames.isChecked()

    def keep_full_sheet(self) -> bool:
        return self._keep_sheet.isChecked()

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
