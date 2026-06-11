"""Tests for asset import."""

from __future__ import annotations

from pathlib import Path

from juce_theme_studio.core.assets import asset_exists, import_asset, resolve_asset_path
from juce_theme_studio.core.manifest import ThemeManifest
from juce_theme_studio.core.project import ensure_studio_dirs


def test_import_asset_copies_without_modifying_source(fixture_project: Path) -> None:
    ensure_studio_dirs(fixture_project)
    manifest = ThemeManifest()
    src = fixture_project / "Resources" / "background.png"
    mtime_before = src.stat().st_mtime

    entry = import_asset(manifest, fixture_project, src, name="Background")
    dest = resolve_asset_path(fixture_project, entry)

    assert dest.is_file()
    assert asset_exists(fixture_project, entry)
    assert src.stat().st_mtime == mtime_before
    assert entry.name == "Background"
    assert not entry.is_sprite_sheet
