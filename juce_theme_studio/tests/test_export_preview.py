"""Tests for export preview."""

from __future__ import annotations

from juce_theme_studio.juce.exporter import preview_export_files


def test_preview_export_lists_files(fixture_project) -> None:
    from juce_theme_studio.core.project import load_project

    loaded = load_project(fixture_project)
    files = preview_export_files(loaded.manifest, fixture_project)
    assert any("ThemeLayout.json" in f for f in files)
    assert any("ThemeAssets.h" in f for f in files)
