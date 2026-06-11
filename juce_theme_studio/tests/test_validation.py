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
