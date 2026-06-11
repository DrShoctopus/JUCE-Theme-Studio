"""Main application window."""

from __future__ import annotations

import copy
import logging
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from juce_theme_studio.core.assets import import_asset
from juce_theme_studio.core.controls import Control, create_control
from juce_theme_studio.core.manifest import ThemeManifest
from juce_theme_studio.core.project import (
    LoadedProject,
    create_manual_screen,
    load_project,
    save_project,
)
from juce_theme_studio.core.sprites import PreviewState, detect_sprite_grid
from juce_theme_studio.core.types import ControlType
from juce_theme_studio.core.undo import CallableCommand, UndoStack
from juce_theme_studio.core.validation import validate_manifest
from juce_theme_studio.git_tools.git import get_status
from juce_theme_studio.gui.canvas import CanvasScene, CanvasView
from juce_theme_studio.gui.panels.git_panel import GitCommitDialog
from juce_theme_studio.gui.panels.layers_panel import LayersPanel
from juce_theme_studio.gui.panels.log_panel import LogPanel
from juce_theme_studio.gui.panels.properties_panel import PropertiesPanel
from juce_theme_studio.juce.exporter import export_theme

logger = logging.getLogger("juce_theme_studio")

CONTROL_PALETTE = [
    (ControlType.KNOB, "Knob"),
    (ControlType.BUTTON, "Button"),
    (ControlType.TOGGLE_BUTTON, "Toggle"),
    (ControlType.SWITCH, "Switch"),
    (ControlType.METER, "Meter"),
    (ControlType.SLIDER, "Slider"),
    (ControlType.LED, "LED"),
    (ControlType.STATIC_IMAGE, "Image"),
    (ControlType.LABEL, "Label"),
    (ControlType.BACKGROUND, "Panel"),
]


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("JUCE Theme Studio")
        self.resize(1400, 900)

        self._project: LoadedProject | None = None
        self._current_screen_id: str | None = None
        self._undo = UndoStack()
        self._clipboard: Control | None = None
        self._preview_mode = False

        self._build_toolbar()
        self._build_ui()
        self._build_menus()

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main")
        self.addToolBar(tb)

        open_act = QAction("Open Project", self)
        open_act.triggered.connect(self._open_project)
        tb.addAction(open_act)

        save_act = QAction("Save", self)
        save_act.setShortcut(QKeySequence.StandardKey.Save)
        save_act.triggered.connect(self._save_project)
        tb.addAction(save_act)

        export_act = QAction("Export", self)
        export_act.triggered.connect(self._export)
        tb.addAction(export_act)

        self._preview_act = QAction("Preview Mode", self)
        self._preview_act.setCheckable(True)
        self._preview_act.triggered.connect(self._toggle_preview)
        tb.addAction(self._preview_act)

        commit_act = QAction("Commit", self)
        commit_act.triggered.connect(self._commit)
        tb.addAction(commit_act)

    def _build_menus(self) -> None:
        edit = self.menuBar().addMenu("Edit")
        undo_act = QAction("Undo", self)
        undo_act.setShortcut(QKeySequence.StandardKey.Undo)
        undo_act.triggered.connect(self._undo_action)
        edit.addAction(undo_act)
        redo_act = QAction("Redo", self)
        redo_act.setShortcut(QKeySequence.StandardKey.Redo)
        redo_act.triggered.connect(self._redo_action)
        edit.addAction(redo_act)
        dup_act = QAction("Duplicate", self)
        dup_act.setShortcut(QKeySequence("Ctrl+D"))
        dup_act.triggered.connect(self._duplicate)
        edit.addAction(dup_act)
        del_act = QAction("Delete", self)
        del_act.setShortcut(QKeySequence.StandardKey.Delete)
        del_act.triggered.connect(self._delete_selected)
        edit.addAction(del_act)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        # Left sidebar
        left = QSplitter(Qt.Orientation.Vertical)
        screens_box = QWidget()
        screens_layout = QVBoxLayout(screens_box)
        screens_layout.addWidget(QLabel("Screens"))
        self._screen_list = QListWidget()
        self._screen_list.currentRowChanged.connect(self._on_screen_selected)
        screens_layout.addWidget(self._screen_list)
        new_screen_btn = QPushButton("New Screen")
        new_screen_btn.clicked.connect(self._new_screen)
        screens_layout.addWidget(new_screen_btn)
        left.addWidget(screens_box)

        assets_box = QWidget()
        assets_layout = QVBoxLayout(assets_box)
        assets_layout.addWidget(QLabel("Assets"))
        self._asset_list = QListWidget()
        assets_layout.addWidget(self._asset_list)
        import_btn = QPushButton("Import Asset")
        import_btn.clicked.connect(self._import_asset)
        assets_layout.addWidget(import_btn)
        import_sprite_btn = QPushButton("Import Sprite Sheet")
        import_sprite_btn.clicked.connect(self._import_sprite_sheet)
        assets_layout.addWidget(import_sprite_btn)
        bg_btn = QPushButton("Set Background")
        bg_btn.clicked.connect(self._set_background)
        assets_layout.addWidget(bg_btn)
        left.addWidget(assets_box)

        palette_box = QWidget()
        palette_layout = QVBoxLayout(palette_box)
        palette_layout.addWidget(QLabel("Control Palette"))
        self._palette = QComboBox()
        for _, label in CONTROL_PALETTE:
            self._palette.addItem(label)
        palette_layout.addWidget(self._palette)
        add_ctrl_btn = QPushButton("Add Control")
        add_ctrl_btn.clicked.connect(self._add_control)
        palette_layout.addWidget(add_ctrl_btn)
        left.addWidget(palette_box)

        left.setMaximumWidth(260)

        # Center canvas
        self._scene = CanvasScene(ThemeManifest(), Path("."))
        self._canvas = CanvasView(self._scene)
        self._scene.selectionChanged.connect(self._on_canvas_selection)

        # Right sidebar
        right = QSplitter(Qt.Orientation.Vertical)
        self._properties = PropertiesPanel()
        self._properties.properties_changed.connect(self._on_properties_changed)
        right.addWidget(self._properties)

        self._layers = LayersPanel()
        self._layers.selection_changed.connect(self._scene.select_control)
        self._layers.layer_order_changed.connect(self._scene.refresh_all)
        self._layers.visibility_changed.connect(self._scene.refresh_all)
        self._layers.lock_changed.connect(self._scene.refresh_all)
        right.addWidget(self._layers)

        preview_box = QWidget()
        preview_layout = QVBoxLayout(preview_box)
        preview_layout.addWidget(QLabel("Preview Controls"))
        self._btn_state = QComboBox()
        for st in PreviewState:
            self._btn_state.addItem(st.value.title(), st)
        self._btn_state.currentIndexChanged.connect(self._on_button_state_preview)
        preview_layout.addWidget(QLabel("Button state"))
        preview_layout.addWidget(self._btn_state)
        right.addWidget(preview_box)
        right.setMaximumWidth(320)

        h_split = QSplitter()
        h_split.addWidget(left)
        h_split.addWidget(self._canvas)
        h_split.addWidget(right)
        h_split.setStretchFactor(1, 1)

        v_split = QSplitter(Qt.Orientation.Vertical)
        v_split.addWidget(h_split)
        self._log_panel = LogPanel()
        v_split.addWidget(self._log_panel)
        v_split.setStretchFactor(0, 4)

        main_layout.addWidget(v_split)

    def _open_project(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Open JUCE Project")
        if not path:
            return
        try:
            self._project = load_project(Path(path))
            self._undo.clear()
            self._scene.manifest = self._project.manifest
            self._scene.project_root = self._project.root
            self._refresh_ui()
            self._log_panel.append_log(f"Opened project: {path}")
            logger.info("Opened project %s", path)
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            logger.exception("Failed to open project")

    def _save_project(self) -> None:
        if not self._project:
            return
        if self._current_screen_id:
            self._project.manifest.last_opened_screen_id = self._current_screen_id
        save_project(self._project)
        self._log_panel.append_log("Project saved.")
        self._refresh_git_status()

    def _refresh_ui(self) -> None:
        if not self._project:
            return
        m = self._project.manifest
        self._scene.manifest = m
        self._scene.snap_to_grid = m.snap_to_grid
        self._scene.grid_size = m.grid_size

        self._screen_list.clear()
        for screen in m.screens:
            tag = " (manual)" if screen.manual else ""
            self._screen_list.addItem(f"{screen.name}{tag}")

        self._asset_list.clear()
        for asset in m.assets:
            tag = " [sprite]" if asset.is_sprite_sheet else ""
            self._asset_list.addItem(f"{asset.name}{tag}")

        idx = 0
        if m.last_opened_screen_id:
            for i, s in enumerate(m.screens):
                if s.id == m.last_opened_screen_id:
                    idx = i
                    break
        if m.screens:
            self._screen_list.setCurrentRow(idx)

        self._refresh_git_status()
        report = validate_manifest(m, self._project.root)
        self._log_panel.set_validation(report)

    def _on_screen_selected(self, row: int) -> None:
        if not self._project or row < 0 or row >= len(self._project.manifest.screens):
            return
        screen = self._project.manifest.screens[row]
        self._current_screen_id = screen.id
        self._scene.load_screen(screen)
        self._layers.set_screen(screen)
        self._canvas.fit_canvas()

    def _new_screen(self) -> None:
        if not self._project:
            QMessageBox.information(self, "No project", "Open a project first.")
            return
        name, ok = QInputDialog.getText(self, "New Screen", "Screen name:")
        if ok and name:
            create_manual_screen(self._project.manifest, name)
            self._refresh_ui()
            self._screen_list.setCurrentRow(len(self._project.manifest.screens) - 1)

    def _import_asset(self) -> None:
        if not self._project:
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self, "Import Asset", "",
            "Images (*.png *.jpg *.jpeg *.webp *.svg);;All (*)",
        )
        for p in paths:
            entry = import_asset(self._project.manifest, self._project.root, Path(p))
            self._log_panel.append_log(f"Imported asset: {entry.name}")
        self._refresh_ui()

    def _import_sprite_sheet(self) -> None:
        if not self._project:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Import Sprite Sheet", "", "Images (*.png *.jpg *.jpeg *.webp)",
        )
        if not path:
            return
        p = Path(path)
        entry = import_asset(
            self._project.manifest, self._project.root, p, is_sprite_sheet=True,
        )
        self._log_panel.append_log(f"Imported sprite sheet: {entry.name}")
        self._refresh_ui()

    def _set_background(self) -> None:
        if not self._project or not self._current_screen_id:
            return
        row = self._asset_list.currentRow()
        if row < 0 or row >= len(self._project.manifest.assets):
            QMessageBox.information(self, "Select asset", "Select an asset from the list first.")
            return
        asset = self._project.manifest.assets[row]
        screen = self._project.manifest.get_screen(self._current_screen_id)
        if screen:
            screen.background_asset_id = asset.id
            self._scene.load_screen(screen)
            self._log_panel.append_log(f"Background set to {asset.name}")

    def _add_control(self) -> None:
        if not self._project or not self._current_screen_id:
            return
        idx = self._palette.currentIndex()
        ctype, label = CONTROL_PALETTE[idx]
        asset_id = None
        sprite_config = None
        row = self._asset_list.currentRow()
        if row >= 0:
            asset = self._project.manifest.assets[row]
            asset_id = asset.id
            if asset.is_sprite_sheet:
                from juce_theme_studio.core.assets import resolve_asset_path
                from juce_theme_studio.core.sprites import SpriteConfig
                fw, fh, fc, cols = detect_sprite_grid(resolve_asset_path(self._project.root, asset))
                sprite_config = SpriteConfig(
                    frame_width=fw, frame_height=fh, frame_count=fc, columns=cols,
                )

        screen = self._project.manifest.get_screen(self._current_screen_id)
        if not screen:
            return
        z = max((c.z_index for c in screen.controls), default=-1) + 1
        control = create_control(ctype, label, 50, 50, 64, 64, asset_id, sprite_config)
        control.z_index = z
        control.mapping.screen_name = screen.name

        def do():
            self._scene.add_control(control)

        def undo():
            self._scene.remove_control(control.id)

        self._undo.push(CallableCommand(do, undo))
        self._layers.set_screen(screen)
        self._scene.select_control(control.id)

    def _on_canvas_selection(self) -> None:
        control = self._scene.get_selected_control()
        self._properties.set_control(control)
        if control:
            self._layers.select_control(control.id)

    def _on_properties_changed(self) -> None:
        self._scene.refresh_all()
        if self._scene.get_selected_control():
            cid = self._scene.get_selected_control().id
            self._scene.select_control(cid)

    def _toggle_preview(self, checked: bool) -> None:
        self._preview_mode = checked
        self._scene.set_preview_mode(checked)

    def _on_button_state_preview(self) -> None:
        state = self._btn_state.currentData()
        self._scene.set_button_preview_state(state)

    def _duplicate(self) -> None:
        control = self._scene.get_selected_control()
        if not control or not self._project:
            return
        new_c = copy.deepcopy(control)
        import uuid
        new_c.id = uuid.uuid4().hex[:12]
        new_c.name = control.name + "_copy"
        new_c.x += 20
        new_c.y += 20
        self._undo.push(CallableCommand(
            lambda: self._scene.add_control(new_c),
            lambda: self._scene.remove_control(new_c.id),
        ))
        self._layers.set_screen(self._project.manifest.get_screen(self._current_screen_id))

    def _delete_selected(self) -> None:
        control = self._scene.get_selected_control()
        if not control:
            return
        snap = copy.deepcopy(control)
        screen = self._current_screen()

        def do():
            self._scene.remove_control(snap.id)

        def undo():
            if screen:
                screen.controls.append(snap)
                self._scene.refresh_all()

        self._undo.push(CallableCommand(do, undo))
        self._layers.set_screen(screen)

    def _current_screen(self):
        if not self._project or not self._current_screen_id:
            return None
        return self._project.manifest.get_screen(self._current_screen_id)

    def _undo_action(self) -> None:
        if self._undo.undo():
            self._layers.set_screen(self._current_screen())
            self._scene.refresh_all()

    def _redo_action(self) -> None:
        if self._undo.redo():
            self._layers.set_screen(self._current_screen())
            self._scene.refresh_all()

    def _export(self) -> None:
        if not self._project:
            return
        save_project(self._project)
        report = validate_manifest(self._project.manifest, self._project.root)
        self._log_panel.set_validation(report)
        if report.has_blocking_errors:
            reply = QMessageBox.question(
                self, "Validation errors",
                "Blocking validation errors found. Export anyway?",
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            result = export_theme(self._project.manifest, self._project.root, force=True)
        else:
            result = export_theme(self._project.manifest, self._project.root)

        lines = [f"Exported to: {result.export_dir}"]
        for f in result.files_written:
            lines.append(f"  {f}")
        if result.backup_dir:
            lines.append(f"Backup: {result.backup_dir}")
        self._log_panel.append_log("\n".join(lines))
        QMessageBox.information(self, "Export complete", "\n".join(lines))

    def _commit(self) -> None:
        if not self._project:
            return
        dlg = GitCommitDialog(self._project.root, self)
        dlg.exec()
        self._refresh_git_status()

    def _refresh_git_status(self) -> None:
        if self._project:
            self._log_panel.set_git_status(get_status(self._project.root))
