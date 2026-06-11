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
    "juce::DrawableButton": ControlType.BUTTON,
    "juce::ComboBox": ControlType.BUTTON,
    "juce::Label": ControlType.LABEL,
    "CustomKnob": ControlType.KNOB,
}


def apply_scanned_mappings(
    screen: Screen,
    detected: DetectedScreen,
    attachments: dict[str, str] | None = None,
) -> int:
    """Add placeholder controls for scanned C++ members not already mapped.

    ``attachments`` maps a component's C++ variable to its APVTS parameter id
    (from ``*Attachment`` constructors); matching controls get their
    ``parameter_id`` filled in automatically.
    """
    attachments = attachments or {}
    existing_vars = {
        c.mapping.cpp_variable for c in screen.controls if c.mapping.cpp_variable
    }
    added = 0
    for idx, det in enumerate(detected.controls):
        if det.cpp_variable in existing_vars:
            continue
        ctype = _JUCE_TYPE_MAP.get(det.juce_class, ControlType.STATIC_IMAGE)
        control = create_control(
            ctype,
            det.cpp_variable,
            x=50 + (idx % 5) * 70,
            y=50 + (idx // 5) * 70,
            width=64 if ctype != ControlType.LABEL else 120,
            height=64 if ctype != ControlType.LABEL else 24,
        )
        control.mapping = ControlMapping(
            juce_class=det.juce_class,
            cpp_variable=det.cpp_variable,
            parameter_id=attachments.get(det.cpp_variable, ""),
            screen_name=screen.name,
        )
        control.z_index = len(screen.controls)
        screen.controls.append(control)
        existing_vars.add(det.cpp_variable)
        added += 1

    _backfill_parameter_ids(screen, attachments)
    return added


def _backfill_parameter_ids(screen: Screen, attachments: dict[str, str]) -> int:
    """Fill empty parameter_id on existing controls from detected attachments."""
    filled = 0
    for control in screen.controls:
        var = control.mapping.cpp_variable
        if var and not control.mapping.parameter_id and var in attachments:
            control.mapping.parameter_id = attachments[var]
            filled += 1
    return filled


def sync_scan_mappings(manifest_screens: list[Screen], scan: ScanResult) -> int:
    """Match detected screens to manifest screens and apply mappings."""
    by_component = {d.class_name: d for d in scan.screens}
    total = 0
    for screen in manifest_screens:
        if not screen.juce_component:
            continue
        detected = by_component.get(screen.juce_component)
        if detected:
            total += apply_scanned_mappings(screen, detected, scan.attachments)
    return total
