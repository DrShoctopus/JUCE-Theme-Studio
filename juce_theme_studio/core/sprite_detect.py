"""Sprite sheet frame detection using OpenCV (optional) or Pillow heuristics."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from PIL import Image, ImageChops

logger = logging.getLogger(__name__)

_opencv_available: bool | None = None


def opencv_available() -> bool:
    global _opencv_available
    if _opencv_available is None:
        try:
            import cv2  # noqa: F401

            _opencv_available = True
        except ImportError:
            _opencv_available = False
    return _opencv_available


@dataclass
class SpriteDetectionResult:
    frame_width: int
    frame_height: int
    frame_count: int
    columns: int
    rows: int
    layout: str  # horizontal_strip | vertical_strip | grid
    method: str  # opencv | pillow


def detect_sprite_sheet(image_path: Path) -> SpriteDetectionResult:
    """Auto-detect sprite frames; prefers OpenCV when installed."""
    pillow_result = _detect_pillow(image_path)
    if opencv_available():
        try:
            result = _detect_opencv(image_path)
            if result is not None and _should_prefer_opencv(result, pillow_result):
                return result
        except Exception as exc:
            logger.debug("OpenCV sprite detect failed: %s", exc)
    return pillow_result


def _should_prefer_opencv(
    opencv: SpriteDetectionResult,
    pillow: SpriteDetectionResult,
) -> bool:
    """Use OpenCV only when it finds real frame structure, not one full-image blob."""
    if opencv.frame_count > 1:
        return True
    return pillow.frame_count <= 1


def _grid_result(fw: int, fh: int, cols: int, rows: int) -> SpriteDetectionResult:
    if rows > 1 and cols > 1:
        layout = "grid"
    elif rows > 1 and cols == 1:
        layout = "vertical_strip"
    else:
        layout = "horizontal_strip"
    return SpriteDetectionResult(fw, fh, cols * rows, cols, rows, layout, "pillow")


def _divisors_desc(n: int) -> list[int]:
    return sorted((d for d in range(1, n + 1) if n % d == 0), reverse=True)


def _square_grid(w: int, h: int) -> tuple[int, int, int] | None:
    """Largest square frame size dividing both dimensions into 2..256 frames.

    Handles gap-packed atlases (e.g. 1448x1086 -> 362px 4x3 grid) that have no
    transparent separators for the projection-based detectors to find.
    """
    from math import gcd

    for s in _divisors_desc(gcd(w, h)):
        if s < 16 or s > min(w, h):
            continue
        cols, rows = w // s, h // s
        if 2 <= cols * rows <= 256:
            return s, cols, rows
    return None


def _content_bands(
    profile: list[int], thresh: int, min_gap: int, min_band: int
) -> list[tuple[int, int]]:
    """Contiguous runs where the 1D content profile is above ``thresh``.

    Runs separated by gaps smaller than ``min_gap`` are merged (within-frame
    slivers); runs shorter than ``min_band`` are dropped as noise.
    """
    runs: list[list[int]] = []
    start: int | None = None
    for i, v in enumerate(profile):
        if v > thresh and start is None:
            start = i
        elif v <= thresh and start is not None:
            runs.append([start, i])
            start = None
    if start is not None:
        runs.append([start, len(profile)])

    merged: list[list[int]] = []
    for r in runs:
        if merged and r[0] - merged[-1][1] < min_gap:
            merged[-1][1] = r[1]
        else:
            merged.append(r)
    return [(a, b) for a, b in merged if b - a >= min_band]


def _content_grid(img: Image.Image) -> tuple[int, int]:
    """(columns, rows) inferred from background gaps between frames.

    Uses the alpha channel when present, else the difference from the border
    background colour, then projects content onto each axis and counts the
    separated bands. Returns (1, 1) when no internal gaps are found.
    """
    rgba = img.convert("RGBA")
    w, h = rgba.size
    alpha = rgba.getchannel("A")
    alpha_extrema = cast(tuple[int, int], alpha.getextrema())
    if alpha_extrema[0] < 16:
        mask = alpha
    else:
        rgb = rgba.convert("RGB")
        bg = Image.new("RGB", (w, h), _corner_color(rgb))
        mask = ImageChops.difference(rgb, bg).convert("L")

    # Average the mask onto each axis (BOX resample does this in C). Use a
    # near-zero threshold so only *truly empty* background gaps split frames;
    # faint dips inside packed art (e.g. round knobs in an atlas) don't.
    col_profile = list(mask.resize((w, 1), Image.Resampling.BOX).tobytes())
    row_profile = list(mask.resize((1, h), Image.Resampling.BOX).tobytes())
    x_bands = _content_bands(col_profile, 2, max(3, w // 80), max(8, w // 30))
    y_bands = _content_bands(row_profile, 2, max(3, h // 80), max(8, h // 30))
    return max(1, len(x_bands)), max(1, len(y_bands))


def _corner_color(img: Image.Image) -> tuple[int, int, int]:
    w, h = img.size
    pts = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
    pixels = [cast(tuple[int, ...], img.getpixel(p)) for p in pts]
    r, g, b = (tuple(sorted(channel)[len(channel) // 2] for channel in zip(*pixels)))
    return r, g, b


def _detect_pillow(image_path: Path) -> SpriteDetectionResult:
    with Image.open(image_path) as img:
        w, h = img.size

        # 0. Frames separated by background gaps (handles non-square frames such
        #    as a 2-up OFF/ON button strip that the size heuristics misread).
        cols, rows = _content_grid(img)
        if cols * rows >= 2:
            fw, fh = round(w / cols), round(h / rows)
            # Gaps were found on only one axis (e.g. an atlas with row gaps but
            # knobs packed within each row). If the strip subdivides cleanly into
            # square frames, recover the packed axis; non-square frames (a wide
            # button strip) fail this test and are left as-is.
            if rows > 1 and cols == 1 and fh and w % fh == 0 and w // fh > 1:
                cols, fw = w // fh, fh
            elif cols > 1 and rows == 1 and fw and h % fw == 0 and h // fw > 1:
                rows, fh = h // fw, fw
            return _grid_result(fw, fh, cols, rows)

    # 1. Common power-of-two-ish frame sizes (fast path for typical strips/grids).
    for frame_size in (256, 128, 64, 48, 32, 24, 16):
        if w % frame_size == 0 and h % frame_size == 0:
            cols, rows = w // frame_size, h // frame_size
            if cols * rows > 1:
                return _grid_result(frame_size, frame_size, cols, rows)

    # 2. Square-frame grid via gcd, for gap-packed sheets with odd frame sizes.
    #    Skipped for square sheets to avoid splitting a single square image.
    if w != h:
        grid = _square_grid(w, h)
        if grid is not None:
            s, cols, rows = grid
            return _grid_result(s, s, cols, rows)

    # 3. Filmstrip of square frames (one dimension a multiple of the other).
    if w > h and w % h == 0:
        return _grid_result(h, h, w // h, 1)
    if h > w and h % w == 0:
        return _grid_result(w, w, 1, h // w)

    return SpriteDetectionResult(w, h, 1, 1, 1, "horizontal_strip", "pillow")


def _detect_opencv(image_path: Path) -> SpriteDetectionResult | None:
    import cv2
    import numpy as np

    img = cv2.imread(str(image_path), cv2.IMREAD_UNCHANGED)
    if img is None:
        return None

    h, w = img.shape[:2]
    if len(img.shape) == 2:
        content = (img < 250).astype(np.uint8)
    elif img.shape[2] == 4:
        alpha = img[:, :, 3]
        content = (alpha > 10).astype(np.uint8)
    else:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        content = (gray < 250).astype(np.uint8)

    col_profile = content.sum(axis=0)
    row_profile = content.sum(axis=1)

    v_bounds = _find_frame_bounds(col_profile, w)
    h_bounds = _find_frame_bounds(row_profile, h)

    if len(v_bounds) >= 2 and len(h_bounds) >= 1:
        fw = int(round(sum(e - s for s, e in v_bounds) / len(v_bounds)))
        if len(h_bounds) == 1:
            fh = h
        else:
            fh = int(round(sum(e - s for s, e in h_bounds) / len(h_bounds)))
        cols = len(v_bounds)
        rows = max(1, len(h_bounds))
        fc = cols * rows
        if rows == 1 and cols > 1:
            layout = "horizontal_strip"
        elif cols == 1 and rows > 1:
            layout = "vertical_strip"
        else:
            layout = "grid"
        return SpriteDetectionResult(fw, fh, fc, cols, rows, layout, "opencv")

    # Fallback: equal division via contour bounding boxes
    contours, _ = cv2.findContours(content, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    boxes = [cv2.boundingRect(c) for c in contours if cv2.contourArea(c) > 50]
    if not boxes:
        return None

    widths = sorted({b[2] for b in boxes})
    heights = sorted({b[3] for b in boxes})
    fw = widths[len(widths) // 2]
    fh = heights[len(heights) // 2]
    if fw < 4 or fh < 4:
        return None
    if fw >= w and fh >= h:
        return None

    cols = max(1, w // fw)
    rows = max(1, h // fh)
    fc = cols * rows
    layout = "grid" if rows > 1 else "horizontal_strip"
    return SpriteDetectionResult(fw, fh, fc, cols, rows, layout, "opencv")


def _find_frame_bounds(profile, size: int, min_gap: int = 2) -> list[tuple[int, int]]:
    """Find contiguous content regions along a 1D projection."""
    bounds: list[tuple[int, int]] = []
    in_region = False
    start = 0
    threshold = max(1, profile.max() * 0.05) if profile.size else 1

    for i in range(size):
        active = profile[i] > threshold if i < len(profile) else False
        if active and not in_region:
            start = i
            in_region = True
        elif not active and in_region:
            if i - start >= min_gap:
                bounds.append((start, i))
            in_region = False
    if in_region and size - start >= min_gap:
        bounds.append((start, size))

    return bounds
