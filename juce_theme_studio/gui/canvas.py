"""Screen editor canvas using QGraphicsScene."""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from PIL.ImageQt import ImageQt
from PySide6.QtCore import QPointF, QRect, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import (
    QBrush,
    QColor,
    QDragEnterEvent,
    QDragMoveEvent,
    QDropEvent,
    QPainter,
    QPen,
    QPixmap,
    QResizeEvent,
    QShowEvent,
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
    control_moved = Signal(str)
    control_clicked = Signal(str)  # control id
    # Emitted on mouse release after a drag/resize, carrying the pre-edit geometry
    # snapshot {control_id: (x, y, width, height)} so an undo command can be built.
    geometry_committed = Signal(dict)

    def __init__(self, manifest: ThemeManifest, project_root: Path) -> None:
        super().__init__()
        self._drag_snapshot: dict[str, tuple[int, int, int, int]] = {}
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
        self._guides.reset()
        self.clear()
        self._items.clear()
        self._bg_item = None

        canvas_w = max(screen.canvas_width, 100)
        canvas_h = max(screen.canvas_height, 100)
        self._border = QGraphicsRectItem(0, 0, canvas_w, canvas_h)
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
                            canvas_w,
                            canvas_h,
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

        self.setSceneRect(-50, -50, canvas_w + 100, canvas_h + 100)

    def _add_control_item(self, control: Control) -> ControlGraphicsItem:
        item = ControlGraphicsItem(
            control,
            self.manifest,
            self.project_root,
            self.preview_mode,
            self.button_preview_state,
        )
        item.geometry_changed.connect(self.control_moved.emit)
        item.clicked.connect(self.control_clicked.emit)
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

    def control_at(self, scene_pos: QPointF) -> Control | None:
        """Return topmost control under a scene position (for drop linking)."""
        for item in self.items(scene_pos):
            if isinstance(item, ControlGraphicsItem):
                return item.control
        return None

    def _geometry_snapshot(self) -> dict[str, tuple[int, int, int, int]]:
        return {
            cid: (item.control.x, item.control.y, item.control.width, item.control.height)
            for cid, item in self._items.items()
        }

    def mousePressEvent(self, event) -> None:  # noqa: ANN001
        # Snapshot geometry before any drag/resize so we can build an undo command.
        if not self.preview_mode:
            self._drag_snapshot = self._geometry_snapshot()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: ANN001
        super().mouseReleaseEvent(event)
        if not self._drag_snapshot:
            return
        after = self._geometry_snapshot()
        changed = {
            cid: before
            for cid, before in self._drag_snapshot.items()
            if cid in after and after[cid] != before
        }
        self._drag_snapshot = {}
        if changed:
            self.geometry_committed.emit(changed)

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

    def update_control(self, control_id: str) -> bool:
        """Refresh a single control's item in place (no full canvas rebuild)."""
        item = self._items.get(control_id)
        if item is None:
            return False
        item.update_from_control(self.preview_mode, self.button_preview_state)
        return True

    def set_preview_mode(self, enabled: bool) -> None:
        self.preview_mode = enabled
        for item in self._items.values():
            item.update_from_control(enabled, self.button_preview_state)

    def set_button_preview_state(self, state: PreviewState) -> None:
        self.button_preview_state = state
        for item in self._items.values():
            item.update_from_control(self.preview_mode, state)

    def snap_point_to_grid(self, pos: QPointF) -> QPointF:
        if not self.snap_to_grid:
            return pos
        g = self.grid_size
        return QPointF(round(pos.x() / g) * g, round(pos.y() / g) * g)

    def drawBackground(self, painter: QPainter, rect: QRectF | QRect) -> None:
        super().drawBackground(painter, rect)
        if not self.snap_to_grid or self.screen is None:
            return
        if isinstance(rect, QRect):
            rect = QRectF(rect)
        # Only draw grid within the canvas bounds to avoid millions of lines when zoomed out.
        clip = QRectF(0, 0, self.screen.canvas_width, self.screen.canvas_height)
        visible = rect.intersected(clip)
        if visible.isEmpty():
            return
        g = self.grid_size
        left = max(0, int(visible.left()) - (int(visible.left()) % g))
        top = max(0, int(visible.top()) - (int(visible.top()) % g))
        right = min(self.screen.canvas_width, int(visible.right()))
        bottom = min(self.screen.canvas_height, int(visible.bottom()))
        lines = QPen(QColor(50, 50, 50, 80))
        painter.setPen(lines)
        max_lines = 500
        x, x_count = left, 0
        while x <= right and x_count < max_lines:
            painter.drawLine(x, top, x, bottom)
            x += g
            x_count += 1
        y, y_count = top, 0
        while y <= bottom and y_count < max_lines:
            painter.drawLine(left, y, right, y)
            y += g
            y_count += 1


class CanvasView(QGraphicsView):
    # asset_id, x, y, is_sprite, target_control_id (empty = new control)
    asset_dropped = Signal(str, int, int, bool, str)
    zoom_changed = Signal(float)  # current zoom factor (1.0 == 100%)

    ZOOM_MIN = 0.1
    ZOOM_MAX = 5.0
    ZOOM_STEP = 1.15

    def __init__(self, scene: CanvasScene) -> None:
        super().__init__(scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setAcceptDrops(True)
        self._zoom = 1.0
        self._pending_fit = False
        self._assign_mode = False

    def set_assign_mode(self, active: bool) -> None:
        self._assign_mode = active
        cursor = (
            Qt.CursorShape.CrossCursor if active else Qt.CursorShape.ArrowCursor
        )
        self.setCursor(cursor)
        self.viewport().setCursor(cursor)
        self.setDragMode(
            QGraphicsView.DragMode.NoDrag
            if active
            else QGraphicsView.DragMode.RubberBandDrag
        )

    def current_zoom(self) -> float:
        return self._zoom

    def set_zoom(self, zoom: float) -> None:
        """Set absolute zoom (clamped). Used by the zoom bar."""
        z = max(self.ZOOM_MIN, min(self.ZOOM_MAX, zoom))
        if abs(z - self._zoom) < 1e-6:
            return
        self._apply_zoom(z)

    def _apply_zoom(self, zoom: float) -> None:
        self._zoom = zoom
        self.resetTransform()
        self.scale(self._zoom, self._zoom)
        self.zoom_changed.emit(self._zoom)

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
        asset_id = bytes(mime.data(MIME_ASSET_ID).data()).decode("utf-8")
        is_sprite = (
            mime.hasFormat(MIME_ASSET_SPRITE)
            and bytes(mime.data(MIME_ASSET_SPRITE).data()) == b"1"
        )
        pos = self.mapToScene(event.position().toPoint())
        target_id = ""
        scene = self.scene()
        if isinstance(scene, CanvasScene):
            target = scene.control_at(pos)
            if target is not None:
                target_id = target.id
        self.asset_dropped.emit(asset_id, int(pos.x()), int(pos.y()), is_sprite, target_id)
        event.acceptProposedAction()

    def wheelEvent(self, event: QWheelEvent) -> None:
        # Plain wheel / two-finger touchpad scroll pans the canvas; zooming is
        # done with the zoom bar (or Ctrl/Cmd+wheel as a shortcut).
        zoom_mod = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.MetaModifier
        if event.modifiers() & zoom_mod:
            factor = self.ZOOM_STEP if event.angleDelta().y() > 0 else 1 / self.ZOOM_STEP
            new_zoom = max(self.ZOOM_MIN, min(self.ZOOM_MAX, self._zoom * factor))
            if abs(new_zoom - self._zoom) >= 1e-6:
                self._apply_zoom(new_zoom)
            event.accept()
            return

        pixel = event.pixelDelta()
        if not pixel.isNull():
            dx, dy = pixel.x(), pixel.y()
        else:
            angle = event.angleDelta()
            dx, dy = angle.x(), angle.y()
        hbar = self.horizontalScrollBar()
        vbar = self.verticalScrollBar()
        hbar.setValue(hbar.value() - dx)
        vbar.setValue(vbar.value() - dy)
        event.accept()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        if self._pending_fit:
            self._perform_fit()

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if self._pending_fit:
            self._perform_fit()

    def fit_canvas(self) -> None:
        if self.viewport().width() < 2 or self.viewport().height() < 2:
            self._pending_fit = True
            QTimer.singleShot(0, self._perform_fit)
            return
        self._perform_fit()

    def _perform_fit(self) -> None:
        if self.viewport().width() < 2 or self.viewport().height() < 2:
            self._pending_fit = True
            return
        scene = self.scene()
        if scene and scene.sceneRect().isValid():
            self.resetTransform()
            self.fitInView(scene.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)
            self._zoom = self.transform().m11()
            self.zoom_changed.emit(self._zoom)
        self._pending_fit = False
