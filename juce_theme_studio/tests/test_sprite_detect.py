"""Tests for sprite sheet auto-detection."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from juce_theme_studio.core.sprite_detect import detect_sprite_sheet, opencv_available


def test_pillow_detect_horizontal_strip(tmp_path: Path) -> None:
    img = Image.new("RGBA", (256, 64), (0, 0, 0, 0))
    for i in range(4):
        for x in range(64):
            img.putpixel((i * 64 + x, 32), (255, 0, 0, 255))
    path = tmp_path / "strip.png"
    img.save(path)
    result = detect_sprite_sheet(path)
    assert result.frame_count >= 4
    assert result.method in ("pillow", "opencv")


def test_pillow_detect_vertical_strip(tmp_path: Path) -> None:
    img = Image.new("RGBA", (64, 256), (0, 0, 0, 0))
    path = tmp_path / "vertical.png"
    img.save(path)
    result = detect_sprite_sheet(path)
    assert result.layout == "vertical_strip"
    assert result.frame_count == 4


def test_opencv_availability_is_bool() -> None:
    assert isinstance(opencv_available(), bool)
