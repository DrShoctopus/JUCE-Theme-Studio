"""Auto-mapping scanned JUCE controls to theme screens."""

from __future__ import annotations

from juce_theme_studio.core.controls import ControlMapping, create_control
from juce_theme_studio.core.manifest import Screen
from juce_theme_studio.core.types import ControlType
from juce_theme_studio.juce.scanner import DetectedScreen, ScanResult

_JUCE_TYPE_MAP: dict[str, ControlType] = {
    "juce::Slider": ControlType.KNOB,
    "juce::TextButton": ControlType.BUTTON,
    "juce::ToggleButton": ControlType.TOGGLE_BUTTON,
    "juce::ImageButton": ControlType.BUTTON,
    "juce::Label": ControlType.LABEL,
    "CustomKnob": ControlType.KNOB,
}


def apply_scanned_mappings(screen: Screen, detected: DetectedScreen) -> int:
    """Add placeholder controls for scanned C++ members not already mapped."""
    existing_vars = {
        c.mapping.cpp_variable for c in screen.controls if c.mapping.cpp_variable
    }
    added = 0
    for idx, det in enumerate(detected.controls):
        if det.cpp_variable in existing_vars:
            continue
        ctype = _JUCE_TYPE_MAP.get(det.juce_class, ControlType.STATIC_IMAGE)
        default_w = 64 if ctype != ControlType.LABEL else 120
        default_h = 64 if ctype != ControlType.LABEL else 24
        control = create_control(
            ctype,
            det.cpp_variable,
            x=det.x if det.x is not None else 50 + (idx % 5) * 70,
            y=det.y if det.y is not None else 50 + (idx // 5) * 70,
            width=det.width if det.width is not None else default_w,
            height=det.height if det.height is not None else default_h,
        )
        control.mapping = ControlMapping(
            juce_class=det.juce_class,
            cpp_variable=det.cpp_variable,
            screen_name=screen.name,
        )
        control.z_index = len(screen.controls)
        screen.controls.append(control)
        existing_vars.add(det.cpp_variable)
        added += 1
    return added


def sync_scan_mappings(manifest_screens: list[Screen], scan: ScanResult) -> int:
    """Match detected screens to manifest screens and apply mappings."""
    by_component = {d.class_name: d for d in scan.screens}
    total = 0
    for screen in manifest_screens:
        if not screen.juce_component:
            continue
        detected = by_component.get(screen.juce_component)
        if detected:
            total += apply_scanned_mappings(screen, detected)
    return total
