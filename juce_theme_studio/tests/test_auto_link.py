"""Tests for heuristic asset auto-linking."""

from __future__ import annotations

from pathlib import Path

from juce_theme_studio.core.assets import import_project_assets
from juce_theme_studio.core.auto_link import auto_link_project_assets
from juce_theme_studio.core.manifest import ThemeManifest
from juce_theme_studio.core.mapping import apply_scanned_mappings
from juce_theme_studio.core.project import ensure_studio_dirs
from juce_theme_studio.juce.scanner import DetectedControl, DetectedScreen, scan_juce_project


def test_auto_link_matches_mock_project_controls(fixture_project: Path) -> None:
    ensure_studio_dirs(fixture_project)
    manifest = ThemeManifest(project_root=".")
    scan = scan_juce_project(fixture_project)

    screen = manifest.screens[0] if manifest.screens else None
    if screen is None:
        from juce_theme_studio.core.manifest import Screen

        screen = Screen(id="s1", name="Main", juce_component="MainComponent")
        manifest.screens.append(screen)

    detected = next(s for s in scan.screens if s.class_name == "MainComponent")
    apply_scanned_mappings(screen, detected)

    imported = import_project_assets(manifest, fixture_project, scan.image_assets)
    assert len(imported) == 3

    linked = auto_link_project_assets(manifest, fixture_project)
    assert linked >= 2

    by_var = {c.mapping.cpp_variable: c for c in screen.controls}
    assert by_var["gainSlider"].asset_id is not None
    assert by_var["bypassButton"].asset_id is not None
    assert screen.background_asset_id is not None


def test_auto_link_uses_setbounds_positions(fixture_project: Path) -> None:
    manifest = ThemeManifest(project_root=".")
    screen = manifest.screens[0] if manifest.screens else None
    if screen is None:
        from juce_theme_studio.core.manifest import Screen

        screen = Screen(id="s1", name="Main", juce_component="MainComponent")
        manifest.screens.append(screen)

    detected = DetectedScreen(
        id="d1",
        name="MainComponent",
        class_name="MainComponent",
        source_file="Source/MainComponent.cpp",
        controls=[
            DetectedControl("gainSlider", "juce::Slider", 10, 100, 200, 64, 64),
            DetectedControl("bypassButton", "juce::TextButton", 20, 200, 200, 80, 32),
        ],
    )
    apply_scanned_mappings(screen, detected)

    gain = next(c for c in screen.controls if c.mapping.cpp_variable == "gainSlider")
    button = next(c for c in screen.controls if c.mapping.cpp_variable == "bypassButton")
    assert gain.x == 100 and gain.y == 200
    assert button.x == 200 and button.y == 200


def test_scanner_extracts_setbounds_from_mock_project(fixture_project: Path) -> None:
    scan = scan_juce_project(fixture_project)
    main = next(s for s in scan.screens if s.class_name == "MainComponent")
    by_var = {c.cpp_variable: c for c in main.controls}
    assert by_var["gainSlider"].x == 100
    assert by_var["gainSlider"].y == 200
    assert by_var["bypassButton"].width == 80
