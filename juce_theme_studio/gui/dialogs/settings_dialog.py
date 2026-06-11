"""Application / project settings."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from juce_theme_studio.core.manifest import ThemeManifest


class SettingsDialog(QDialog):
    def __init__(self, manifest: ThemeManifest, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self._manifest = manifest

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self._grid = QSpinBox()
        self._grid.setRange(1, 128)
        self._grid.setValue(manifest.grid_size)
        form.addRow("Grid size (px)", self._grid)

        self._snap = QCheckBox("Snap to grid")
        self._snap.setChecked(manifest.snap_to_grid)
        form.addRow(self._snap)

        self._namespace = QLineEdit(manifest.export_settings.namespace)
        form.addRow("C++ export namespace", self._namespace)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def apply(self) -> None:
        self._manifest.grid_size = self._grid.value()
        self._manifest.snap_to_grid = self._snap.isChecked()
        self._manifest.export_settings.namespace = self._namespace.text().strip() or "ThemeStudio"
