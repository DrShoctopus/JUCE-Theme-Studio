"""Tests for background-removal image op."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from juce_theme_studio.core.image_ops import make_background_transparent


def test_removes_solid_border_keeps_interior(tmp_path: Path) -> None:
    # White background with an opaque coloured square in the middle.
    img = Image.new("RGB", (40, 40), (255, 255, 255))
    for y in range(12, 28):
        for x in range(12, 28):
            img.putpixel((x, y), (200, 40, 40))
    path = tmp_path / "btn.png"
    img.save(path)

    cleared = make_background_transparent(path)
    assert cleared > 0

    out = Image.open(path).convert("RGBA")
    assert out.getpixel((0, 0))[3] == 0      # background corner cleared
    assert out.getpixel((20, 20))[3] == 255  # interior art preserved


def test_no_uniform_background_clears_nothing(tmp_path: Path) -> None:
    # A photo-like gradient has no solid border colour to flood from.
    img = Image.new("RGB", (32, 32))
    for y in range(32):
        for x in range(32):
            img.putpixel((x, y), (x * 8 % 256, y * 8 % 256, 90))
    path = tmp_path / "grad.png"
    img.save(path)

    # The corners differ from each other, so little/nothing should be cleared.
    cleared = make_background_transparent(path, tolerance=5, cleanup_tolerance=2)
    assert cleared <= 4
