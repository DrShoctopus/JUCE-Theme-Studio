"""Tests for asset import."""

from __future__ import annotations

from pathlib import Path

from juce_theme_studio.core.assets import (
    asset_exists,
    delete_asset,
    get_asset_usages,
    import_asset,
    resolve_asset_path,
    unimported_project_images,
)
from juce_theme_studio.core.controls import create_control
from juce_theme_studio.core.manifest import Screen, ThemeManifest
from juce_theme_studio.core.project import ensure_studio_dirs
from juce_theme_studio.core.types import ControlType


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


def test_delete_asset_removes_file(fixture_project: Path) -> None:
    ensure_studio_dirs(fixture_project)
    manifest = ThemeManifest()
    src = fixture_project / "Resources" / "background.png"
    entry = import_asset(manifest, fixture_project, src)
    dest = resolve_asset_path(fixture_project, entry)

    deleted = delete_asset(manifest, fixture_project, entry.id)

    assert deleted is entry
    assert manifest.assets == []
    assert not dest.is_file()


def test_delete_asset_clears_references(fixture_project: Path) -> None:
    ensure_studio_dirs(fixture_project)
    manifest = ThemeManifest()
    entry = import_asset(
        manifest, fixture_project, fixture_project / "Resources" / "background.png",
    )
    screen = Screen(id="s1", name="Main", canvas_width=800, canvas_height=600)
    screen.background_asset_id = entry.id
    control = create_control(ControlType.KNOB, "Knob", 10, 10, 64, 64, entry.id)
    screen.controls.append(control)
    manifest.screens.append(screen)

    assert get_asset_usages(manifest, entry.id)
    delete_asset(manifest, fixture_project, entry.id, clear_references=True)

    assert screen.background_asset_id is None
    assert control.asset_id is None


def test_unimported_project_images(fixture_project: Path) -> None:
    ensure_studio_dirs(fixture_project)
    manifest = ThemeManifest()
    from juce_theme_studio.juce.scanner import scan_juce_project

    scan = scan_juce_project(fixture_project)
    unimported = unimported_project_images(manifest, fixture_project, scan.image_assets)
    assert unimported == scan.image_assets

    import_asset(manifest, fixture_project, fixture_project / "Resources" / "background.png")
    remaining = unimported_project_images(manifest, fixture_project, scan.image_assets)
    assert "Resources/background.png" in scan.image_assets
    assert "Resources/background.png" not in remaining
    assert len(remaining) == len(scan.image_assets) - 1
