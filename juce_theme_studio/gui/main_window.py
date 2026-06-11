"""Main application window."""

from __future__ import annotations

import copy
import logging
import uuid
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

from juce_theme_studio.core.alignment import (
    AlignMode,
    align_controls,
    align_to_canvas,
    distribute_horizontally,
    distribute_vertically,
)
from juce_theme_studio.core.assets import import_asset, resolve_asset_path
from juce_theme_studio.core.controls import Control, create_control
from juce_theme_studio.core.manifest import ThemeManifest
from juce_theme_studio.core.mapping import sync_scan_mappings
from juce_theme_studio.core.project import (
    LoadedProject,
    create_manual_screen,
    load_project,
    rescan_mappings,
    save_project,
)
from juce_theme_studio.core.sprites import PreviewState, SpriteConfig, detect_sprite_grid
from juce_theme_studio.core.types import ControlType
from juce_theme_studio.core.undo import CallableCommand, UndoStack
from juce_theme_studio.core.validation import validate_manifest
from juce_theme_studio.git_tools.git import get_status
from juce_theme_studio.gui.canvas import CanvasScene, CanvasView
from juce_theme_studio.gui.dialogs.export_preview_dialog import ExportPreviewDialog
from juce_theme_studio.gui.dialogs.settings_dialog import SettingsDialog
from juce_theme_studio.gui.dialogs.sprite_import_dialog import SpriteImportDialog
from juce_theme_studio.gui.panels.export_panel import ExportPanel
from juce_theme_studio.gui.panels.git_panel import GitCommitDialog
from juce_theme_studio.gui.panels.layers_panel import LayersPanel
from juce_theme_studio.gui.panels.log_panel import LogPanel
from juce_theme_studio.gui.panels.properties_panel import PropertiesPanel
from juce_theme_studio.gui.panels.screen_panel import ScreenPanel
from juce_theme_studio.juce.exporter import export_theme

logger = logging.getLogger("juce_theme_studio")

CONTROL_PALETTE = [
    (ControlType.KNOB, "Knob"),
    (ControlType.BUTTON, "Button"),
    (ControlType.TOGGLE_BUTTON, "Toggle"),
    (ControlType.SWITCH, "Switch"),
    (ControlType.METER, "Meter"),
    (ControlType.VU_METER, "VU Meter"),
    (ControlType.GAIN_REDUCTION_METER, "GR Meter"),
    (ControlType.SLIDER, "Slider"),
    (ControlType.LED, "LED"),
    (ControlType.STATIC_IMAGE, "Image"),
    (ControlType.LABEL, "Label"),
    (ControlType.BACKGROUND, "Panel"),
]

