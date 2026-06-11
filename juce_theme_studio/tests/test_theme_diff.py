"""Tests for theme diffing."""

from __future__ import annotations

from juce_theme_studio.core.controls import create_control
from juce_theme_studio.core.manifest import Screen, ThemeManifest
from juce_theme_studio.core.theme_diff import diff_manifests
from juce_theme_studio.core.types import ControlType


def test_diff_detects_added_screen() -> None:
    left = ThemeManifest(screens=[Screen(id="a", name="A")])
    right = ThemeManifest(
        screens=[Screen(id="a", name="A"), Screen(id="b", name="B")],
    )
    report = diff_manifests(left, right)
    assert report.has_changes
    assert any(e.action == "added" and e.category == "screen" for e in report.entries)


def test_diff_detects_moved_control() -> None:
    c1 = create_control(ControlType.KNOB, "Gain", 10, 10, 64, 64)
    c2 = create_control(ControlType.KNOB, "Gain", 50, 50, 64, 64)
    left = ThemeManifest(screens=[Screen(id="s", name="Main", controls=[c1])])
    right = ThemeManifest(screens=[Screen(id="s", name="Main", controls=[c2])])
    report = diff_manifests(left, right)
    assert any(e.action == "changed" and e.category == "control" for e in report.entries)
