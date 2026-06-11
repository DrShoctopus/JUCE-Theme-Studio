"""Smoke tests that the main window wires up and edits flow through undo/dirty.

These guard against signal-wiring regressions (e.g. connecting to a signal a
widget does not define) that unit tests on core modules cannot catch.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

from juce_theme_studio.core.controls import create_control  # noqa: E402
from juce_theme_studio.core.project import load_project  # noqa: E402
from juce_theme_studio.core.types import ControlType  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def window(qapp, fixture_project: Path):
    from juce_theme_studio.gui.main_window import MainWindow

    w = MainWindow()
    w._project = load_project(fixture_project)
    w._scene.manifest = w._project.manifest
    w._scene.project_root = w._project.root
    w._refresh_ui()
    w._set_dirty(False)
    w._refresh_parameter_suggestions()
    yield w
    # Silence selection signals so scene teardown does not fire into deleted C++.
    # Do not call close(): closeEvent would pop a modal save prompt and hang.
    w._scene.blockSignals(True)
    w.deleteLater()


def test_main_window_constructs(window) -> None:
    assert window._current_screen() is not None


def test_geometry_edit_is_undoable_and_marks_dirty(window) -> None:
    screen = window._current_screen()
    c = create_control(ControlType.KNOB, "TestKnob", 10, 20, 64, 64)
    window._scene.load_screen(screen)
    window._push_add_control(c)
    assert window._dirty
    assert "*" in window.windowTitle()

    before = {c.id: (c.x, c.y, c.width, c.height)}
    c.x, c.y, c.width, c.height = 100, 200, 80, 80  # simulate a drag
    window._on_geometry_committed(before)

    assert window._undo.undo() and (c.x, c.y) == (10, 20)
    assert window._undo.redo() and (c.x, c.y) == (100, 200)


def test_property_edit_is_undoable(window) -> None:
    screen = window._current_screen()
    c = create_control(ControlType.KNOB, "TestKnob", 10, 20, 64, 64)
    window._scene.load_screen(screen)
    window._push_add_control(c)

    window._scene.select_control(c.id)
    window._props_baseline = copy.deepcopy(c)
    c.name = "Renamed"
    window._on_property_commit()

    assert window._undo.undo() and c.name == "TestKnob"
    assert window._undo.redo() and c.name == "Renamed"


def test_save_clears_dirty_marker(window) -> None:
    window._push_add_control(create_control(ControlType.KNOB, "K", 0, 0, 64, 64))
    assert window._dirty
    window._save_project()
    assert not window._dirty
    assert "*" not in window.windowTitle()