NUDGE_STEP = 1
NUDGE_STEP_LARGE = 8


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("JUCE Theme Studio")
        self.resize(1400, 900)

        self._project: LoadedProject | None = None
        self._current_screen_id: str | None = None
        self._undo = UndoStack()
        self._clipboard: list[Control] = []
        self._preview_mode = False

        self._build_toolbar()
        self._build_menus()
        self._build_ui()

    def _build_toolbar(self) -> None:
        tb = QToolBar("Main")
        self.addToolBar(tb)

        for label, slot in [
            ("Open Project", self._open_project),
            ("Save", self._save_project),
            ("Export", self._export),
        ]:
            act = QAction(label, self)
            act.triggered.connect(slot)
            tb.addAction(act)

        self._preview_act = QAction("Preview Mode", self)
        self._preview_act.setCheckable(True)
        self._preview_act.triggered.connect(self._toggle_preview)
        tb.addAction(self._preview_act)

        fit_act = QAction("Fit Canvas", self)
        fit_act.triggered.connect(self._fit_canvas)
        tb.addAction(fit_act)

        tb.addAction(QAction("Settings", self, triggered=self._show_settings))
        tb.addAction(QAction("Commit", self, triggered=self._commit))

        save_act = tb.actions()[1]
        save_act.setShortcut(QKeySequence.StandardKey.Save)

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("File")
        file_menu.addAction("Open Project...", self._open_project)
        file_menu.addAction("Save", self._save_project, QKeySequence.StandardKey.Save)
        file_menu.addSeparator()
        file_menu.addAction("Export...", self._export)
        file_menu.addSeparator()
        file_menu.addAction("Settings...", self._show_settings)

        edit = self.menuBar().addMenu("Edit")
        edit.addAction("Undo", self._undo_action, QKeySequence.StandardKey.Undo)
        edit.addAction("Redo", self._redo_action, QKeySequence.StandardKey.Redo)
        edit.addSeparator()
        edit.addAction("Cut", self._cut_selected, QKeySequence.StandardKey.Cut)
        edit.addAction("Copy", self._copy_selected, QKeySequence.StandardKey.Copy)
        edit.addAction("Paste", self._paste, QKeySequence.StandardKey.Paste)
        edit.addSeparator()
        edit.addAction("Duplicate", self._duplicate, QKeySequence("Ctrl+D"))
        edit.addAction("Delete", self._delete_selected, QKeySequence.StandardKey.Delete)
        edit.addSeparator()
        edit.addAction("Select All", self._select_all, QKeySequence.StandardKey.SelectAll)

        layout_menu = self.menuBar().addMenu("Layout")
        for label, mode in [
            ("Align Left", AlignMode.LEFT),
            ("Align H Center", AlignMode.H_CENTER),
            ("Align Right", AlignMode.RIGHT),
            ("Align Top", AlignMode.TOP),
            ("Align V Center", AlignMode.V_CENTER),
            ("Align Bottom", AlignMode.BOTTOM),
        ]:
            layout_menu.addAction(label, lambda m=mode: self._align(m))
        layout_menu.addSeparator()
        layout_menu.addAction(
            "Align to Canvas H Center", lambda: self._align_canvas(AlignMode.H_CENTER),
        )
        layout_menu.addAction(
            "Align to Canvas V Center", lambda: self._align_canvas(AlignMode.V_CENTER),
        )
        layout_menu.addSeparator()
        layout_menu.addAction("Distribute Horizontally", self._distribute_h)
        layout_menu.addAction("Distribute Vertically", self._distribute_v)

        project_menu = self.menuBar().addMenu("Project")
        project_menu.addAction("Sync JUCE Mappings", self._sync_mappings)
        project_menu.addAction("Rescan Project", self._rescan_project)

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QHBoxLayout(central)

        left = QSplitter(Qt.Orientation.Vertical)

        screens_box = QWidget()
        sl = QVBoxLayout(screens_box)
        sl.addWidget(QLabel("Screens"))
        self._screen_list = QListWidget()
        self._screen_list.currentRowChanged.connect(self._on_screen_selected)
        sl.addWidget(self._screen_list)
        row = QHBoxLayout()
        row.addWidget(self._btn("New Screen", self._new_screen))
        row.addWidget(self._btn("Fit", self._fit_canvas))
        sl.addLayout(row)
        left.addWidget(screens_box)

        assets_box = QWidget()
        al = QVBoxLayout(assets_box)
        al.addWidget(QLabel("Asset Library"))
        self._asset_list = QListWidget()
        al.addWidget(self._asset_list)
        al.addWidget(self._btn("Import Asset", self._import_asset))
        al.addWidget(self._btn("Import Sprite Sheet", self._import_sprite_sheet))
        al.addWidget(self._btn("Set Background", self._set_background))
        left.addWidget(assets_box)

        palette_box = QWidget()
        pl = QVBoxLayout(palette_box)
        pl.addWidget(QLabel("Control Palette"))
        self._palette = QComboBox()
        for _, label in CONTROL_PALETTE:
            self._palette.addItem(label)
        pl.addWidget(self._palette)
        pl.addWidget(self._btn("Add Control", self._add_control))
        left.addWidget(palette_box)
        left.setMaximumWidth(260)

        self._scene = CanvasScene(ThemeManifest(), Path("."))
        self._canvas = CanvasView(self._scene)
        self._scene.selectionChanged.connect(self._on_canvas_selection)

        right = QSplitter(Qt.Orientation.Vertical)
        self._screen_panel = ScreenPanel()
        self._screen_panel.screen_changed.connect(self._on_screen_settings_changed)
        right.addWidget(self._screen_panel)

        self._properties = PropertiesPanel()
        self._properties.properties_changed.connect(self._on_properties_changed)
        right.addWidget(self._properties)

        self._layers = LayersPanel()
        self._layers.selection_changed.connect(self._scene.select_control)
        self._layers.layer_order_changed.connect(self._refresh_canvas)
        self._layers.visibility_changed.connect(self._refresh_canvas)
        self._layers.lock_changed.connect(self._refresh_canvas)
        right.addWidget(self._layers)

        self._export_panel = ExportPanel()
        right.addWidget(self._export_panel)

        preview_box = QWidget()
        pvl = QVBoxLayout(preview_box)
        pvl.addWidget(QLabel("Preview Simulation"))
        self._btn_state = QComboBox()
        for st in PreviewState:
            self._btn_state.addItem(st.value.title(), st)
        self._btn_state.currentIndexChanged.connect(self._on_button_state_preview)
        pvl.addWidget(QLabel("Button state"))
        pvl.addWidget(self._btn_state)
        right.addWidget(preview_box)
        right.setMaximumWidth(340)

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

    @staticmethod
    def _btn(text: str, slot) -> QPushButton:
        b = QPushButton(text)
        b.clicked.connect(slot)
        return b

    def keyPressEvent(self, event) -> None:  # noqa: ANN001
        key = event.key()
        mods = event.modifiers()
        step = NUDGE_STEP_LARGE if mods & Qt.KeyboardModifier.ShiftModifier else NUDGE_STEP

        if key in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
            dx = dy = 0
            if key == Qt.Key.Key_Left:
                dx = -step
            elif key == Qt.Key.Key_Right:
                dx = step
            elif key == Qt.Key.Key_Up:
                dy = -step
            elif key == Qt.Key.Key_Down:
                dy = step
            if self._nudge_selected(dx, dy):
                event.accept()
                return
        super().keyPressEvent(event)

    def _open_project(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Open JUCE Project")
        if not path:
            return
        try:
            self._project = load_project(Path(path))
            self._undo.clear()
            self._scene.manifest = self._project.manifest
            self._scene.project_root = self._project.root
            self._export_panel.set_manifest(self._project.manifest)
            self._refresh_ui()
            msg = f"Opened project: {path}"
            if self._project.mappings_added:
                msg += f" ({self._project.mappings_added} control mapping(s) added from scanner)"
            self._log_panel.append_log(msg)
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
            src = f" [{screen.juce_component}]" if screen.juce_component else ""
            self._screen_list.addItem(f"{screen.name}{src}{tag}")

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
        self._screen_panel.set_screen(screen)
        self._canvas.fit_canvas()

    def _on_screen_settings_changed(self) -> None:
        screen = self._current_screen()
        if screen:
            row = self._screen_list.currentRow()
            if 0 <= row < self._screen_list.count():
                tag = " (manual)" if screen.manual else ""
                src = f" [{screen.juce_component}]" if screen.juce_component else ""
                self._screen_list.item(row).setText(f"{screen.name}{src}{tag}")
            self._scene.load_screen(screen)
            self._canvas.fit_canvas()

    def _new_screen(self) -> None:
        if not self._project:
            QMessageBox.information(self, "No project", "Open a project first.")
            return
        name, ok = QInputDialog.getText(self, "New Screen", "Screen name:")
        if ok and name:
            w, ok_w = QInputDialog.getInt(self, "Canvas Width", "Width:", 800, 100, 10000)
            if not ok_w:
                w = 800
            h, ok_h = QInputDialog.getInt(self, "Canvas Height", "Height:", 600, 100, 10000)
            if not ok_h:
                h = 600
            create_manual_screen(self._project.manifest, name, w, h)
            self._refresh_ui()
            self._screen_list.setCurrentRow(len(self._project.manifest.screens) - 1)

    def _import_asset(self) -> None:
        if not self._project:
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Import Asset",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.svg);;Fonts (*.ttf *.otf);;All (*)",
        )
        for p in paths:
            entry = import_asset(self._project.manifest, self._project.root, Path(p))
            self._log_panel.append_log(f"Imported asset: {entry.name}")
        self._refresh_ui()

    def _import_sprite_sheet(self) -> None:
        if not self._project:
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Import Sprite Sheet",
            "",
            "Images (*.png *.jpg *.jpeg *.webp)",
        )
        if not path:
            return
        p = Path(path)
        dlg = SpriteImportDialog(p, self)
        sprite_cfg = None
        if dlg.exec():
            sprite_cfg = dlg.sprite_config()

        entry = import_asset(
            self._project.manifest,
            self._project.root,
            p,
            is_sprite_sheet=True,
        )
        if sprite_cfg:
            entry.sprite_config = sprite_cfg.to_dict()
        self._log_panel.append_log(f"Imported sprite sheet: {entry.name}")
        self._refresh_ui()

    def _set_background(self) -> None:
        if not self._project or not self._current_screen_id:
            return
        row = self._asset_list.currentRow()
        if row < 0:
            QMessageBox.information(self, "Select asset", "Select an asset from the list first.")
            return
        asset = self._project.manifest.assets[row]
        screen = self._current_screen()
        if screen:
            screen.background_asset_id = asset.id
            self._scene.load_screen(screen)
            self._log_panel.append_log(f"Background set to {asset.name}")

    def _sprite_config_for_asset(self, asset) -> SpriteConfig | None:
        if asset.sprite_config:
            return SpriteConfig.from_dict(asset.sprite_config)
        path = resolve_asset_path(self._project.root, asset)
        fw, fh, fc, cols = detect_sprite_grid(path)
        return SpriteConfig(frame_width=fw, frame_height=fh, frame_count=fc, columns=cols)

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
                sprite_config = self._sprite_config_for_asset(asset)

        screen = self._current_screen()
        if not screen:
            return
        z = max((c.z_index for c in screen.controls), default=-1) + 1
        w, h = (120, 24) if ctype == ControlType.LABEL else (64, 64)
        control = create_control(ctype, label, 50, 50, w, h, asset_id, sprite_config)
        control.z_index = z
        control.mapping.screen_name = screen.name
        self._push_add_control(control)

    def _push_add_control(self, control: Control) -> None:
        screen = self._current_screen()

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
        cid = None
        sel = self._scene.get_selected_control()
        if sel:
            cid = sel.id
        self._scene.refresh_all()
        if cid:
            self._scene.select_control(cid)

    def _toggle_preview(self, checked: bool) -> None:
        self._preview_mode = checked
        self._scene.set_preview_mode(checked)

    def _on_button_state_preview(self) -> None:
        self._scene.set_button_preview_state(self._btn_state.currentData())

    def _fit_canvas(self) -> None:
        self._canvas.fit_canvas()

    def _current_screen(self):
        if not self._project or not self._current_screen_id:
            return None
        return self._project.manifest.get_screen(self._current_screen_id)

    def _selected_controls(self) -> list[Control]:
        return self._scene.get_selected_controls()

    def _apply_positions(self, positions: dict[str, tuple[int, int]]) -> None:
        if not positions:
            return
        screen = self._current_screen()
        if not screen:
            return
        before = {cid: (c.x, c.y) for c in screen.controls for cid in [c.id] if cid in positions}

        def do():
            for c in screen.controls:
                if c.id in positions:
                    c.x, c.y = positions[c.id]
            self._refresh_canvas()

        def undo():
            for c in screen.controls:
                if c.id in before:
                    c.x, c.y = before[c.id]
            self._refresh_canvas()

        self._undo.push(CallableCommand(do, undo))

    def _align(self, mode: AlignMode) -> None:
        controls = self._selected_controls()
        if len(controls) < 2 and mode in {AlignMode.LEFT, AlignMode.H_CENTER, AlignMode.RIGHT,
                                          AlignMode.TOP, AlignMode.V_CENTER, AlignMode.BOTTOM}:
            if not controls:
                return
        positions = align_controls(controls, mode)
        self._apply_positions(positions)

    def _align_canvas(self, mode: AlignMode) -> None:
        controls = self._selected_controls()
        screen = self._current_screen()
        if not controls or not screen:
            return
        positions = align_to_canvas(
            controls, mode, screen.canvas_width, screen.canvas_height,
        )
        self._apply_positions(positions)

    def _distribute_h(self) -> None:
        self._apply_positions(distribute_horizontally(self._selected_controls()))

    def _distribute_v(self) -> None:
        self._apply_positions(distribute_vertically(self._selected_controls()))

    def _nudge_selected(self, dx: int, dy: int) -> bool:
        controls = self._selected_controls()
        if not controls or self._preview_mode:
            return False
        positions = {c.id: (c.x + dx, c.y + dy) for c in controls}
        self._apply_positions(positions)
        return True

    def _copy_selected(self) -> None:
        self._clipboard = copy.deepcopy(self._selected_controls())

    def _cut_selected(self) -> None:
        self._copy_selected()
        self._delete_selected()

    def _paste(self) -> None:
        if not self._clipboard or not self._current_screen():
            return
        screen = self._current_screen()
        new_controls: list[Control] = []
        for c in self._clipboard:
            nc = copy.deepcopy(c)
            nc.id = uuid.uuid4().hex[:12]
            nc.x += 20
            nc.y += 20
            nc.name = c.name + "_paste"
            nc.z_index = max((x.z_index for x in screen.controls), default=-1) + 1
            new_controls.append(nc)

        def do():
            for nc in new_controls:
                self._scene.add_control(nc)

        def undo():
            for nc in new_controls:
                self._scene.remove_control(nc.id)

        self._undo.push(CallableCommand(do, undo))
        self._layers.set_screen(screen)

    def _select_all(self) -> None:
        for item in self._scene._items.values():
            item.setSelected(True)

    def _duplicate(self) -> None:
        for c in self._selected_controls():
            nc = copy.deepcopy(c)
            nc.id = uuid.uuid4().hex[:12]
            nc.name = c.name + "_copy"
            nc.x += 20
            nc.y += 20
            self._push_add_control(nc)

    def _delete_selected(self) -> None:
        controls = self._selected_controls()
        if not controls:
            return
        snaps = copy.deepcopy(controls)
        screen = self._current_screen()

        def do():
            for c in snaps:
                self._scene.remove_control(c.id)

        def undo():
            if screen:
                screen.controls.extend(snaps)
                self._refresh_canvas()

        self._undo.push(CallableCommand(do, undo))
        self._layers.set_screen(screen)

    def _refresh_canvas(self) -> None:
        screen = self._current_screen()
        if screen:
            self._scene.load_screen(screen)

    def _undo_action(self) -> None:
        if self._undo.undo():
            self._layers.set_screen(self._current_screen())
            self._refresh_canvas()

    def _redo_action(self) -> None:
        if self._undo.redo():
            self._layers.set_screen(self._current_screen())
            self._refresh_canvas()

    def _show_settings(self) -> None:
        if not self._project:
            QMessageBox.information(self, "No project", "Open a project first.")
            return
        dlg = SettingsDialog(self._project.manifest, self)
        if dlg.exec():
            dlg.apply()
            self._scene.snap_to_grid = self._project.manifest.snap_to_grid
            self._scene.grid_size = self._project.manifest.grid_size
            self._log_panel.append_log("Settings updated.")

    def _sync_mappings(self) -> None:
        if not self._project:
            return
        count = rescan_mappings(self._project)
        self._refresh_canvas()
        self._layers.set_screen(self._current_screen())
        self._log_panel.append_log(f"Synced {count} new JUCE control mapping(s).")

    def _rescan_project(self) -> None:
        if not self._project:
            return
        from juce_theme_studio.juce.scanner import scan_juce_project

        self._project.scan_result = scan_juce_project(self._project.root)
        count = sync_scan_mappings(self._project.manifest.screens, self._project.scan_result)
        self._refresh_ui()
        self._log_panel.append_log(f"Rescan complete. {count} new mapping(s) added.")

    def _export(self) -> None:
        if not self._project:
            return
        save_project(self._project)
        report = validate_manifest(self._project.manifest, self._project.root)
        self._log_panel.set_validation(report)

        preview = ExportPreviewDialog(
            self._project.manifest,
            self._project.root,
            report,
            self,
        )
        if preview.exec() != ExportPreviewDialog.DialogCode.Accepted:
            return

        if report.has_blocking_errors:
            reply = QMessageBox.question(
                self,
                "Validation errors",
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
        self._refresh_git_status()

    def _commit(self) -> None:
        if not self._project:
            return
        GitCommitDialog(self._project.root, self).exec()
        self._refresh_git_status()

    def _refresh_git_status(self) -> None:
        if self._project:
            self._log_panel.set_git_status(get_status(self._project.root))
