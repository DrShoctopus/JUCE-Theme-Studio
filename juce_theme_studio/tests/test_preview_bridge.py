"""Tests for live preview bridge helpers."""

from __future__ import annotations

from juce_theme_studio.juce.preview_bridge import LivePreviewBridge


def test_find_bundled_preview_missing(tmp_path) -> None:
    assert LivePreviewBridge.find_bundled_preview(tmp_path) is None
