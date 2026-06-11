"""Tests for theme diffing."""

from __future__ import annotations

import json
from pathlib import Path

from juce_theme_studio.core.controls import create_control
from juce_theme_studio.core.manifest import Screen, ThemeManifest
from juce_theme_studio.core.theme_diff import diff_against_backup, diff_manifests
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


def test_diff_against_backup_detects_removed_control(tmp_path: Path) -> None:
    studio = tmp_path / ".juce_theme_studio"
    backup = studio / "backups" / "export_test"
    backup.mkdir(parents=True)
    layout = {
        "screens": [
            {
                "name": "Main",
                "controls": [
                    {"name": "Gain", "bounds": {"x": 10, "y": 10, "width": 64, "height": 64}},
                ],
            }
        ]
    }
    (backup / "ThemeLayout.json").write_text(json.dumps(layout), encoding="utf-8")

    knob = create_control(ControlType.KNOB, "Gain", 10, 10, 64, 64)
    manifest = ThemeManifest(screens=[Screen(id="s", name="Main", controls=[knob])])
    manifest.save(studio / "theme_project.json")

    report = diff_against_backup(tmp_path)
    assert report is not None
    assert not report.has_changes

    manifest.screens[0].controls.clear()
    manifest.save(studio / "theme_project.json")
    report = diff_against_backup(tmp_path)
    assert report is not None
    assert any(
        e.action == "removed" and e.category == "control" and "Gain" in e.path
        for e in report.entries
    )
