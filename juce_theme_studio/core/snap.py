"""Smart snapping: grid + alignment guides to other controls and canvas."""

from __future__ import annotations

from dataclasses import dataclass

from juce_theme_studio.core.alignment import control_rect
from juce_theme_studio.core.controls import Control


@dataclass
class SnapResult:
    x: int
    y: int
    guide_lines_x: list[int]
    guide_lines_y: list[int]


def _best_snap(
    origin: float,
    size: float,
    targets: list[float],
    threshold: float,
) -> tuple[int, list[int]]:
    """Snap a rectangle origin given candidate target lines for edges/center."""
    lines: list[int] = []
    best_origin = int(round(origin))
    best_dist = threshold + 1.0

    for offset in (0.0, size / 2, size):
        edge = origin + offset
        for target in targets:
            dist = abs(edge - target)
            if dist <= threshold and dist < best_dist:
                best_origin = int(round(target - offset))
                best_dist = dist
                lines = [int(round(target))]

    return best_origin, lines


def snap_position(
    moving: Control,
    new_x: float,
    new_y: float,
    others: list[Control],
    *,
    canvas_width: int,
    canvas_height: int,
    grid_size: int = 8,
    snap_to_grid: bool = True,
    guide_threshold: float = 6.0,
) -> SnapResult:
    """Snap dragged control to grid and nearby edges/centers."""
    rect = control_rect(moving)
    w, h = rect.width, rect.height

    x_targets: list[float] = [0.0, canvas_width / 2, float(canvas_width)]
    y_targets: list[float] = [0.0, canvas_height / 2, float(canvas_height)]

    for other in others:
        if other.id == moving.id:
            continue
        o = control_rect(other)
        x_targets.extend([float(o.x), float(o.h_center), float(o.right)])
        y_targets.extend([float(o.y), float(o.v_center), float(o.bottom)])

    if snap_to_grid and grid_size > 0:
        x_targets.append(round(new_x / grid_size) * grid_size)
        y_targets.append(round(new_y / grid_size) * grid_size)

    snapped_x, guide_x = _best_snap(new_x, float(w), x_targets, guide_threshold)
    snapped_y, guide_y = _best_snap(new_y, float(h), y_targets, guide_threshold)

    return SnapResult(snapped_x, snapped_y, guide_x, guide_y)
