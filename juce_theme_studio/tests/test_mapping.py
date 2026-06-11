"""Tests for scanner auto-mapping."""

from __future__ import annotations

from juce_theme_studio.core.manifest import Screen
from juce_theme_studio.core.mapping import apply_scanned_mappings, sync_scan_mappings
from juce_theme_studio.juce.scanner import DetectedControl, DetectedScreen, ScanResult


def test_apply_scanned_mappings_uses_setbounds() -> None:
    screen = Screen(id="s1", name="Main", juce_component="MainComponent")
    detected = DetectedScreen(
        id="d1",
        name="MainComponent",
        class_name="MainComponent",
        source_file="Source/MainComponent.cpp",
        controls=[
            DetectedControl("gainSlider", "juce::Slider", 10, 100, 200, 64, 64),
        ],
    )
    apply_scanned_mappings(screen, detected)
    assert screen.controls[0].x == 100
    assert screen.controls[0].y == 200
    assert screen.controls[0].width == 64


def test_apply_scanned_mappings() -> None:
    screen = Screen(id="s1", name="Main", juce_component="MainComponent")
    detected = DetectedScreen(
        id="d1",
        name="MainComponent",
        class_name="MainComponent",
        source_file="Source/MainComponent.cpp",
        controls=[
            DetectedControl("gainSlider", "juce::Slider", 10),
            DetectedControl("bypassButton", "juce::TextButton", 20),
        ],
    )
    added = apply_scanned_mappings(screen, detected)
    assert added == 2
    assert {c.mapping.cpp_variable for c in screen.controls} == {"gainSlider", "bypassButton"}


def test_sync_skips_duplicates() -> None:
    screen = Screen(id="s1", name="Main", juce_component="MainComponent")
    from juce_theme_studio.core.controls import create_control
    from juce_theme_studio.core.types import ControlType

    existing = create_control(ControlType.KNOB, "gainSlider", 0, 0, 64, 64)
    existing.mapping.cpp_variable = "gainSlider"
    screen.controls.append(existing)

    scan = ScanResult(
        project_root=".",
        screens=[
            DetectedScreen(
                id="d1", name="Main", class_name="MainComponent",
                source_file="x.cpp",
                controls=[DetectedControl("gainSlider", "juce::Slider", 1)],
            )
        ],
    )
    assert sync_scan_mappings([screen], scan) == 0
    assert len(screen.controls) == 1
