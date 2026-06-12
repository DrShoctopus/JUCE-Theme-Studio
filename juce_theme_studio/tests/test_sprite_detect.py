"""Tests for sprite sheet auto-detection."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from juce_theme_studio.core.sprite_detect import (
    _detect_pillow,
    detect_sprite_sheet,
    opencv_available,
)


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


def test_pillow_detect_gap_packed_grid(tmp_path: Path) -> None:
    # Frames packed edge-to-edge with no transparent gaps (e.g. a 3x2 grid of
    # 40px frames). gcd(120, 80) == 40 -> the gcd grid heuristic must find it.
    path = tmp_path / "packed.png"
    Image.new("RGBA", (120, 80), (10, 20, 30, 255)).save(path)
    result = _detect_pillow(path)
    assert (result.frame_width, result.frame_height) == (40, 40)
    assert (result.columns, result.rows, result.frame_count) == (3, 2, 6)
    assert result.layout == "grid"


def test_pillow_detects_nonsquare_frames_by_gap(tmp_path: Path) -> None:
    # Two wide frames separated by a transparent gap (an OFF/ON button strip).
    # The square-size heuristics would mis-slice this; gap detection must not.
    img = Image.new("RGBA", (120, 40), (0, 0, 0, 0))
    for cx in (25, 95):
        for y in range(5, 35):
            for x in range(cx - 15, cx + 15):
                img.putpixel((x, y), (200, 80, 40, 255))
    path = tmp_path / "offon.png"
    img.save(path)
    result = _detect_pillow(path)
    assert (result.columns, result.rows, result.frame_count) == (2, 1, 2)
    assert result.frame_width == 60  # half of 120, not a square 40


def test_pillow_does_not_split_single_square_image(tmp_path: Path) -> None:
    # A single square control image must stay one frame, not be over-split.
    path = tmp_path / "knob.png"
    Image.new("RGBA", (132, 132), (10, 20, 30, 255)).save(path)
    result = _detect_pillow(path)
    assert result.frame_count == 1


def test_opencv_availability_is_bool() -> None:
    assert isinstance(opencv_available(), bool)
