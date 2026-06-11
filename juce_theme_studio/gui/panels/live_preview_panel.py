"""Live preview controls: auto-export + optional JUCE binary."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from juce_theme_studio.juce.preview_bridge import LivePreviewBridge


class LivePreviewPanel(QWidget):
    toggled = Signal(bool)

    def __init__(self, bridge: LivePreviewBridge) -> None:
        super().__init__()
        self._bridge = bridge
        layout = QVBoxLayout(self)
        box = QGroupBox("Live JUCE Preview")
        form = QFormLayout(box)

        self._enable = QCheckBox("Auto-export on edit (debounced)")
        self._enable.toggled.connect(self._on_toggle)
        form.addRow(self._enable)

        self._binary = QLineEdit()
        self._binary.setPlaceholderText("Path to JuceLivePreview binary (optional)")
        browse = QPushButton("Browse…")
        browse.clicked.connect(self._browse_binary)
        form.addRow("JUCE binary", self._binary)

        self._status = QLabel("Disabled")
        self._status.setWordWrap(True)
        form.addRow("Status", self._status)

        layout.addWidget(box)
        layout.addStretch()

        bridge.status_changed.connect(self._status.setText)
        bridge.exported.connect(lambda p: self._status.setText(f"Live export: {p}"))
        bridge.error.connect(lambda e: self._status.setText(f"Error: {e}"))

    def _on_toggle(self, checked: bool) -> None:
        path = Path(self._binary.text()) if self._binary.text().strip() else None
        if path and path.is_file():
            self._bridge.set_external_binary(path)
        self._bridge.set_enabled(checked)
        self.toggled.emit(checked)

    def _browse_binary(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "JUCE Preview Binary", "")
        if path:
            self._binary.setText(path)
            self._bridge.set_external_binary(Path(path))

    def set_suggested_binary(self, path: Path | None) -> None:
        if path and path.is_file():
            self._binary.setText(str(path))
