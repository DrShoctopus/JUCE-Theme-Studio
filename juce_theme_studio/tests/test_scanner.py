"""Tests for JUCE project scanner."""

from __future__ import annotations

from pathlib import Path

from juce_theme_studio.juce.scanner import scan_juce_project


def test_scan_mock_project(fixture_project: Path) -> None:
    result = scan_juce_project(fixture_project)
    assert result.jucer_files
    assert result.cmake_files
    assert "Source" in result.source_dirs
    assert result.image_assets
    assert any(s.class_name == "MainComponent" for s in result.screens)

    main = next(s for s in result.screens if s.class_name == "MainComponent")
    assert main.suggested_width == 800
    assert main.suggested_height == 600
    assert any(c.cpp_variable == "gainSlider" for c in main.controls)
