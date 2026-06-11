"""Tests for importing scanned project images into the asset library."""

from __future__ import annotations

from pathlib import Path

from juce_theme_studio.core.assets import import_project_assets, is_asset_imported
from juce_theme_studio.core.manifest import ThemeManifest
from juce_theme_studio.core.project import ensure_studio_dirs
from juce_theme_studio.juce.scanner import scan_juce_project


def test_import_project_assets_copies_images(fixture_project: Path) -> None:
    ensure_studio_dirs(fixture_project)
    manifest = ThemeManifest()
    scan = scan_juce_project(fixture_project)

    imported = import_project_assets(manifest, fixture_project, scan.image_assets)

    assert len(imported) == len(scan.image_assets)
    assert len(manifest.assets) == len(scan.image_assets)
    for entry in imported:
        assert is_asset_imported(manifest, fixture_project, entry.original_source)
        assert (fixture_project / ".juce_theme_studio" / entry.relative_path).is_file()


def test_import_project_assets_skips_duplicates(fixture_project: Path) -> None:
    ensure_studio_dirs(fixture_project)
    manifest = ThemeManifest()
    scan = scan_juce_project(fixture_project)

    first = import_project_assets(manifest, fixture_project, scan.image_assets)
    second = import_project_assets(manifest, fixture_project, scan.image_assets)

    assert len(first) == len(scan.image_assets)
    assert second == []
    assert len(manifest.assets) == len(scan.image_assets)


def test_import_project_assets_detects_sprite_strips(fixture_project: Path) -> None:
    ensure_studio_dirs(fixture_project)
    manifest = ThemeManifest()
    scan = scan_juce_project(fixture_project)

    imported = import_project_assets(manifest, fixture_project, scan.image_assets)
    sprite_entries = [e for e in imported if e.is_sprite_sheet]

    assert sprite_entries, "Expected wide strip images to be flagged as sprite sheets"
