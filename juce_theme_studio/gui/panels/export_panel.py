"""Export settings panel."""

from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from juce_theme_studio.core.manifest import ThemeManifest


class ExportPanel(QWidget):
    settings_changed = Signal()

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        box = QGroupBox("Export Settings")
        form = QFormLayout(box)

        self._json = QCheckBox("Export ThemeLayout.json")
        self._json.toggled.connect(self._emit)
        self._cpp = QCheckBox("Export C++ helpers")
        self._cpp.toggled.connect(self._emit)
        self._assets = QCheckBox("Copy assets")
        self._assets.toggled.connect(self._emit)
        form.addRow(self._json)
        form.addRow(self._cpp)
        form.addRow(self._assets)

        self._namespace = QLineEdit()
        self._namespace.editingFinished.connect(self._emit)
        form.addRow("Namespace", self._namespace)

        self._subdir = QLineEdit()
        self._subdir.editingFinished.connect(self._emit)
        form.addRow("Output subdir", self._subdir)

        layout.addWidget(box)
        layout.addStretch()

        self._manifest: ThemeManifest | None = None
        self._block = False

    def set_manifest(self, manifest: ThemeManifest | None) -> None:
        self._manifest = manifest
        self._block = True
        if manifest is None:
            self._block = False
            return
        s = manifest.export_settings
        self._json.setChecked(s.export_json)
        self._cpp.setChecked(s.export_cpp)
        self._assets.setChecked(s.copy_assets)
        self._namespace.setText(s.namespace)
        self._subdir.setText(s.output_subdir)
        self._block = False

    def _emit(self) -> None:
        if self._block or not self._manifest:
            return
        s = self._manifest.export_settings
        s.export_json = self._json.isChecked()
        s.export_cpp = self._cpp.isChecked()
        s.copy_assets = self._assets.isChecked()
        s.namespace = self._namespace.text().strip() or "ThemeStudio"
        s.output_subdir = self._subdir.text().strip() or "exports"
        self.settings_changed.emit()
