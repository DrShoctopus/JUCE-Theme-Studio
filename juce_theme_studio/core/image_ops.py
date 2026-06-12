"""Non-destructive image operations on library assets."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw

# Flood-fill threshold for the border background, and a tighter global pass that
# mops up isolated near-background specks left by grungy/distressed artwork.
DEFAULT_TOLERANCE = 60
DEFAULT_CLEANUP_TOLERANCE = 30


def _corner_color(img: Image.Image) -> tuple[int, int, int]:
    """Median background colour sampled from the four corners."""
    w, h = img.size
    pts = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
    chans = list(zip(*(img.getpixel(p)[:3] for p in pts)))
    return tuple(sorted(c)[len(c) // 2] for c in chans)  # type: ignore[return-value]


def make_background_transparent(
    path: Path,
    *,
    key_color: tuple[int, int, int] | None = None,
    tolerance: int = DEFAULT_TOLERANCE,
    cleanup_tolerance: int = DEFAULT_CLEANUP_TOLERANCE,
) -> int:
    """Knock the solid background colour out to transparent, in place.

    A flood fill seeded from every corner removes the background *connected to
    the edges* (keeping interior detail), then a tight global pass clears any
    remaining specks within ``cleanup_tolerance`` of the background colour.
    Operates on the library copy only; returns the number of pixels cleared.
    """
    img = Image.open(path).convert("RGBA")
    rgb = img.convert("RGB")
    key = key_color if key_color is not None else _corner_color(rgb)

    sentinel = (1, 254, 1)  # unlikely to occur in real artwork
    w, h = img.size
    for corner in ((0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)):
        if _within(rgb.getpixel(corner), key, tolerance):
            ImageDraw.floodfill(rgb, corner, sentinel, thresh=tolerance)

    rgb_bytes = rgb.tobytes()
    alpha = bytearray(img.getchannel("A").tobytes())
    kr, kg, kb = key
    cleared = 0
    for i in range(w * h):
        if alpha[i] == 0:
            continue
        j = 3 * i
        r, g, b = rgb_bytes[j], rgb_bytes[j + 1], rgb_bytes[j + 2]
        near_key = abs(r - kr) + abs(g - kg) + abs(b - kb) <= cleanup_tolerance
        if (r, g, b) == sentinel or near_key:
            alpha[i] = 0
            cleared += 1

    img.putalpha(Image.frombytes("L", img.size, bytes(alpha)))
    img.save(path, format="PNG")
    return cleared


def _within(c: tuple[int, ...], key: tuple[int, int, int], tol: int) -> bool:
    return sum(abs(a - b) for a, b in zip(c[:3], key)) <= tol
