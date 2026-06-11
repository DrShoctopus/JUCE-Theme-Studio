"""Screen editor canvas using QGraphicsScene."""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from PIL.ImageQt import ImageQt
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QPainter,
    QPen,
    QPixmap,
    QWheelEvent,
)
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsScene, QGraphicsView

from juce_theme_studio.core.assets import resolve_asset_path
from juce_theme_studio.core.controls import Control
from juce_theme_studio.core.manifest import Screen, ThemeManifest
from juce_theme_studio.core.snap import snap_position
from juce_theme_studio.core.sprites import PreviewState
from juce_theme_studio.gui.canvas_items import ControlGraphicsItem
from juce_theme_studio.gui.guide_overlay import GuideOverlay
from juce_theme_studio.gui.widgets.asset_list import MIME_ASSET_ID, MIME_ASSET_SPRITE


class CanvasScene(QGraphicsScene):
    selection_changed = Signal(object)  # Control | None
    control_moved = Signal(str)

    def __init__(self, manifest: ThemeManifest, project_root: Path) -> None:
        super().__init__()
        self.manifest = manifest
        self.project_root = project_root
        self.screen: Screen | None = None
        self.preview_mode = False
        self.button_preview_state = PreviewState.NORMAL
        self.snap_to_grid = manifest.snap_to_grid
        self.grid_size = manifest.grid_size
        self._items: dict[str, ControlGraphicsItem] = {}
        self._bg_item: QGraphicsPixmapItem | None = None
        self._border: QGraphicsRectItem | None = None
        self._guides = GuideOverlay()
        self.show_guides = True

    def load_screen(self, screen: Screen) -> None:
        self.screen = screen
        self.clear()
        self._items.clear()
        self._bg_item = None

        self._border = QGraphicsRectItem(0, 0, screen.canvas_width, screen.canvas_height)
        self._border.setPen(QPen(QColor(60, 60, 60), 2))
        self._border.setBrush(QBrush(QColor(30, 30, 30)))
        self._border.setZValue(-1000)
        self.addItem(self._border)

        if screen.background_asset_id:
            asset = self.manifest.get_asset(screen.background_asset_id)
            if asset:
                path = resolve_asset_path(self.project_root, asset)
                if path.is_file():
                    try:
                        with Image.open(path) as img:
                            qimg = ImageQt(img.convert("RGBA"))
                        pix = QPixmap.fromImage(qimg).scaled(
                            screen.canvas_width,
                            screen.canvas_height,
                            Qt.AspectRatioMode.IgnoreAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                        self._bg_item = QGraphicsPixmapItem(pix)
                        self._bg_item.setZValue(-500)
                        self.addItem(self._bg_item)
                    except Exception:
                        pass

        for control in sorted(screen.controls, key=lambda c: c.z_index):
            self._add_control_item(control)

        self.setSceneRect(-50, -50, screen.canvas_width + 100, screen.canvas_height + 100)

    def _add_control_item(self, control: Control) -> ControlGraphicsItem:
        item = ControlGraphicsItem(
            control,
            self.manifest,
            self.project_root,
            self.preview_mode,
            self.button_preview_state,
        )
        item.geometry_changed.connect(self.control_moved.emit)
        self.addItem(item)
        self._items[control.id] = item
        return item

    def add_control(self, control: Control) -> None:
        if self.screen is None:
            return
        self.screen.controls.append(control)
        self._add_control_item(control)

    def remove_control(self, control_id: str) -> None:
        item = self._items.pop(control_id, None)
        if item:
            self.removeItem(item)
        if self.screen:
            self.screen.controls = [c for c in self.screen.controls if c.id != control_id]

    def get_selected_controls(self) -> list[Control]:
        return [
            item.control
            for item in self.selectedItems()
            if isinstance(item, ControlGraphicsItem)
        ]

    def get_selected_control(self) -> Control | None:
        selected = self.get_selected_controls()
        return selected[0] if selected else None

    def snap_control(self, control: Control, x: float, y: float):
        if self.screen is None:
            from juce_theme_studio.core.snap import SnapResult
            return SnapResult(int(x), int(y), [], [])
        others = self.screen.controls
        return snap_position(
            control,
            x,
            y,
            others,
            canvas_width=self.screen.canvas_width,
            canvas_height=self.screen.canvas_height,
            grid_size=self.grid_size,
            snap_to_grid=self.snap_to_grid,
        )

    def update_guides(self, x_lines: list[int], y_lines: list[int]) -> None:
        if not self.show_guides or self.screen is None:
            self._guides.clear(self)
            return
        self._guides.show(
            self,
            x_lines,
            y_lines,
            self.screen.canvas_width,
            self.screen.canvas_height,
        )

    def clear_guides(self) -> None:
        self._guides.clear(self)

    def select_control(self, control_id: str | None) -> None:
        self.clearSelection()
        if control_id and control_id in self._items:
            self._items[control_id].setSelected(True)

    def refresh_all(self) -> None:
        if self.screen:
            self.load_screen(self.screen)

    def set_preview_mode(self, enabled: bool) -> None:
        self.preview_mode = enabled
        for item in self._items.values():
            item.preview_mode = enabled
            item.setFlag(
                item.GraphicsItemFlag.ItemIsMovable,
                not item.control.locked and not enabled,
            )
            item.update()

    def set_button_preview_state(self, state: PreviewState) -> None:
        self.button_preview_state = state
        for item in self._items.values():
            item.button_preview_state = state
            item._refresh_pixmap()
            item.update()

    def snap_position(self, pos: QPointF) -> QPointF:
        if not self.snap_to_grid:
            return pos
        g = self.grid_size
        return QPointF(round(pos.x() / g) * g, round(pos.y() / g) * g)

    def drawBackground(self, painter: QPainter, rect: QRectF) -> None:
        super().drawBackground(painter, rect)
        if not self.snap_to_grid:
            return
        g = self.grid_size
        left = int(rect.left()) - (int(rect.left()) % g)
        top = int(rect.top()) - (int(rect.top()) % g)
        lines = QPen(QColor(50, 50, 50, 80))
        for x in range(left, int(rect.right()), g):
            painter.setPen(lines)
            painter.drawLine(x, int(rect.top()), x, int(rect.bottom()))
        for y in range(top, int(rect.bottom()), g):
            painter.drawLine(int(rect.left()), y, int(rect.right()), y)


class CanvasView(QGraphicsView):
    asset_dropped = Signal(str, int, int, bool)  # asset_id, x, y, is_sprite

    def __init__(self, scene: CanvasScene) -> None:
        super().__init__(scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setAcceptDrops(True)
        self._zoom = 1.0

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if event.mimeData().hasFormat(MIME_ASSET_ID):
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dragMoveEvent(self, event: QDragMoveEvent) -> None:
        if event.mimeData().hasFormat(MIME_ASSET_ID):
            event.acceptProposedAction()
        else:
            super().dragMoveEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        mime = event.mimeData()
        if not mime.hasFormat(MIME_ASSET_ID):
            super().dropEvent(event)
            return
        asset_id = bytes(mime.data(MIME_ASSET_ID)).decode("utf-8")
        is_sprite = mime.hasFormat(MIME_ASSET_SPRITE) and mime.data(MIME_ASSET_SPRITE) == b"1"
        pos = self.mapToScene(event.position().toPoint())
        self.asset_dropped.emit(asset_id, int(pos.x()), int(pos.y()), is_sprite)
        event.acceptProposedAction()

    def wheelEvent(self, event: QWheelEvent) -> None:
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self._zoom = max(0.1, min(5.0, self._zoom * factor))
        self.setTransform(self.transform().scale(factor, factor))

    def fit_canvas(self) -> None:
        scene = self.scene()
        if scene and scene.sceneRect().isValid():
            self.fitInView(scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
            self._zoom = 1.0
