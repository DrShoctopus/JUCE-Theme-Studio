"""Alignment and distribution helpers for canvas controls."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from juce_theme_studio.core.controls import Control


class AlignMode(str, Enum):
    LEFT = "left"
    H_CENTER = "h_center"
    RIGHT = "right"
    TOP = "top"
    V_CENTER = "v_center"
    BOTTOM = "bottom"


@dataclass(frozen=True)
class Rect:
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height

    @property
    def h_center(self) -> int:
        return self.x + self.width // 2

    @property
    def v_center(self) -> int:
        return self.y + self.height // 2


def control_rect(control: Control) -> Rect:
    return Rect(control.x, control.y, control.width, control.height)


def selection_bounds(controls: list[Control]) -> Rect | None:
    if not controls:
        return None
    rects = [control_rect(c) for c in controls]
    x1 = min(r.x for r in rects)
    y1 = min(r.y for r in rects)
    x2 = max(r.right for r in rects)
    y2 = max(r.bottom for r in rects)
    return Rect(x1, y1, x2 - x1, y2 - y1)


def align_controls(
    controls: list[Control],
    mode: AlignMode,
    *,
    reference: Rect | None = None,
) -> dict[str, tuple[int, int]]:
    """Return control id -> (new_x, new_y) after alignment."""
    if not controls:
        return {}

    bounds = reference or selection_bounds(controls)
    if bounds is None:
        return {}

    if mode == AlignMode.LEFT:
        target = bounds.x
        return {c.id: (target, c.y) for c in controls}
    if mode == AlignMode.RIGHT:
        target = bounds.right
        return {c.id: (target - c.width, c.y) for c in controls}
    if mode == AlignMode.H_CENTER:
        target = bounds.h_center
        return {c.id: (target - c.width // 2, c.y) for c in controls}
    if mode == AlignMode.TOP:
        target = bounds.y
        return {c.id: (c.x, target) for c in controls}
    if mode == AlignMode.BOTTOM:
        target = bounds.bottom
        return {c.id: (c.x, target - c.height) for c in controls}
    if mode == AlignMode.V_CENTER:
        target = bounds.v_center
        return {c.id: (c.x, target - c.height // 2) for c in controls}

    return {}


def align_to_canvas(
    controls: list[Control],
    mode: AlignMode,
    canvas_width: int,
    canvas_height: int,
) -> dict[str, tuple[int, int]]:
    """Align selection to canvas edges or center."""
    if not controls:
        return {}
    result: dict[str, tuple[int, int]] = {}
    for c in controls:
        if mode == AlignMode.LEFT:
            result[c.id] = (0, c.y)
        elif mode == AlignMode.RIGHT:
            result[c.id] = (canvas_width - c.width, c.y)
        elif mode == AlignMode.H_CENTER:
            result[c.id] = ((canvas_width - c.width) // 2, c.y)
        elif mode == AlignMode.TOP:
            result[c.id] = (c.x, 0)
        elif mode == AlignMode.BOTTOM:
            result[c.id] = (c.x, canvas_height - c.height)
        elif mode == AlignMode.V_CENTER:
            result[c.id] = (c.x, (canvas_height - c.height) // 2)
    return result


def distribute_horizontally(controls: list[Control]) -> dict[str, tuple[int, int]]:
    """Evenly space controls horizontally within selection bounds."""
    if len(controls) < 3:
        return {}
    ordered = sorted(controls, key=lambda c: c.x)
    bounds = selection_bounds(ordered)
    if bounds is None:
        return {}
    total_width = sum(c.width for c in ordered)
    gap = (bounds.width - total_width) / (len(ordered) - 1)
    result: dict[str, tuple[int, int]] = {}
    x = float(bounds.x)
    for c in ordered:
        result[c.id] = (int(round(x)), c.y)
        x += c.width + gap
    return result


def distribute_vertically(controls: list[Control]) -> dict[str, tuple[int, int]]:
    """Evenly space controls vertically within selection bounds."""
    if len(controls) < 3:
        return {}
    ordered = sorted(controls, key=lambda c: c.y)
    bounds = selection_bounds(ordered)
    if bounds is None:
        return {}
    total_height = sum(c.height for c in ordered)
    gap = (bounds.height - total_height) / (len(ordered) - 1)
    result: dict[str, tuple[int, int]] = {}
    y = float(bounds.y)
    for c in ordered:
        result[c.id] = (c.x, int(round(y)))
        y += c.height + gap
    return result
