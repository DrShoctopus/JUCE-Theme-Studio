"""Tests for validation."""

from __future__ import annotations

from pathlib import Path

from juce_theme_studio.core.controls import create_control
from juce_theme_studio.core.manifest import Screen, ThemeManifest
from juce_theme_studio.core.types import ControlType
from juce_theme_studio.core.validation import validate_manifest


def test_validation_warnings(fixture_project: Path) -> None:
    manifest = ThemeManifest(
        screens=[
            Screen(
                id="s1",
                name="Test",
                canvas_width=100,
                canvas_height=100,
                controls=[
                    create_control(ControlType.KNOB, "", 90, 90, 50, 50),
                    create_control(ControlType.KNOB, "dup", 0, 0, 20, 20),
                    create_control(ControlType.KNOB, "dup", 0, 0, 20, 20),
                ],
            )
        ],
    )
    report = validate_manifest(manifest, fixture_project)
    assert report.warnings
    assert any("no name" in w.message.lower() or "Duplicate" in w.message for w in report.warnings)


def test_validation_rejects_export_subdir_traversal(fixture_project: Path) -> None:
    manifest = ThemeManifest()
    manifest.export_settings.output_subdir = "../outside"

    report = validate_manifest(manifest, fixture_project)

    assert any("output subdir" in e.message.lower() for e in report.errors)


def test_validation_warns_for_negative_control_bounds(fixture_project: Path) -> None:
    control = create_control(ControlType.KNOB, "Lost", -200, -10, 50, 50)
    manifest = ThemeManifest(
        screens=[
            Screen(
                id="s1",
                name="Main",
                canvas_width=100,
                canvas_height=100,
                controls=[control],
            )
        ]
    )

    report = validate_manifest(manifest, fixture_project)

    assert any("outside canvas" in w.message.lower() for w in report.warnings)
