"""Preview files that export will generate."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QPlainTextEdit,
    QSplitter,
    QVBoxLayout,
)

from juce_theme_studio.core.manifest import ThemeManifest
from juce_theme_studio.core.validation import ValidationReport
from juce_theme_studio.juce.exporter import preview_export_files


class ExportPreviewDialog(QDialog):
    def __init__(
        self,
        manifest: ThemeManifest,
        project_root: Path,
        validation: ValidationReport,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export Preview")
        self.setMinimumSize(640, 480)
        # Assign before wiring the list: setCurrentRow below fires
        # _show_detail synchronously, which reads these.
        self._manifest = manifest
        self._root = project_root

        layout = QVBoxLayout(self)
        files = preview_export_files(manifest, project_root)

        warn_count = len(validation.warnings)
        err_count = len(validation.errors)
        layout.addWidget(
            QLabel(
                f"{len(files)} file(s) will be written. "
                f"Validation: {err_count} error(s), {warn_count} warning(s)."
            )
        )

        split = QSplitter()
        self._list = QListWidget()
        for f in files:
            self._list.addItem(f)
        split.addWidget(self._list)

        self._detail = QPlainTextEdit()
        self._detail.setReadOnly(True)
        split.addWidget(self._detail)
        layout.addWidget(split)

        self._list.currentTextChanged.connect(self._show_detail)
        if files:
            self._list.setCurrentRow(0)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Export")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _show_detail(self, rel_path: str) -> None:
        if not rel_path:
            return
        full = self._root / rel_path
        if full.is_file():
            try:
                text = full.read_text(encoding="utf-8", errors="replace")
                self._detail.setPlainText(text[:8000])
                return
            except OSError:
                pass
        self._detail.setPlainText(f"Will create or overwrite:\n  {rel_path}")
