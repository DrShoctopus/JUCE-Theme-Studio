"""Smoke tests that the main window wires up and edits flow through undo/dirty.

These guard against signal-wiring regressions (e.g. connecting to a signal a
widget does not define) that unit tests on core modules cannot catch.
"""

from __future__ import annotations

import copy
from pathlib import Path

import pytest
from PIL import Image

pytest.importorskip("PySide6")

from PySide6.QtGui import QAction  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog, QPushButton  # noqa: E402

from juce_theme_studio.core.assets import import_asset  # noqa: E402
from juce_theme_studio.core.controls import create_control  # noqa: E402
from juce_theme_studio.core.project import load_project  # noqa: E402
from juce_theme_studio.core.sprites import SpriteConfig  # noqa: E402
from juce_theme_studio.core.types import ControlType, SpriteLayout  # noqa: E402


def _project_tree(root: Path) -> list[tuple[str, str]]:
    return sorted(
        (
            "dir" if path.is_dir() else "file",
            path.relative_to(root).as_posix(),
        )
        for path in root.rglob("*")
    )


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


def test_screen_list_click_loads_scene_once(window) -> None:
    """A row-changing click loads the scene exactly once, not twice.

    Qt fires currentRowChanged on the press and itemClicked on the release of
    the same physical click, so naive wiring rebuilds the scene twice per
    click. A click on the already-selected row fires only itemClicked and must
    still reload (the canvas-refresh path).
    """
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from juce_theme_studio.core.project import create_manual_screen

    create_manual_screen(window._project.manifest, "Second", 800, 600)
    window._refresh_ui()
    window.show()
    QApplication.processEvents()

    calls: list[str] = []
    real_load = window._scene.load_screen

    def counting_load(screen) -> None:  # noqa: ANN001
        calls.append(screen.id)
        real_load(screen)

    window._scene.load_screen = counting_load

    def click(row: int) -> None:
        rect = window._screen_list.visualItemRect(window._screen_list.item(row))
        QTest.mouseClick(
            window._screen_list.viewport(),
            Qt.MouseButton.LeftButton,
            pos=rect.center(),
        )

    other = 1 if window._screen_list.currentRow() == 0 else 0
    other_id = window._project.manifest.screens[other].id

    click(other)
    assert calls == [other_id], "row-changing click must load exactly once"
    assert window._current_screen_id == other_id

    click(other)
    assert calls == [other_id, other_id], "same-row click must still reload"

    window.hide()


def test_export_cancel_does_not_save_or_clear_dirty(
    window, monkeypatch: pytest.MonkeyPatch
) -> None:
    from juce_theme_studio.gui import main_window as main_window_module

    calls: list[Path] = []

    class CancelPreview:
        DialogCode = QDialog.DialogCode

        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
            pass

        def exec(self):
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(main_window_module, "ExportPreviewDialog", CancelPreview)
    monkeypatch.setattr(
        main_window_module,
        "save_project",
        lambda loaded: calls.append(loaded.root),
    )
    window._set_dirty(True)

    window._export()

    assert calls == []
    assert window._dirty


def test_main_window_has_apply_and_revert_actions(window) -> None:
    action_texts = [action.text() for action in window.findChildren(QAction)]

    assert "Apply to Project" in action_texts
    assert "Revert Last Apply" in action_texts


