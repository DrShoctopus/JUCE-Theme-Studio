"""Confirm linking an asset to an existing canvas control."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QVBoxLayout,
)

from juce_theme_studio.core.controls import Control
from juce_theme_studio.core.manifest import AssetEntry


class LinkAssetDialog(QDialog):
    def __init__(
        self,
        control: Control,
        asset: AssetEntry,
        parent=None,
        *,
        prompt: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Link Asset to Control")
        self.setMinimumWidth(420)

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                prompt or "Link this asset to the selected control?",
            )
        )

        form = QFormLayout()
        form.addRow("Control name", QLabel(control.name))
        form.addRow("Control type", QLabel(control.control_type.value))
        if control.mapping.cpp_variable:
            form.addRow("C++ variable", QLabel(control.mapping.cpp_variable))
        if control.mapping.juce_class:
            form.addRow("JUCE class", QLabel(control.mapping.juce_class))
        if control.mapping.parameter_id:
            form.addRow("Parameter ID", QLabel(control.mapping.parameter_id))
        form.addRow("Asset", QLabel(f"{asset.name}{' [sprite]' if asset.is_sprite_sheet else ''}"))
        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Link")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
