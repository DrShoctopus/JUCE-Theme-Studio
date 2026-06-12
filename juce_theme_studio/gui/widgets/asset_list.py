"""Asset library list with drag-and-drop onto the canvas."""

from __future__ import annotations

from PySide6.QtCore import QMimeData, Qt, Signal
from PySide6.QtGui import QDrag, QKeyEvent
from PySide6.QtWidgets import QListWidget, QListWidgetItem

MIME_ASSET_ID = "application/x-juce-asset-id"
MIME_ASSET_SPRITE = "application/x-juce-asset-sprite"


class AssetListWidget(QListWidget):
    delete_requested = Signal()
    asset_clicked = Signal(str, bool)  # asset_id, is_sprite

    def __init__(self) -> None:
        super().__init__()
        self.setDragEnabled(True)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self.itemClicked.connect(self._on_item_clicked)

    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        asset_id = item.data(Qt.ItemDataRole.UserRole)
        if not asset_id:
            return
        is_sprite = bool(item.data(Qt.ItemDataRole.UserRole + 1))
        self.asset_clicked.emit(str(asset_id), is_sprite)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace):
            self.delete_requested.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def _show_context_menu(self, pos) -> None:  # noqa: ANN001
        if self.itemAt(pos) is None:
            return
        from PySide6.QtWidgets import QMenu

        menu = QMenu(self)
        delete_act = menu.addAction("Delete Asset")
        delete_act.triggered.connect(self.delete_requested.emit)
        menu.exec(self.mapToGlobal(pos))

    def startDrag(self, supportedActions) -> None:  # noqa: ANN001
        item = self.currentItem()
        if item is None:
            return
        asset_id = item.data(Qt.ItemDataRole.UserRole)
        if not asset_id:
            return
        mime = QMimeData()
        mime.setData(MIME_ASSET_ID, str(asset_id).encode("utf-8"))
        is_sprite = bool(item.data(Qt.ItemDataRole.UserRole + 1))
        mime.setData(MIME_ASSET_SPRITE, b"1" if is_sprite else b"0")
        drag = QDrag(self)
        drag.setMimeData(mime)
        drag.exec(Qt.DropAction.CopyAction)

    def set_assets(self, assets: list) -> None:
        self.clear()
        for asset in assets:
            tag = " [sprite]" if asset.is_sprite_sheet else ""
            item = QListWidgetItem(f"{asset.name}{tag}")
            item.setData(Qt.ItemDataRole.UserRole, asset.id)
            item.setData(Qt.ItemDataRole.UserRole + 1, asset.is_sprite_sheet)
            self.addItem(item)

    def select_asset(self, asset_id: str) -> bool:
        """Select and scroll to the asset with this id (e.g. after import)."""
        for i in range(self.count()):
            item = self.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == asset_id:
                self.setCurrentItem(item)
                self.scrollToItem(item, QListWidget.ScrollHint.PositionAtCenter)
                return True
        return False
