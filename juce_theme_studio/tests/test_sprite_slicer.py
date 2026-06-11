"""Tests for sprite sheet slicing into library."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from juce_theme_studio.core.assets import asset_exists
from juce_theme_studio.core.manifest import ThemeManifest
from juce_theme_studio.core.sprite_slicer import slice_sprite_sheet_to_library
from juce_theme_studio.core.sprites import SpriteConfig
from juce_theme_studio.core.types import SpriteLayout


def test_slice_sprite_sheet_creates_frame_assets(tmp_path: Path) -> None:
    img = Image.new("RGBA", (256, 64), (0, 0, 0, 0))
    for i in range(4):
        for x in range(64):
            img.putpixel((i * 64 + x, 32), (255, 0, 0, 255))
    sheet = tmp_path / "knob_strip.png"
    img.save(sheet)

    manifest = ThemeManifest()
    cfg = SpriteConfig(
        layout=SpriteLayout.HORIZONTAL_STRIP,
        frame_width=64,
        frame_height=64,
        frame_count=4,
        columns=4,
    )
    entries = slice_sprite_sheet_to_library(
        manifest, tmp_path, sheet, cfg, base_name="knob",
    )
    assert len(entries) == 4
    assert len(manifest.assets) == 4
    for entry in entries:
        assert entry.name.startswith("knob_frame_")
        assert not entry.is_sprite_sheet
        assert asset_exists(tmp_path, entry)
