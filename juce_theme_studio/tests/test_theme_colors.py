"""Tests for the theme colour palette: manifest round-trip and hex conversion."""

from __future__ import annotations

from juce_theme_studio.core.manifest import DEFAULT_THEME_COLORS, ThemeManifest


def test_manifest_defaults_and_round_trip() -> None:
    m = ThemeManifest()
    assert m.theme_colors == DEFAULT_THEME_COLORS
    assert m.theme_colors is not DEFAULT_THEME_COLORS  # independent copy

    m.theme_colors["primary"] = "ffaabbcc"
    restored = ThemeManifest.from_dict(m.to_dict())
    assert restored.theme_colors["primary"] == "ffaabbcc"
    # Missing keys fall back to defaults.
    assert restored.theme_colors["background"] == DEFAULT_THEME_COLORS["background"]


def test_partial_colors_merge_with_defaults() -> None:
    restored = ThemeManifest.from_dict({"theme_colors": {"text": "ff112233"}})
    assert restored.theme_colors["text"] == "ff112233"
    assert restored.theme_colors["meter"] == DEFAULT_THEME_COLORS["meter"]


def test_hex_qcolor_conversion_round_trip() -> None:
    from juce_theme_studio.gui.dialogs.theme_colors_dialog import hex_to_qcolor, qcolor_to_hex

    for value in ("ff1e1e1e", "8061afef", "ffffffff", "00000000"):
        assert qcolor_to_hex(hex_to_qcolor(value)) == value

    # 6-digit hex is treated as fully opaque.
    assert qcolor_to_hex(hex_to_qcolor("61afef")) == "ff61afef"
