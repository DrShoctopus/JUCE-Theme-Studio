"""Asset library list with drag-and-drop onto the canvas."""

from __future__ import annotations

from PySide6.QtCore import QMimeData, Qt
from PySide6.QtGui import QDrag
from PySide6.QtWidgets import QListWidget, QListWidgetItem

MIME_ASSET_ID = "application/x-juce-asset-id"
MIME_ASSET_SPRITE = "application/x-juce-asset-sprite"


class AssetListWidget(QListWidget):
    def __init__(self) -> None:
        super().__init__()
        self.setDragEnabled(True)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)

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
