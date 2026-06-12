"""QGraphicsItem subclasses for canvas controls."""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from PIL.ImageQt import ImageQt
from PySide6.QtCore import QPointF, QRectF, Qt, Signal  # QPointF used in itemChange
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QGraphicsItem, QGraphicsObject, QGraphicsTextItem

from juce_theme_studio.core.assets import resolve_asset_path
from juce_theme_studio.core.controls import Control
from juce_theme_studio.core.manifest import AssetEntry, ThemeManifest
from juce_theme_studio.core.sprites import (
    PreviewState,
    extract_frame,
    frame_for_button_state,
    frame_index_for_value,
)
from juce_theme_studio.core.types import ControlType


class ControlGraphicsItem(QGraphicsObject):
    """Draggable, resizable control on the canvas."""

    geometry_changed = Signal(str)
    clicked = Signal(str)  # control id

    HANDLE_SIZE = 8

    def __init__(
        self,
        control: Control,
        manifest: ThemeManifest,
        project_root: Path,
        preview_mode: bool = False,
        button_preview_state: PreviewState = PreviewState.NORMAL,
    ) -> None:
        super().__init__()
        self._rect = QRectF(0, 0, control.width, control.height)
        self.control = control
        self.manifest = manifest
        self.project_root = project_root
        self.preview_mode = preview_mode
        self.button_preview_state = button_preview_state
        self._pixmap: QPixmap | None = None
        self._aspect_ratio = control.width / max(1, control.height)
        self._resizing = False
        self._resize_mode = ""  # "e" | "s" | "se"
        self._drag_start: QPointF | None = None
        self._orig_geom: QRectF | None = None

        self.setPos(control.x, control.y)
        self.setZValue(control.z_index)
        self.setVisible(control.visible)
        self.setAcceptHoverEvents(True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        if not control.locked and not preview_mode:
            self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)

        self._label = QGraphicsTextItem(control.name, self)
        self._label.setDefaultTextColor(QColor(200, 200, 255))
        self._label.setFont(QFont("Sans", 8))
        self._label.setPos(2, 2)

        self._refresh_pixmap()

    def boundingRect(self) -> QRectF:
        return self._rect

    def rect(self) -> QRectF:
        return QRectF(self._rect)

    def setRect(self, x: float, y: float, width: float, height: float) -> None:
        new_rect = QRectF(x, y, width, height)
        if new_rect == self._rect:
            return
        self.prepareGeometryChange()
        self._rect = new_rect

    def _refresh_pixmap(self) -> None:
        self._pixmap = None
        if self.control.control_type == ControlType.LABEL:
            return
        asset = self._get_asset()
        if asset is None:
            return
        path = resolve_asset_path(self.project_root, asset)
        if not path.is_file():
            return
        try:
            if self.control.sprite_config and asset.is_sprite_sheet:
                frame_idx = self._current_frame_index()
                img = extract_frame(path, self.control.sprite_config, frame_idx)
            else:
                with Image.open(path) as img_raw:
                    img = img_raw.convert("RGBA")
            qimg = ImageQt(img)
            self._pixmap = QPixmap.fromImage(qimg)
        except Exception:
            self._pixmap = None

    def _get_asset(self) -> AssetEntry | None:
        if not self.control.asset_id:
            return None
        return self.manifest.get_asset(self.control.asset_id)

    def _current_frame_index(self) -> int:
        sc = self.control.sprite_config
        if sc is None:
            return 0
        ctype = self.control.control_type
        if ctype in {ControlType.BUTTON, ControlType.TOGGLE_BUTTON, ControlType.SWITCH}:
            if self.preview_mode:
                if self.button_preview_state != PreviewState.NORMAL:
                    return frame_for_button_state(sc, self.button_preview_state)
                return (
                    sc.active_frame
                    if self.control.preview_on and sc.active_frame is not None
                    else sc.default_frame
                )
            return sc.default_frame
        if ctype in {ControlType.KNOB, ControlType.SLIDER, ControlType.METER, ControlType.VU_METER,
                     ControlType.GAIN_REDUCTION_METER}:
            return frame_index_for_value(sc, self.control.preview_value)
        if ctype == ControlType.LED:
            return (
                sc.active_frame
                if self.control.preview_on and sc.active_frame is not None
                else sc.default_frame
            )
        return sc.default_frame

    def paint(self, painter: QPainter, option, widget=None) -> None:  # noqa: ANN001
        rect = self.rect()
        if self._pixmap and not self._pixmap.isNull():
            painter.drawPixmap(rect.toRect(), self._pixmap)
        else:
            color = QColor(80, 120, 180, 120)
            if self.control.control_type == ControlType.KNOB:
                color = QColor(180, 120, 80, 120)
            elif self.control.control_type == ControlType.LABEL:
                color = QColor(60, 60, 60, 80)
            painter.fillRect(rect, color)

        if self.control.control_type == ControlType.LABEL:
            painter.setPen(QColor(220, 220, 220))
            text = self.control.label_text or self.control.name
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, text)

        pen = QPen(QColor(100, 150, 255) if self.isSelected() else QColor(80, 80, 80))
        pen.setWidth(2 if self.isSelected() else 1)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(rect)

        if self.isSelected() and not self.preview_mode and not self.control.locked:
            self._draw_handles(painter)

    def _handles(self) -> dict[str, QRectF]:
        """Resize handles: east (width), south (height), south-east (both)."""
        hs = self.HANDLE_SIZE
        r = self.rect()
        return {
            "e": QRectF(r.right() - hs, r.center().y() - hs / 2, hs, hs),
            "s": QRectF(r.center().x() - hs / 2, r.bottom() - hs, hs, hs),
            "se": QRectF(r.right() - hs, r.bottom() - hs, hs, hs),
        }

    def _handle_at(self, pos: QPointF) -> str:
        handles = self._handles()
        for mode in ("se", "e", "s"):  # corner wins over edges
            if handles[mode].contains(pos):
                return mode
        return ""

    def _draw_handles(self, painter: QPainter) -> None:
        painter.setBrush(QBrush(QColor(100, 150, 255)))
        for h in self._handles().values():
            painter.drawRect(h)

    def itemChange(self, change, value):  # noqa: ANN001
        scene = self.scene()
        if (
            change == QGraphicsItem.GraphicsItemChange.ItemPositionChange
            and scene is not None
            and hasattr(scene, "snap_control")
            and not self.preview_mode
            and not self.control.locked
        ):
            pos = value
            result = scene.snap_control(self.control, pos.x(), pos.y())
            scene.update_guides(result.guide_lines_x, result.guide_lines_y)
            return QPointF(result.x, result.y)
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self.control.x = int(self.pos().x())
            self.control.y = int(self.pos().y())
            if scene is not None and hasattr(scene, "clear_guides"):
                scene.clear_guides()
            self.geometry_changed.emit(self.control.id)
        return super().itemChange(change, value)

    def mousePressEvent(self, event) -> None:  # noqa: ANN001
        if self.preview_mode or self.control.locked:
            super().mousePressEvent(event)
            return
        pos = event.pos()
        r = self.rect()
        mode = self._handle_at(pos)
        if mode:
            self._resizing = True
            self._resize_mode = mode
            self._drag_start = event.scenePos()
            self._orig_geom = QRectF(self.pos().x(), self.pos().y(), r.width(), r.height())
            event.accept()
            return
        super().mousePressEvent(event)
        if event.button() == Qt.MouseButton.LeftButton and not self._resizing:
            self.clicked.emit(self.control.id)

    def mouseMoveEvent(self, event) -> None:  # noqa: ANN001
        if self._resizing and self._drag_start and self._orig_geom:
            delta = event.scenePos() - self._drag_start
            ow, oh = self._orig_geom.width(), self._orig_geom.height()
            new_w, new_h = int(ow), int(oh)
            # Edge handles resize a single axis; the corner does both.
            if self._resize_mode in ("e", "se"):
                new_w = max(8, int(ow + delta.x()))
            if self._resize_mode in ("s", "se"):
                new_h = max(8, int(oh + delta.y()))
            # Aspect lock only couples the free corner drag, never the edges.
            if self._resize_mode == "se" and self.control.aspect_locked:
                new_h = max(8, int(new_w / self._aspect_ratio))
            self.setRect(0, 0, new_w, new_h)
            self.control.width = new_w
            self.control.height = new_h
            self.geometry_changed.emit(self.control.id)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: ANN001
        self._resizing = False
        self._resize_mode = ""
        super().mouseReleaseEvent(event)

    def hoverMoveEvent(self, event) -> None:  # noqa: ANN001
        if self.preview_mode or self.control.locked or not self.isSelected():
            self.setCursor(Qt.CursorShape.ArrowCursor)
            super().hoverMoveEvent(event)
            return
        cursors = {
            "e": Qt.CursorShape.SizeHorCursor,
            "s": Qt.CursorShape.SizeVerCursor,
            "se": Qt.CursorShape.SizeFDiagCursor,
        }
        self.setCursor(cursors.get(self._handle_at(event.pos()), Qt.CursorShape.ArrowCursor))
        super().hoverMoveEvent(event)

    def update_from_control(self, preview_mode: bool, button_state: PreviewState) -> None:
        self.preview_mode = preview_mode
        self.button_preview_state = button_state
        self.setPos(self.control.x, self.control.y)
        self.setRect(0, 0, self.control.width, self.control.height)
        self.setZValue(self.control.z_index)
        self.setVisible(self.control.visible)
        movable = not self.control.locked and not preview_mode
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, movable)
        self._refresh_pixmap()
        self.update()
