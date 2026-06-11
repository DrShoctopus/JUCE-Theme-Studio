"""Tests for alignment helpers."""

from __future__ import annotations

from juce_theme_studio.core.alignment import (
    AlignMode,
    align_controls,
    align_to_canvas,
    distribute_horizontally,
)
from juce_theme_studio.core.controls import create_control
from juce_theme_studio.core.types import ControlType


def test_align_left() -> None:
    a = create_control(ControlType.KNOB, "A", 10, 5, 32, 32)
    b = create_control(ControlType.KNOB, "B", 50, 20, 32, 32)
    result = align_controls([a, b], AlignMode.LEFT)
    assert result[a.id][0] == 10
    assert result[b.id][0] == 10


def test_align_h_center() -> None:
    a = create_control(ControlType.KNOB, "A", 0, 0, 40, 40)
    b = create_control(ControlType.KNOB, "B", 100, 0, 20, 20)
    result = align_controls([a, b], AlignMode.H_CENTER)
    # bounds: x=0..120, center=60; a->40, b->50
    assert result[a.id][0] == 40
    assert result[b.id][0] == 50


def test_align_to_canvas() -> None:
    c = create_control(ControlType.KNOB, "K", 10, 10, 64, 64)
    result = align_to_canvas([c], AlignMode.H_CENTER, 800, 600)
    assert result[c.id][0] == (800 - 64) // 2


def test_distribute_horizontal() -> None:
    controls = [
        create_control(ControlType.KNOB, f"C{i}", 0, 0, 20, 20) for i in range(3)
    ]
    controls[0].x = 0
    controls[1].x = 50
    controls[2].x = 150
    result = distribute_horizontally(controls)
    xs = sorted(result[c.id][0] for c in controls)
    assert xs[1] - xs[0] == xs[2] - xs[1]
