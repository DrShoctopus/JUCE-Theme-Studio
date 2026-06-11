"""Live preview bridge: debounced export + optional external JUCE preview process."""

from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from PySide6.QtCore import QObject, QProcess, QTimer, Signal

from juce_theme_studio.core.manifest import ThemeManifest
from juce_theme_studio.core.types import STUDIO_DIR
from juce_theme_studio.juce.exporter import export_theme

logger = logging.getLogger(__name__)

MIME_LAYOUT = "application/x-juce-theme-layout-path"


class LivePreviewBridge(QObject):
    """Auto-export theme layout and optionally launch/monitor a JUCE preview binary."""

    exported = Signal(str)
    status_changed = Signal(str)
    error = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._project_root: Path | None = None
        self._manifest: ThemeManifest | None = None
        self._enabled = False
        self._dirty = False
        self._external_path: Path | None = None
        self._process: QProcess | None = None

        self._timer = QTimer(self)
        self._timer.setInterval(800)
        self._timer.timeout.connect(self._on_tick)

    def configure(
        self,
        project_root: Path,
        manifest: ThemeManifest,
        *,
        external_binary: Path | None = None,
    ) -> None:
        self._project_root = project_root.resolve()
        self._manifest = manifest
        self._external_path = external_binary

    def set_external_binary(self, path: Path | None) -> None:
        """Update the JUCE preview binary path (e.g. after browse)."""
        self._external_path = path.resolve() if path else None
        if self._enabled and self._external_path and self._external_path.is_file():
            layout = self.layout_export_path()
            if layout and layout.is_file():
                self._sync_external(layout)

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        if enabled:
            self._timer.start()
            self.status_changed.emit("Live preview enabled")
            self.mark_dirty()
        else:
            self._timer.stop()
            self._stop_external()
            self.status_changed.emit("Live preview disabled")

    def mark_dirty(self) -> None:
        self._dirty = True

    def layout_export_path(self) -> Path | None:
        if self._project_root is None or self._manifest is None:
            return None
        sub = self._manifest.export_settings.output_subdir
        return self._project_root / STUDIO_DIR / sub / "ThemeLayout.json"

    def _on_tick(self) -> None:
        if not self._enabled or not self._dirty:
            return
        if self._project_root is None or self._manifest is None:
            return
        try:
            result = export_theme(self._manifest, self._project_root, force=True)
            layout = result.export_dir / "ThemeLayout.json"
            if layout.is_file():
                self.exported.emit(str(layout))
                self._dirty = False
                self.status_changed.emit(f"Exported {layout.name}")
                self._sync_external(layout)
        except Exception as exc:
            logger.exception("Live export failed")
            self.error.emit(str(exc))

    def _sync_external(self, layout_path: Path) -> None:
        if self._external_path is None or not self._external_path.is_file():
            return
        if self._process is None:
            self._process = QProcess(self)
            self._process.errorOccurred.connect(
                lambda: self.error.emit(self._process.errorString() if self._process else "")
            )

        if self._process.state() == QProcess.ProcessState.Running:
            self._write_ipc(layout_path)
            return

        self._process.start(str(self._external_path), [str(layout_path)])
        self.status_changed.emit(f"Launched JUCE preview: {self._external_path.name}")

    def _write_ipc(self, layout_path: Path) -> None:
        ipc = layout_path.parent / ".live_preview_ipc.json"
        ipc.write_text(
            json.dumps(
                {
                    "layout": str(layout_path),
                    "reload": True,
                    "mime": MIME_LAYOUT,
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def _stop_external(self) -> None:
        if self._process and self._process.state() == QProcess.ProcessState.Running:
            self._process.terminate()

    @staticmethod
    def find_bundled_preview(project_root: Path) -> Path | None:
        """Locate a user-built preview binary from examples/juce_live_preview."""
        studio_preview = (
            project_root.parent / "juce_theme_studio" / "examples"
            / "juce_live_preview" / "build" / "JuceLivePreview"
        )
        candidates = [
            project_root / "examples" / "juce_live_preview" / "build" / "JuceLivePreview",
            studio_preview,
            Path.home() / ".juce_theme_studio" / "JuceLivePreview",
        ]
        for c in candidates:
            if c.is_file():
                return c
        return None

    @staticmethod
    def try_launch_cli_preview(layout_path: Path, binary: Path) -> bool:
        """Fire-and-forget launch for tests/CLI."""
        if not binary.is_file() or not layout_path.is_file():
            return False
        try:
            subprocess.Popen([str(binary), str(layout_path)], start_new_session=True)
            return True
        except OSError:
            return False