def test_apply_cancel_does_not_write_project_files(
    window,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from juce_theme_studio.gui import main_window as main_window_module

    class CancelApplyPreview:
        DialogCode = QDialog.DialogCode

        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
            pass

        def exec(self):
            return QDialog.DialogCode.Rejected

    calls: list[str] = []
    monkeypatch.setattr(main_window_module, "ApplyPreviewDialog", CancelApplyPreview)
    monkeypatch.setattr(
        main_window_module,
        "execute_managed_apply",
        lambda plan: calls.append(plan.apply_id),
    )
    before = _project_tree(window._project.root)

    window._apply_to_project()

    after = _project_tree(window._project.root)
    assert after == before
    assert calls == []


def test_apply_failure_refreshes_git_status(
    window,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from juce_theme_studio.gui import main_window as main_window_module

    class AcceptApplyPreview:
        DialogCode = QDialog.DialogCode

        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
            pass

        def exec(self):
            return QDialog.DialogCode.Accepted

    refreshes: list[Path] = []
    monkeypatch.setattr(main_window_module, "ApplyPreviewDialog", AcceptApplyPreview)
    monkeypatch.setattr(
        main_window_module,
        "execute_managed_apply",
        lambda plan: (_ for _ in ()).throw(RuntimeError("apply broke")),
    )
    monkeypatch.setattr(
        main_window_module.QMessageBox,
        "critical",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        window,
        "_refresh_git_status",
        lambda: refreshes.append(window._project.root),
    )

    window._apply_to_project()

    assert refreshes == [window._project.root]


def test_revert_failure_refreshes_git_status(
    window,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from juce_theme_studio.gui import main_window as main_window_module

    refreshes: list[Path] = []
    monkeypatch.setattr(
        main_window_module.QMessageBox,
        "question",
        lambda *args, **kwargs: main_window_module.QMessageBox.StandardButton.Yes,
    )
    monkeypatch.setattr(
        main_window_module.QMessageBox,
        "critical",
        lambda *args, **kwargs: None,
    )
    monkeypatch.setattr(
        main_window_module,
        "revert_last_apply",
        lambda root: (_ for _ in ()).throw(RuntimeError("revert broke")),
    )
    monkeypatch.setattr(
        window,
        "_refresh_git_status",
        lambda: refreshes.append(window._project.root),
    )

    window._revert_last_apply()

    assert refreshes == [window._project.root]


def test_linking_static_asset_clears_previous_sprite_config(window, fixture_project: Path) -> None:
    screen = window._current_screen()
    sprite = import_asset(
        window._project.manifest,
        fixture_project,
        fixture_project / "Resources" / "knob_strip.png",
        is_sprite_sheet=True,
    )
    static = import_asset(
        window._project.manifest,
        fixture_project,
        fixture_project / "Resources" / "background.png",
    )
    control = create_control(
        ControlType.KNOB,
        "Gain",
        10,
        10,
        64,
        64,
        sprite.id,
        SpriteConfig(frame_count=8),
    )
    screen.controls.append(control)
    window._scene.load_screen(screen)

    window._link_asset_to_control(control, static, is_sprite=False)

    assert control.asset_id == static.id
    assert control.sprite_config is None


def test_live_preview_browse_button_is_visible(qapp) -> None:
    from juce_theme_studio.gui.panels.live_preview_panel import LivePreviewPanel
    from juce_theme_studio.juce.preview_bridge import LivePreviewBridge

    panel = LivePreviewPanel(LivePreviewBridge())

    assert any(button.text().startswith("Browse") for button in panel.findChildren(QPushButton))


def test_layer_up_moves_control_toward_front(qapp) -> None:
    from juce_theme_studio.core.manifest import Screen
    from juce_theme_studio.gui.panels.layers_panel import LayersPanel

    back = create_control(ControlType.KNOB, "Back", 0, 0, 64, 64)
    mid = create_control(ControlType.KNOB, "Middle", 0, 0, 64, 64)
    front = create_control(ControlType.KNOB, "Front", 0, 0, 64, 64)
    back.z_index, mid.z_index, front.z_index = 0, 1, 2
    screen = Screen(id="s1", name="Main", controls=[back, mid, front])
    panel = LayersPanel()
    panel.set_screen(screen)
    panel.select_control(mid.id)

    panel._move_layer(-1)

    assert mid.z_index == 2
    assert front.z_index == 1


def test_properties_panel_resets_sprite_fields_for_static_control(qapp) -> None:
    from juce_theme_studio.gui.panels.properties_panel import PropertiesPanel

    panel = PropertiesPanel()
    sprite_control = create_control(
        ControlType.KNOB,
        "Sprite",
        0,
        0,
        64,
        64,
        sprite_config=SpriteConfig(frame_count=8, frame_width=32, frame_height=32),
    )
    static_control = create_control(ControlType.STATIC_IMAGE, "Static", 0, 0, 64, 64)

    panel.set_control(sprite_control)
    panel.set_control(static_control)

    assert panel._frame_count.value() == 1
    assert not panel._frame_count.isEnabled()
    assert not panel._sprite_layout.isEnabled()


def test_clearing_canvas_selection_clears_layers_selection(window) -> None:
    control = create_control(ControlType.KNOB, "K", 0, 0, 64, 64)
    window._push_add_control(control)
    assert window._layers._tree.selectedItems()

    window._scene.clearSelection()
    QApplication.processEvents()

    assert not window._layers._tree.selectedItems()


def test_sprite_import_dialog_uses_ceil_rows_for_partial_grid(qapp, tmp_path: Path) -> None:
    from juce_theme_studio.gui.dialogs.sprite_import_dialog import SpriteImportDialog

    path = tmp_path / "grid.png"
    Image.new("RGBA", (300, 200), (0, 0, 0, 0)).save(path)
    dialog = SpriteImportDialog(path)
    dialog._layout.setCurrentIndex(dialog._layout.findData(SpriteLayout.GRID))
    dialog._frame_count.setValue(5)
    dialog._columns.setValue(3)

    cfg = dialog.sprite_config()

    assert cfg.rows == 2
