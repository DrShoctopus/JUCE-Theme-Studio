"""Configure sprite sheet after import."""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from PIL.ImageQt import ImageQt
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap
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

_PREVIEW_MAX = 320


class SpriteImportDialog(QDialog):
    def __init__(self, image_path: Path, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Sprite Sheet Configuration")
        self._image_path = image_path
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

        # Scaled base pixmap for the live grid preview.
        self._base_pixmap: QPixmap | None = None
        self._sheet_size = (0, 0)
        try:
            with Image.open(image_path) as im:
                rgba = im.convert("RGBA")
                self._sheet_size = rgba.size
                self._base_pixmap = QPixmap.fromImage(ImageQt(rgba)).scaled(
                    _PREVIEW_MAX, _PREVIEW_MAX,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation,
                )
        except Exception:
            self._base_pixmap = None
        self._preview = QLabel()
        self._preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._preview.setMinimumHeight(120)
        layout.addWidget(self._preview)

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

        # Frame size follows the grid: changing the layout / frame count /
        # columns recomputes frame width & height to divide the sheet evenly.
        # This is the only reliable way to fix a full-bleed sheet (no
        # transparent gaps) that auto-detect mis-slices - the user just sets
        # how many frames there are and the size snaps to match, instead of
        # hand-editing width and count to stay consistent.
        self._grid_block = False
        self._frame_count.valueChanged.connect(self._sync_frame_size)
        self._columns.valueChanged.connect(self._sync_frame_size)
        self._layout.currentIndexChanged.connect(self._sync_frame_size)
        for spin in (self._frame_w, self._frame_h):
            spin.valueChanged.connect(self._update_preview)

        form.addRow("Frame width", self._frame_w)
        form.addRow("Frame height", self._frame_h)
        form.addRow("Frame count", self._frame_count)
        form.addRow("Columns (grid)", self._columns)

        layout.addLayout(form)

        # The single sheet asset is what animates: assign it to a knob/button and
        # the frame follows the control's value/state. Slicing is the opt-in path
        # for using individual frames as separate static images (LEDs, decals).
        self._keep_sheet = QCheckBox("Keep sprite sheet as one animated asset")
        self._keep_sheet.setChecked(True)
        self._keep_sheet.setToolTip(
            "Imports the sheet as a single asset whose frames drive a knob/button "
            "animation when assigned to a control."
        )
        layout.addWidget(self._keep_sheet)

        self._slice_frames = QCheckBox("Also slice each frame into separate static assets")
        self._slice_frames.setChecked(False)
        self._slice_frames.setToolTip(
            "Adds every frame to the library as its own image. Use for single-state "
            "art (LEDs, decals), not for animated knobs/meters."
        )
        layout.addWidget(self._slice_frames)

        self._remove_bg = QCheckBox("Make near-white background transparent")
        self._remove_bg.setChecked(False)
        self._remove_bg.setToolTip(
            "Knock out a solid border background so frames sit cleanly on the UI "
            "instead of showing a white box."
        )
        layout.addWidget(self._remove_bg)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._update_preview()

    def _sync_frame_size(self) -> None:
        """Recompute frame width/height so the grid divides the sheet evenly."""
        if self._grid_block:
            return
        sheet_w, sheet_h = self._sheet_size
        if sheet_w <= 0 or sheet_h <= 0:
            return
        count = max(1, self._frame_count.value())
        layout = self._layout.currentData()
        if layout == SpriteLayout.VERTICAL_STRIP:
            cols, rows = 1, count
        elif layout == SpriteLayout.HORIZONTAL_STRIP:
            cols, rows = count, 1
        else:  # grid: keep the user's column count, derive rows
            cols = max(1, min(count, self._columns.value()))
            rows = -(-count // cols)  # ceil

        self._grid_block = True
        self._columns.setValue(cols)
        self._frame_w.setValue(max(1, round(sheet_w / cols)))
        self._frame_h.setValue(max(1, round(sheet_h / rows)))
        self._grid_block = False
        self._update_preview()

    def _update_preview(self) -> None:
        """Overlay the current frame grid on the scaled sheet so the user can
        confirm the slice before importing."""
        if self._base_pixmap is None or self._base_pixmap.isNull():
            self._preview.setText("(no preview)")
            return
        sheet_w, sheet_h = self._sheet_size
        if sheet_w <= 0 or sheet_h <= 0:
            return
        pix = QPixmap(self._base_pixmap)
        scale = pix.width() / sheet_w
        fw = max(1, self._frame_w.value())
        fh = max(1, self._frame_h.value())
        painter = QPainter(pix)
        painter.setPen(QPen(QColor(255, 80, 80, 200), 1))
        x = fw
        while x < sheet_w:
            px = round(x * scale)
            painter.drawLine(px, 0, px, pix.height())
            x += fw
        y = fh
        while y < sheet_h:
            py = round(y * scale)
            painter.drawLine(0, py, pix.width(), py)
            y += fh
        painter.end()
        self._preview.setPixmap(pix)

    def slice_into_library(self) -> bool:
        return self._slice_frames.isChecked()

    def keep_full_sheet(self) -> bool:
        return self._keep_sheet.isChecked()

    def remove_background(self) -> bool:
        return self._remove_bg.isChecked()

    def sprite_config(self) -> SpriteConfig:
        # QComboBox data round-trips str-subclass enums as plain str on PySide6.
        layout = SpriteLayout(self._layout.currentData())
        return SpriteConfig(
            layout=layout,
            frame_width=self._frame_w.value(),
            frame_height=self._frame_h.value(),
            frame_count=self._frame_count.value(),
            columns=self._columns.value(),
            rows=max(1, -(-self._frame_count.value() // max(1, self._columns.value()))),
        )
