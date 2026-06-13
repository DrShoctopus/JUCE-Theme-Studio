"""Tests for live preview bridge helpers."""

from __future__ import annotations

from typing import Any, cast

from PySide6.QtCore import QProcess

from juce_theme_studio.core.manifest import ThemeManifest
from juce_theme_studio.juce.preview_bridge import LivePreviewBridge


def test_find_bundled_preview_missing(tmp_path) -> None:
    assert LivePreviewBridge.find_bundled_preview(tmp_path) is None


def test_layout_export_path_rejects_traversal_subdir(tmp_path) -> None:
    manifest = ThemeManifest()
    manifest.export_settings.output_subdir = "../outside"
    bridge = LivePreviewBridge()
    bridge.configure(tmp_path, manifest)

    assert bridge.layout_export_path() is None


def test_running_external_preview_reuses_layout_polling_without_ipc(tmp_path) -> None:
    binary = tmp_path / "JuceLivePreview"
    binary.write_text("#!/bin/sh\n", encoding="utf-8")
    layout_dir = tmp_path / "exports"
    layout_dir.mkdir()
    layout = layout_dir / "ThemeLayout.json"
    layout.write_text("{}", encoding="utf-8")

    class RunningProcess:
        def state(self) -> QProcess.ProcessState:
            return QProcess.ProcessState.Running

    bridge = LivePreviewBridge()
    cast(Any, bridge)._external_path = binary
    cast(Any, bridge)._process = RunningProcess()
    statuses: list[str] = []
    bridge.status_changed.connect(statuses.append)

    cast(Any, bridge)._sync_external(layout)

    assert not (layout_dir / ".live_preview_ipc.json").exists()
    assert statuses == ["Updated ThemeLayout.json"]
