"""Tests for undo primitives used by drag/resize/property editing."""

from __future__ import annotations

from juce_theme_studio.core.controls import create_control
from juce_theme_studio.core.sprites import SpriteConfig
from juce_theme_studio.core.types import ControlType
from juce_theme_studio.core.undo import CallableCommand, UndoStack


def test_push_applied_does_not_re_execute() -> None:
    calls: list[str] = []
    stack = UndoStack()
    cmd = CallableCommand(lambda: calls.append("do"), lambda: calls.append("undo"))

    stack.push_applied(cmd)
    assert calls == []  # effect already applied; do() not run again

    assert stack.undo() is True
    assert calls == ["undo"]
    assert stack.redo() is True
    assert calls == ["undo", "do"]


def test_geometry_undo_redo_round_trip() -> None:
    """Mirrors how a drag/resize is registered: model already at 'after'."""
    control = create_control(ControlType.KNOB, "Gain", x=10, y=20, width=64, height=64)
    before = (10, 20, 64, 64)
    control.x, control.y, control.width, control.height = 100, 200, 80, 80  # live drag
    after = (100, 200, 80, 80)

    def apply(state):
        control.x, control.y, control.width, control.height = state

    stack = UndoStack()
    stack.push_applied(CallableCommand(lambda: apply(after), lambda: apply(before)))

    stack.undo()
    assert (control.x, control.y, control.width, control.height) == before
    stack.redo()
    assert (control.x, control.y, control.width, control.height) == after


def test_assign_from_restores_all_fields_in_place() -> None:
    target = create_control(ControlType.KNOB, "Gain", x=0, y=0)
    target_id = target.id

    source = create_control(
        ControlType.SLIDER, "Tone", x=5, y=6, width=120, height=24,
        sprite_config=SpriteConfig(frame_count=12),
    )
    source.mapping.cpp_variable = "toneSlider"
    source.preview_value = 0.7
    source.locked = True

    target.assign_from(source)

    assert target.id == target_id  # identity preserved (canvas items keep the ref)
    assert target.control_type == ControlType.SLIDER
    assert (target.x, target.y, target.width, target.height) == (5, 6, 120, 24)
    assert target.mapping.cpp_variable == "toneSlider"
    assert target.preview_value == 0.7
    assert target.locked is True
    assert target.sprite_config is not source.sprite_config  # deep-copied
    assert target.sprite_config is not None
    assert target.sprite_config.frame_count == 12
