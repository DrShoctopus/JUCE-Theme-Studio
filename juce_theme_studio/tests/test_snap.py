"""Tests for snap guides."""

from __future__ import annotations

from juce_theme_studio.core.controls import create_control
from juce_theme_studio.core.snap import snap_position
from juce_theme_studio.core.types import ControlType


def test_snap_to_other_control_edge() -> None:
    moving = create_control(ControlType.KNOB, "A", 95, 50, 32, 32)
    other = create_control(ControlType.KNOB, "B", 50, 50, 32, 32)
    result = snap_position(
        moving, 85.0, 50.0, [moving, other],
        canvas_width=800, canvas_height=600,
        snap_to_grid=False, guide_threshold=8.0,
    )
    # Snap moving left edge to other's right edge (50 + 32 = 82)
    assert result.x == 82
    assert result.guide_lines_x


def test_snap_to_grid() -> None:
    moving = create_control(ControlType.KNOB, "A", 0, 0, 32, 32)
    result = snap_position(
        moving, 13.0, 11.0, [moving],
        canvas_width=800, canvas_height=600,
        grid_size=8, snap_to_grid=True, guide_threshold=4.0,
    )
    assert result.x == 16
    assert result.y == 8
