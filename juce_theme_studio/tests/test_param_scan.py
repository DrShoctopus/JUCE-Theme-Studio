"""Tests for APVTS parameter-id scanning and attachment-driven mapping."""

from __future__ import annotations

from juce_theme_studio.core.manifest import Screen
from juce_theme_studio.core.mapping import apply_scanned_mappings
from juce_theme_studio.juce.scanner import DetectedControl, DetectedScreen, extract_parameters

PROCESSOR_CPP = """
juce::AudioProcessorValueTreeState::ParameterLayout createLayout()
{
    std::vector<std::unique_ptr<juce::RangedAudioParameter>> params;
    params.push_back (std::make_unique<juce::AudioParameterFloat> (
        "gain", "Gain", 0.0f, 1.0f, 0.5f));
    params.push_back (std::make_unique<juce::AudioParameterFloat> (
        juce::ParameterID { "tone", 1 }, "Tone", 0.0f, 1.0f, 0.5f));
    params.push_back (std::make_unique<juce::AudioParameterBool> (
        "bypass", "Bypass", false));
    return { params.begin(), params.end() };
}
"""

EDITOR_CPP = """
gainAttachment = std::make_unique<juce::AudioProcessorValueTreeState::SliderAttachment> (
    apvts, "gain", gainSlider);
toneAttachment.reset (new SliderAttachment (state, "tone", toneKnob));
bypassAttachment = std::make_unique<ButtonAttachment> (apvts, "bypass", bypassButton);
"""


def test_extract_parameter_definitions() -> None:
    ids, attachments = extract_parameters(PROCESSOR_CPP)
    assert set(ids) == {"gain", "tone", "bypass"}
    assert attachments == {}


def test_extract_attachments_map_variables_to_params() -> None:
    ids, attachments = extract_parameters(EDITOR_CPP)
    assert attachments == {
        "gainSlider": "gain",
        "toneKnob": "tone",
        "bypassButton": "bypass",
    }
    assert set(ids) == {"gain", "tone", "bypass"}


def test_apply_scanned_mappings_fills_parameter_id() -> None:
    screen = Screen(id="s1", name="Main")
    detected = DetectedScreen(
        id="s1", name="Main", class_name="MainComponent", source_file="Main.cpp",
        controls=[
            DetectedControl("gainSlider", "juce::Slider", 1),
            DetectedControl("bypassButton", "juce::TextButton", 2),
        ],
    )
    attachments = {"gainSlider": "gain", "bypassButton": "bypass"}

    added = apply_scanned_mappings(screen, detected, attachments)
    assert added == 2
    by_var = {c.mapping.cpp_variable: c.mapping.parameter_id for c in screen.controls}
    assert by_var == {"gainSlider": "gain", "bypassButton": "bypass"}


def test_backfill_existing_control_parameter_id() -> None:
    screen = Screen(id="s1", name="Main")
    detected = DetectedScreen(
        id="s1", name="Main", class_name="MainComponent", source_file="Main.cpp",
        controls=[DetectedControl("gainSlider", "juce::Slider", 1)],
    )
    # Pre-existing control already mapped to the variable but without a param id.
    apply_scanned_mappings(screen, detected, {})
    assert screen.controls[0].mapping.parameter_id == ""

    # A later scan discovers the attachment; the empty id gets backfilled.
    apply_scanned_mappings(screen, detected, {"gainSlider": "gain"})
    assert screen.controls[0].mapping.parameter_id == "gain"
