"""Tests for AST scanner backends."""

from __future__ import annotations

from juce_theme_studio.juce.scanner import scan_juce_project
from juce_theme_studio.juce.scanner_ast import (
    analyze_with_ast,
    libclang_available,
    treesitter_available,
)


def test_backend_flags() -> None:
    assert isinstance(treesitter_available(), bool)
    assert isinstance(libclang_available(), bool)


def test_analyze_mock_project(fixture_project) -> None:
    cpp = fixture_project / "Source" / "MainComponent.cpp"
    screen = analyze_with_ast(cpp, fixture_project)
    if treesitter_available() or libclang_available():
        assert screen is not None
        assert screen.class_name == "MainComponent"
    else:
        assert screen is None


def test_scan_still_finds_main_component(fixture_project) -> None:
    result = scan_juce_project(fixture_project)
    assert any(s.class_name == "MainComponent" for s in result.screens)
