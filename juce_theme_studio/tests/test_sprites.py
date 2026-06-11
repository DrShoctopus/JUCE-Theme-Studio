"""Tests for sprite sheet slicing."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from juce_theme_studio.core.sprites import (
    SpriteConfig,
    detect_sprite_grid,
    extract_frame,
    frame_index_for_value,
    frame_position,
)
from juce_theme_studio.core.types import SpriteLayout


def test_frame_index_for_value() -> None:
    cfg = SpriteConfig(frame_count=11, reversed=False)
    assert frame_index_for_value(cfg, 0.0) == 0
    assert frame_index_for_value(cfg, 1.0) == 10
    assert frame_index_for_value(cfg, 0.5) == 5

    cfg_rev = SpriteConfig(frame_count=11, reversed=True)
    assert frame_index_for_value(cfg_rev, 0.0) == 10


def test_frame_position_horizontal() -> None:
    cfg = SpriteConfig(
        layout=SpriteLayout.HORIZONTAL_STRIP,
        frame_width=64,
        frame_height=64,
        frame_count=8,
    )
    assert frame_position(cfg, 0) == (0, 0)
    assert frame_position(cfg, 3) == (192, 0)


def test_extract_frame(tmp_path: Path) -> None:
    img = Image.new("RGBA", (256, 64), (0, 0, 0, 0))
    for i in range(4):
        for x in range(64):
            img.putpixel((i * 64 + x, 32), (255, 0, 0, 255))
    path = tmp_path / "strip.png"
    img.save(path)

    cfg = SpriteConfig(
        layout=SpriteLayout.HORIZONTAL_STRIP,
        frame_count=4,
        frame_width=64,
        frame_height=64,
    )
    frame = extract_frame(path, cfg, 2)
    assert frame.size == (64, 64)
    assert frame.getpixel((32, 32))[0] == 255


def test_detect_sprite_grid(tmp_path: Path) -> None:
    img = Image.new("RGB", (512, 64))
    path = tmp_path / "knob.png"
    img.save(path)
    fw, fh, fc, cols = detect_sprite_grid(path)
    assert fw == 64
    assert fc == 8
