"""Tests for JUCE project scanner."""

from __future__ import annotations

from pathlib import Path

from juce_theme_studio.juce.scanner import scan_juce_project


def test_scan_mock_project(fixture_project: Path) -> None:
    result = scan_juce_project(fixture_project)
    assert result.jucer_files
    assert result.cmake_files
    assert "Source" in result.source_dirs
    assert result.image_assets
    assert any(s.class_name == "MainComponent" for s in result.screens)

    main = next(s for s in result.screens if s.class_name == "MainComponent")
    assert main.suggested_width == 800
    assert main.suggested_height == 600
    assert any(c.cpp_variable == "gainSlider" for c in main.controls)


# A project that organises screens as subclasses of a shared, custom Component
# base (the TRIPTYCH "PageBase" pattern), using `final`, `enum class`, and
# sibling widget classes that must NOT be reported as screens.
_PAGE_BASE_HEADER = """
#pragma once
#include <JuceHeader.h>

namespace L { constexpr int baseW = 1280; constexpr int baseH = 880; }

enum class Page { Pedals, Amp, CabPost };

class PageBase : public juce::Component
{
public:
    void paint(juce::Graphics&) override;
    void resized() override;
};

class PedalsPage final : public PageBase
{
private:
    juce::Slider driveSlider;
};

class AmpPage final : public PageBase
{
private:
    juce::Slider gainSlider;
};

class CabPostPage final : public PageBase, private juce::Timer
{
};

// A widget and a container that derive from juce::Component directly: neither
// is a "page", so neither should be detected as a screen.
class VuMeter final : public juce::Component, private juce::Timer {};

class ShellUI final : public juce::Component
{
public:
    ShellUI() { setSize(L::baseW, L::baseH); }
};
"""


def test_scan_detects_custom_page_base_subclasses(tmp_path: Path) -> None:
    src = tmp_path / "Source" / "ui"
    src.mkdir(parents=True)
    (src / "Pages.h").write_text(_PAGE_BASE_HEADER)

    result = scan_juce_project(tmp_path)
    names = {s.class_name for s in result.screens}

    # The three concrete pages are the screens...
    assert names == {"PedalsPage", "AmpPage", "CabPostPage"}
    # ...not the enum, the abstract base, the widget, or the container.
    assert "Page" not in names
    assert "PageBase" not in names
    assert "VuMeter" not in names
    assert "ShellUI" not in names

    # Canvas size is resolved through the int constants used by setSize().
    pedals = next(s for s in result.screens if s.class_name == "PedalsPage")
    assert (pedals.suggested_width, pedals.suggested_height) == (1280, 880)
    # Controls are scoped to each class body, not shared across pages.
    assert {c.cpp_variable for c in pedals.controls} == {"driveSlider"}


def test_ast_enhancement_does_not_readd_filtered_direct_component(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from juce_theme_studio.juce import scanner_ast
    from juce_theme_studio.juce.scanner import DetectedScreen

    src = tmp_path / "Source" / "ui"
    src.mkdir(parents=True)
    path = src / "Pages.h"
    path.write_text(_PAGE_BASE_HEADER)

    def fake_analyze(candidate: Path, root: Path) -> DetectedScreen | None:
        if candidate == path:
            return DetectedScreen(
                id="ast",
                name="ShellUI",
                class_name="ShellUI",
                source_file="Source/ui/Pages.h",
            )
        return None

    monkeypatch.setattr(scanner_ast, "analyze_with_ast", fake_analyze)

    result = scan_juce_project(tmp_path)

    assert {s.class_name for s in result.screens} == {
        "PedalsPage",
        "AmpPage",
        "CabPostPage",
    }


def test_scan_detects_audio_processor_editor_screen(tmp_path: Path) -> None:
    src = tmp_path / "Source"
    src.mkdir()
    (src / "PluginEditor.h").write_text(
        """
        #include <JuceHeader.h>
        class PluginEditor final : public juce::AudioProcessorEditor
        {
        public:
            PluginEditor() : juce::AudioProcessorEditor(nullptr) { setSize(640, 480); }
        private:
            juce::Slider gainSlider;
        };
        """,
        encoding="utf-8",
    )

    result = scan_juce_project(tmp_path)

    editor = next(s for s in result.screens if s.class_name == "PluginEditor")
    assert (editor.suggested_width, editor.suggested_height) == (640, 480)
    assert {c.cpp_variable for c in editor.controls} == {"gainSlider"}


def test_scan_merges_ast_controls_when_backend_reports_them(
    tmp_path: Path,
    monkeypatch,
) -> None:
    from juce_theme_studio.juce import scanner_ast
    from juce_theme_studio.juce.scanner import DetectedControl, DetectedScreen

    src = tmp_path / "Source"
    src.mkdir()
    path = src / "MainComponent.cpp"
    path.write_text(
        """
        #include <JuceHeader.h>
        class MainComponent : public juce::Component
        {
        public:
            MainComponent() { setSize(800, 600); }
        };
        """,
        encoding="utf-8",
    )
    calls: list[Path] = []

    def fake_analyze(candidate: Path, root: Path) -> DetectedScreen | None:
        calls.append(candidate)
        if candidate == path:
            return DetectedScreen(
                id="ast",
                name="MainComponent",
                class_name="MainComponent",
                source_file="Source/MainComponent.cpp",
                controls=[DetectedControl("modeBox", "juce::ComboBox", 12)],
            )
        return None

    monkeypatch.setattr(scanner_ast, "analyze_with_ast", fake_analyze)

    result = scan_juce_project(tmp_path)

    assert calls
    main = next(s for s in result.screens if s.class_name == "MainComponent")
    assert {c.cpp_variable for c in main.controls} == {"modeBox"}
