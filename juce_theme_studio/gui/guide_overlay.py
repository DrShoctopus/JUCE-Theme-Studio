"""Temporary alignment guide lines on the canvas."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPen
from PySide6.QtWidgets import QGraphicsLineItem


class GuideOverlay:
    """Manages ephemeral guide line items on a scene."""

    def __init__(self) -> None:
        self._lines: list[QGraphicsLineItem] = []

    def reset(self) -> None:
        """Drop references without removing items (e.g. before scene.clear())."""
        self._lines.clear()

    def clear(self, scene) -> None:  # noqa: ANN001
        for line in self._lines:
            scene.removeItem(line)
        self._lines.clear()

    def show(
        self,
        scene,  # noqa: ANN001
        x_lines: list[int],
        y_lines: list[int],
        canvas_width: int,
        canvas_height: int,
    ) -> None:
        self.clear(scene)
        pen = QPen(QColor(255, 100, 180, 200))
        pen.setWidth(1)
        pen.setStyle(Qt.PenStyle.DashLine)

        for x in x_lines:
            item = QGraphicsLineItem(x, -50, x, canvas_height + 50)
            item.setPen(pen)
            item.setZValue(9999)
            scene.addItem(item)
            self._lines.append(item)

        for y in y_lines:
            item = QGraphicsLineItem(-50, y, canvas_width + 50, y)
            item.setPen(pen)
            item.setZValue(9999)
            scene.addItem(item)
            self._lines.append(item)
