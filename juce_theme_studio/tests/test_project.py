"""Tests for project load/save."""

from __future__ import annotations

from pathlib import Path

from juce_theme_studio.core.project import create_manual_screen, load_project, save_project
from juce_theme_studio.core.types import STUDIO_DIR


def test_load_creates_studio_dir(fixture_project: Path) -> None:
    loaded = load_project(fixture_project)
    assert loaded.studio_dir.is_dir()
    assert (loaded.studio_dir / "assets").is_dir()
    assert loaded.manifest.screens
    assert any(s.juce_component == "MainComponent" for s in loaded.manifest.screens)

    create_manual_screen(loaded.manifest, "CustomPanel", 400, 300)
    save_project(loaded)

    reloaded = load_project(fixture_project)
    assert any(s.name == "CustomPanel" for s in reloaded.manifest.screens)
    assert (fixture_project / STUDIO_DIR / "theme_project.json").is_file()
