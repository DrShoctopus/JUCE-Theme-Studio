"""Main application window."""

from __future__ import annotations

import copy
import logging
import uuid
from pathlib import Path

from PIL import Image
from PIL.ImageQt import ImageQt
from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QAction, QKeySequence, QPixmap, QPixmapCache
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSlider,
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
from juce_theme_studio.core.assets import (
    delete_asset,
    get_asset_usages,
    import_asset,
    import_project_assets,
    resolve_asset_path,
    unimported_project_images,
)
from juce_theme_studio.core.controls import Control, create_control
from juce_theme_studio.core.image_ops import make_background_transparent
from juce_theme_studio.core.manifest import ThemeManifest
from juce_theme_studio.core.project import (
    LoadedProject,
    create_manual_screen,
    load_project,
    rescan_mappings,
    rescan_project,
    save_project,
)
from juce_theme_studio.core.sprite_slicer import slice_sprite_sheet_to_library
from juce_theme_studio.core.sprites import PreviewState, SpriteConfig, detect_sprite_grid
from juce_theme_studio.core.types import ControlType
from juce_theme_studio.core.undo import CallableCommand, UndoStack
from juce_theme_studio.core.validation import validate_manifest
from juce_theme_studio.git_tools.git import get_status
from juce_theme_studio.gui.canvas import CanvasScene, CanvasView
from juce_theme_studio.gui.dialogs.about_dialog import AboutDialog
from juce_theme_studio.gui.dialogs.export_preview_dialog import ExportPreviewDialog
from juce_theme_studio.gui.dialogs.help_dialog import HelpDialog
from juce_theme_studio.gui.dialogs.link_asset_dialog import LinkAssetDialog
from juce_theme_studio.gui.dialogs.settings_dialog import SettingsDialog
from juce_theme_studio.gui.dialogs.sprite_import_dialog import SpriteImportDialog
from juce_theme_studio.gui.dialogs.theme_colors_dialog import ThemeColorsDialog
from juce_theme_studio.gui.dialogs.theme_diff_dialog import ThemeDiffDialog
from juce_theme_studio.gui.panels.export_panel import ExportPanel
from juce_theme_studio.gui.panels.git_panel import GitCommitDialog
from juce_theme_studio.gui.panels.layers_panel import LayersPanel
from juce_theme_studio.gui.panels.live_preview_panel import LivePreviewPanel
from juce_theme_studio.gui.panels.log_panel import LogPanel
from juce_theme_studio.gui.panels.properties_panel import PropertiesPanel
from juce_theme_studio.gui.panels.screen_panel import ScreenPanel
from juce_theme_studio.gui.widgets.asset_list import AssetListWidget
from juce_theme_studio.juce.exporter import export_theme
from juce_theme_studio.juce.preview_bridge import LivePreviewBridge
from juce_theme_studio.juce.scanner_ast import libclang_available, treesitter_available

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
        # Fit small laptop screens: a window taller than the screen pushes the
        # zoom bar/log offscreen and breaks modal dialog placement on macOS.
        screen = QApplication.primaryScreen()
        if screen is not None:
            avail = screen.availableGeometry()
            self.resize(min(1400, avail.width() - 40), min(900, avail.height() - 40))
        else:
            self.resize(1400, 900)
        # Hold decoded sprite frames in cache so canvas reloads don't re-decode
        # the same images (pages can have 100+ sprite controls).
        QPixmapCache.setCacheLimit(96 * 1024)  # 96 MB

        self._project: LoadedProject | None = None
        self._current_screen_id: str | None = None
        self._undo = UndoStack()
        self._clipboard: list[Control] = []
        self._preview_mode = False
        self._live_preview = LivePreviewBridge(self)
        self._assign_asset_id: str | None = None
        self._assign_asset_is_sprite = False
        self._dirty = False
        # Snapshot of the currently selected control, used to build undo entries
        # from Properties-panel edits (which mutate the control in place).
        self._props_baseline: Control | None = None
        # True while we programmatically re-select a control during a refresh, so
        # the selection handler does not overwrite the undo baseline mid-edit.
        self._restoring_selection = False
        # Screen-list row that was current when the mouse last pressed on the
        # list. itemClicked (fired on release) cannot otherwise tell a same-row
        # refresh click apart from the release half of a row-changing click,
        # whose currentRowChanged already loaded the screen on press.
        self._screen_row_at_press = -1

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

        settings_act = QAction("Settings", self)
        settings_act.triggered.connect(self._show_settings)
        tb.addAction(settings_act)
        commit_act = QAction("Commit", self)
        commit_act.triggered.connect(self._commit)
        tb.addAction(commit_act)

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
        project_menu.addSeparator()
        project_menu.addAction("Theme Colors…", self._show_theme_colors)
        project_menu.addAction("Theme Diff…", self._show_theme_diff)

        help_menu = self.menuBar().addMenu("Help")
        help_menu.addAction("User Guide…", self._show_help, QKeySequence("F1"))
        help_menu.addSeparator()
        help_menu.addAction("About JUCE Theme Studio…", self._show_about)

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
        self._screen_list.itemClicked.connect(self._on_screen_item_clicked)
        # eventFilter records the current row before each press moves it.
        self._screen_list.viewport().installEventFilter(self)
        sl.addWidget(self._screen_list)
        row = QHBoxLayout()
        row.addWidget(self._btn("New Screen", self._new_screen))
        row.addWidget(self._btn("Fit", self._fit_canvas))
        sl.addLayout(row)
        left.addWidget(screens_box)

        assets_box = QWidget()
        al = QVBoxLayout(assets_box)
        al.addWidget(QLabel("Asset Library"))
        self._asset_list = AssetListWidget()
        self._asset_list.asset_clicked.connect(self._on_asset_clicked)
        al.addWidget(self._asset_list)
        self._asset_preview = QLabel("Click an asset to preview")
        self._asset_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._asset_preview.setMinimumHeight(140)
        self._asset_preview.setFrameShape(QFrame.Shape.StyledPanel)
        self._asset_preview.setStyleSheet("color: #888; background: #1b1b1b;")
        al.addWidget(self._asset_preview)
        assign_hint = QLabel("Click asset → click control to assign")
        assign_hint.setWordWrap(True)
        assign_hint.setStyleSheet("color: #888; font-size: 11px;")
        al.addWidget(assign_hint)
        row_assets = QHBoxLayout()
        row_assets.addWidget(self._btn("Import Asset", self._import_asset))
        row_assets.addWidget(self._btn("From Project", lambda: self._import_from_project()))
        al.addLayout(row_assets)
        al.addWidget(self._btn("Import Sprite Sheet", self._import_sprite_sheet))
        row_asset_actions = QHBoxLayout()
        row_asset_actions.addWidget(self._btn("Set Background", self._set_background))
        row_asset_actions.addWidget(self._btn("Delete Asset", self._delete_selected_asset))
        al.addLayout(row_asset_actions)
        self._asset_list.delete_requested.connect(self._delete_selected_asset)
        self._asset_list.make_transparent_requested.connect(self._make_asset_transparent)
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

        # Scrollable for the same reason as the right column below: the
        # column's minimum height must not force the window off small screens.
        left_scroll = QScrollArea()
        left_scroll.setWidget(left)
        left_scroll.setWidgetResizable(True)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_scroll.setMaximumWidth(260)

        self._scene = CanvasScene(ThemeManifest(), Path("."))
        self._canvas = CanvasView(self._scene)
        self._scene.selectionChanged.connect(self._on_canvas_selection)
        self._scene.control_moved.connect(lambda _cid: self._mark_live_dirty())
        self._scene.geometry_committed.connect(self._on_geometry_committed)
        self._scene.control_clicked.connect(self._on_control_clicked)
        self._canvas.asset_dropped.connect(self._on_asset_dropped)
        self._canvas.zoom_changed.connect(self._on_canvas_zoom_changed)

        canvas_container = QWidget()
        cc = QVBoxLayout(canvas_container)
        cc.setContentsMargins(0, 0, 0, 0)
        cc.setSpacing(0)
        cc.addWidget(self._canvas)
        cc.addWidget(self._build_zoom_bar())

        right = QSplitter(Qt.Orientation.Vertical)
        self._screen_panel = ScreenPanel()
        self._screen_panel.screen_changed.connect(self._on_screen_settings_changed)
        right.addWidget(self._screen_panel)

        self._properties = PropertiesPanel()
        self._properties.properties_changed.connect(self._on_properties_changed)
        self._properties.edit_committed.connect(self._on_property_commit)
        right.addWidget(self._properties)

        self._layers = LayersPanel()
        self._layers.selection_changed.connect(self._scene.select_control)
        self._layers.layer_order_changed.connect(self._refresh_canvas)
        self._layers.visibility_changed.connect(self._refresh_canvas)
        self._layers.lock_changed.connect(self._refresh_canvas)
        right.addWidget(self._layers)

        self._export_panel = ExportPanel()
        self._export_panel.settings_changed.connect(self._on_export_settings_changed)
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

        self._live_panel = LivePreviewPanel(self._live_preview)
        right.addWidget(self._live_panel)

        # The stacked panels' combined minimum height exceeds small laptop
        # screens; scrolling the column lets the window itself stay on-screen.
        right_scroll = QScrollArea()
        right_scroll.setWidget(right)
        right_scroll.setWidgetResizable(True)
        right_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        right_scroll.setMaximumWidth(340)

        h_split = QSplitter()
        h_split.addWidget(left_scroll)
        h_split.addWidget(canvas_container)
        h_split.addWidget(right_scroll)
        h_split.setStretchFactor(1, 1)

        v_split = QSplitter(Qt.Orientation.Vertical)
        v_split.addWidget(h_split)
        self._log_panel = LogPanel()
        v_split.addWidget(self._log_panel)
        # Give the log a compact ~1/8 strip (half its old height); window resize
        # grows the canvas, not the log. Still drag-resizable; text scrolls.
        v_split.setStretchFactor(0, 1)
        v_split.setStretchFactor(1, 0)
        v_split.setSizes([840, 120])
        main_layout.addWidget(v_split)

    @staticmethod
    def _btn(text: str, slot) -> QPushButton:
        b = QPushButton(text)
        b.clicked.connect(slot)
        return b

    def _build_zoom_bar(self) -> QWidget:
        bar = QWidget()
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(6, 2, 6, 2)
        lay.addWidget(QLabel("Zoom"))
        out_btn = self._btn("−", lambda: self._nudge_zoom(False))
        in_btn = self._btn("+", lambda: self._nudge_zoom(True))
        for b in (out_btn, in_btn):
            b.setMaximumWidth(30)
        self._zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self._zoom_slider.setRange(
            int(CanvasView.ZOOM_MIN * 100), int(CanvasView.ZOOM_MAX * 100)
        )
        self._zoom_slider.setValue(100)
        self._zoom_slider.setMaximumWidth(240)
        self._zoom_slider.valueChanged.connect(self._on_zoom_slider)
        self._zoom_block = False
        self._zoom_label = QLabel("100%")
        self._zoom_label.setMinimumWidth(46)
        lay.addWidget(out_btn)
        lay.addWidget(self._zoom_slider)
        lay.addWidget(in_btn)
        lay.addWidget(self._zoom_label)
        lay.addStretch(1)
        lay.addWidget(self._btn("Fit", self._fit_canvas))
        return bar

    def _on_zoom_slider(self, value: int) -> None:
        if self._zoom_block:
            return
        self._canvas.set_zoom(value / 100.0)

    def _nudge_zoom(self, zoom_in: bool) -> None:
        factor = CanvasView.ZOOM_STEP if zoom_in else 1 / CanvasView.ZOOM_STEP
        self._canvas.set_zoom(self._canvas.current_zoom() * factor)

    def _on_canvas_zoom_changed(self, zoom: float) -> None:
        percent = int(round(zoom * 100))
        self._zoom_block = True
        self._zoom_slider.setValue(max(self._zoom_slider.minimum(),
                                       min(self._zoom_slider.maximum(), percent)))
        self._zoom_block = False
        self._zoom_label.setText(f"{percent}%")

    def _show_asset_preview(self, asset) -> None:  # noqa: ANN001
        self._asset_preview.setPixmap(QPixmap())
        if asset is None or self._project is None:
            self._asset_preview.setText("Click an asset to preview")
            return
        path = resolve_asset_path(self._project.root, asset)
        if not path.is_file():
            self._asset_preview.setText("(file missing)")
            return
        try:
            with Image.open(path) as im:
                pix = QPixmap.fromImage(ImageQt(im.convert("RGBA")))
            w = max(120, self._asset_preview.width() - 8)
            self._asset_preview.setPixmap(
                pix.scaled(w, 200, Qt.AspectRatioMode.KeepAspectRatio,
                           Qt.TransformationMode.SmoothTransformation)
            )
        except Exception:
            self._asset_preview.setText("(preview unavailable)")

    def keyPressEvent(self, event) -> None:  # noqa: ANN001
        key = event.key()
        mods = event.modifiers()
        step = NUDGE_STEP_LARGE if mods & Qt.KeyboardModifier.ShiftModifier else NUDGE_STEP

        if key == Qt.Key.Key_Escape and self._assign_asset_id:
            self._clear_assign_mode()
            self._log_panel.append_log("Asset assignment cancelled.")
            event.accept()
            return

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
        if not self._maybe_save_changes():
            return
        path = QFileDialog.getExistingDirectory(self, "Open JUCE Project")
        if not path:
            return
        try:
            self._project = load_project(Path(path))
            self._undo.clear()
            self._props_baseline = None
            self._scene.manifest = self._project.manifest
            self._scene.project_root = self._project.root
            self._export_panel.set_manifest(self._project.manifest)
            self._live_preview.configure(self._project.root, self._project.manifest)
            binary = LivePreviewBridge.find_bundled_preview(self._project.root)
            self._live_panel.set_suggested_binary(binary)
            self._refresh_ui()
            self._set_dirty(False)
            self._refresh_parameter_suggestions()
            parsers = []
            if treesitter_available():
                parsers.append("tree-sitter-cpp")
            if libclang_available():
                parsers.append("libclang")
            parser_note = f" [parsers: {', '.join(parsers) or 'regex fallback'}]"
            msg = f"Opened project: {path}{parser_note}"
            if self._project.mappings_added:
                msg += f" ({self._project.mappings_added} mapping(s) from scanner)"
            self._log_panel.append_log(msg)
            self._offer_import_project_assets()
        except Exception as exc:
            QMessageBox.critical(self, "Error", str(exc))
            logger.exception("Failed to open project")

    def _save_project(self) -> None:
        if not self._project:
            return
        if self._current_screen_id:
            self._project.manifest.last_opened_screen_id = self._current_screen_id
        save_project(self._project)
        self._set_dirty(False)
        self._log_panel.append_log("Project saved.")
        self._refresh_git_status()

    def _set_dirty(self, dirty: bool) -> None:
        self._dirty = dirty
        self._update_title()

    def _update_title(self) -> None:
        title = "JUCE Theme Studio"
        if self._project:
            title += f" — {self._project.root.name}"
        if self._dirty:
            title += " *"
        self.setWindowTitle(title)

    def _maybe_save_changes(self) -> bool:
        """Prompt to save unsaved edits. Return False only if the user cancels."""
        if not self._dirty or not self._project:
            return True
        reply = QMessageBox.question(
            self,
            "Unsaved changes",
            "Save changes to the theme project before continuing?",
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if reply == QMessageBox.StandardButton.Cancel:
            return False
        if reply == QMessageBox.StandardButton.Save:
            self._save_project()
        return True

    def closeEvent(self, event) -> None:  # noqa: ANN001
        if self._maybe_save_changes():
            # Selection signals fired during teardown land in a half-deleted
            # scene (RuntimeError: Internal C++ object already deleted).
            self._scene.blockSignals(True)
            event.accept()
        else:
            event.ignore()

    def eventFilter(self, obj, event) -> bool:  # noqa: ANN001
        if (
            obj is self._screen_list.viewport()
            and event.type() == QEvent.Type.MouseButtonPress
        ):
            # Selection moves on press, so this is the last moment the
            # pre-click row is still known; _on_screen_item_clicked needs it
            # to recognise the trailing itemClicked of a row-changing click.
            self._screen_row_at_press = self._screen_list.currentRow()
        return super().eventFilter(obj, event)

    # --- macOS fullscreen workaround ---------------------------------------
    # macOS 26 (Tahoe) + Qt 6.11 corrupt the QWindow geometry cache in native
    # fullscreen Spaces: Qt keeps/reverts to stale window rects (no state
    # change event fires, isFullScreen() reports False, the layout visibly
    # reflows), so every mouse event - mapped local = global - cached_origin -
    # lands offset from the UI. Sprites and the zoom bar stop responding where
    # they are drawn. Qt-side geometry writes make it worse: Cocoa fights the
    # write and eventually drops the window into a corrupted pseudo-fullscreen.
    # Until the toolkit bug is fixed, keep the window out of fullscreen Spaces
    # altogether: the green titlebar button zooms (maximises) instead, which
    # looks near-identical and has shown pixel-accurate input in every test.

    def showEvent(self, event) -> None:  # noqa: ANN001
        super().showEvent(event)
        self._disable_native_fullscreen()

    def _disable_native_fullscreen(self) -> None:
        if QApplication.platformName() != "cocoa":
            return
        try:
            import ctypes

            import objc  # pyobjc-framework-Cocoa

            view = objc.objc_object(c_void_p=ctypes.c_void_p(int(self.winId())))
            nswin = view.window()
            if nswin is None:
                return
            behavior = int(nswin.collectionBehavior())
            behavior &= ~(1 << 7)  # clear NSWindowCollectionBehaviorFullScreenPrimary
            behavior |= 1 << 9  # NSWindowCollectionBehaviorFullScreenNone
            nswin.setCollectionBehavior_(behavior)
        except Exception:  # noqa: BLE001
            logger.debug("Could not disable native fullscreen", exc_info=True)

    def _native_fullscreen(self) -> bool | None:
        """Ground-truth fullscreen state from the NSWindow; None if unknown."""
        if QApplication.platformName() != "cocoa":
            return None
        try:
            import ctypes

            import objc  # pyobjc-framework-Cocoa

            view = objc.objc_object(c_void_p=ctypes.c_void_p(int(self.winId())))
            nswin = view.window()
            if nswin is None:
                return None
            return bool(int(nswin.styleMask()) & (1 << 14))  # NSWindowStyleMaskFullScreen
        except Exception:  # noqa: BLE001
            return None

    def _refresh_ui(self) -> None:
        if not self._project:
            return
        m = self._project.manifest
        self._scene.manifest = m
        self._scene.snap_to_grid = m.snap_to_grid
        self._scene.grid_size = m.grid_size

        self._screen_list.blockSignals(True)
        self._screen_list.clear()
        for screen in m.screens:
            tag = " (manual)" if screen.manual else ""
            src = f" [{screen.juce_component}]" if screen.juce_component else ""
            item = QListWidgetItem(f"{screen.name}{src}{tag}")
            item.setData(Qt.ItemDataRole.UserRole, screen.id)
            self._screen_list.addItem(item)

        self._asset_list.set_assets(m.assets)

        idx = 0
        if m.last_opened_screen_id:
            for i, s in enumerate(m.screens):
                if s.id == m.last_opened_screen_id:
                    idx = i
                    break
        self._screen_list.blockSignals(False)
        if m.screens:
            self._screen_list.setCurrentRow(idx)
            # QListWidget may already be on row 0 after repopulating, so currentRowChanged
            # does not fire — always load the selected screen explicitly.
            self._load_screen_at_row(idx)

        self._refresh_git_status()
        report = validate_manifest(m, self._project.root)
        self._log_panel.set_validation(report)
        self._log_panel.set_warnings([issue.message for issue in report.warnings])

    def _on_screen_selected(self, row: int) -> None:
        self._load_screen_at_row(row)

    def _on_screen_item_clicked(self, item: QListWidgetItem) -> None:
        row = self._screen_list.row(item)
        if row != self._screen_row_at_press:
            # The press half of this click moved the selection, so
            # currentRowChanged already loaded this screen; loading it again
            # here would rebuild the whole scene a second time.
            return
        # Clicking the already-selected row does not emit currentRowChanged;
        # this reload is what lets a same-row click refresh the canvas.
        self._load_screen_at_row(row)

    def _load_screen_at_row(self, row: int) -> None:
        if not self._project or row < 0 or row >= len(self._project.manifest.screens):
            return
        screen = self._project.manifest.screens[row]
        self._current_screen_id = screen.id
        self._clear_assign_mode()
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
            self._mark_live_dirty()

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
            new_idx = len(self._project.manifest.screens) - 1
            self._screen_list.setCurrentRow(new_idx)
            self._load_screen_at_row(new_idx)
            self._set_dirty(True)

    def _import_asset(self) -> None:
        if not self._project:
            return
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Import Asset",
            "",
            "Images (*.png *.jpg *.jpeg *.webp);;Fonts (*.ttf *.otf);;All (*)",
        )
        last_id = None
        for p in paths:
            entry = import_asset(self._project.manifest, self._project.root, Path(p))
            self._log_panel.append_log(f"Imported asset: {entry.name}")
            last_id = entry.id
        self._refresh_ui()
        if last_id:
            self._set_dirty(True)
            if self._asset_list.select_asset(last_id):
                self._show_asset_preview(self._project.manifest.get_asset(last_id))

    def _offer_import_project_assets(self) -> None:
        if not self._project or not self._project.scan_result:
            return
        images = unimported_project_images(
            self._project.manifest,
            self._project.root,
            self._project.scan_result.image_assets,
        )
        if not images:
            return
        answer = QMessageBox.question(
            self,
            "Import project assets",
            f"Found {len(images)} new image(s) in this JUCE project.\n\n"
            "Copy them into the asset library now? (Original files are not modified.)",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self._import_from_project(silent=False, image_paths=images)

    def _import_from_project(
        self,
        *,
        silent: bool = False,
        image_paths: list[str] | None = None,
    ) -> None:
        if not self._project or not self._project.scan_result:
            if not silent:
                QMessageBox.information(self, "No project", "Open a project first.")
            return
        if image_paths is None:
            image_paths = self._project.scan_result.image_assets
        if not image_paths:
            if not silent:
                QMessageBox.information(
                    self,
                    "No images",
                    "No image files were found under this project.",
                )
            return
        imported = import_project_assets(
            self._project.manifest,
            self._project.root,
            image_paths,
        )
        if imported:
            for entry in imported:
                self._log_panel.append_log(f"Imported from project: {entry.name}")
            save_project(self._project)
            self._set_dirty(False)
            self._refresh_ui()
            if not silent:
                QMessageBox.information(
                    self,
                    "Import complete",
                    f"Copied {len(imported)} asset(s) into the library.",
                )
        elif not silent:
            QMessageBox.information(
                self,
                "Already imported",
                "All project images are already in the asset library.",
            )

    def _delete_selected_asset(self) -> None:
        if not self._project:
            return
        row = self._asset_list.currentRow()
        if row < 0 or row >= len(self._project.manifest.assets):
            QMessageBox.information(self, "Select asset", "Select an asset from the list first.")
            return
        asset = self._project.manifest.assets[row]
        usages = get_asset_usages(self._project.manifest, asset.id)
        clear_refs = False
        if usages:
            usage_lines = "\n".join(f"  • {u.screen_name}: {u.description}" for u in usages[:8])
            if len(usages) > 8:
                usage_lines += f"\n  … and {len(usages) - 8} more"
            reply = QMessageBox.question(
                self,
                "Asset in use",
                f"'{asset.name}' is used in {len(usages)} place(s):\n\n{usage_lines}\n\n"
                "Remove the asset and clear these references?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
            clear_refs = True
        else:
            reply = QMessageBox.question(
                self,
                "Delete asset",
                f"Delete '{asset.name}' from the asset library?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if reply != QMessageBox.StandardButton.Yes:
                return

        deleted = delete_asset(
            self._project.manifest,
            self._project.root,
            asset.id,
            clear_references=clear_refs,
        )
        if deleted is None:
            return
        save_project(self._project)
        self._set_dirty(False)
        self._refresh_ui()
        if self._current_screen_id:
            self._scene.load_screen(self._current_screen())
        self._log_panel.append_log(f"Deleted asset: {deleted.name}")

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
        if not dlg.exec():
            return

        sprite_cfg = dlg.sprite_config()
        slice_frames = dlg.slice_into_library()
        keep_sheet = dlg.keep_full_sheet()
        remove_bg = dlg.remove_background()

        if slice_frames:
            sliced = slice_sprite_sheet_to_library(
                self._project.manifest,
                self._project.root,
                p,
                sprite_cfg,
                base_name=p.stem,
            )
            if remove_bg:
                for frame in sliced:
                    self._strip_background(frame)
            self._log_panel.append_log(
                f"Sliced {len(sliced)} frame(s) into asset library."
            )

        new_id = None
        if keep_sheet or not slice_frames:
            entry = import_asset(
                self._project.manifest,
                self._project.root,
                p,
                is_sprite_sheet=True,
            )
            entry.sprite_config = sprite_cfg.to_dict()
            if remove_bg:
                self._strip_background(entry)
            new_id = entry.id
            self._log_panel.append_log(
                f"Imported sprite sheet '{entry.name}' "
                f"({sprite_cfg.frame_count} frames). Assign it to a knob/button to animate."
            )

        self._refresh_ui()
        self._set_dirty(True)
        if new_id and self._asset_list.select_asset(new_id):
            self._show_asset_preview(self._project.manifest.get_asset(new_id))

    def _strip_background(self, asset) -> int:  # noqa: ANN001
        """Knock out an asset's solid background in place; returns pixels cleared."""
        if self._project is None:
            return 0
        path = resolve_asset_path(self._project.root, asset)
        if not path.is_file():
            return 0
        try:
            return make_background_transparent(path)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Background removal failed for %s: %s", asset.name, exc)
            return 0

    def _make_asset_transparent(self) -> None:
        if not self._project:
            return
        row = self._asset_list.currentRow()
        if row < 0 or row >= len(self._project.manifest.assets):
            QMessageBox.information(self, "Select asset", "Select an asset from the list first.")
            return
        asset = self._project.manifest.assets[row]
        path = resolve_asset_path(self._project.root, asset)
        if not path.is_file():
            QMessageBox.warning(self, "Missing file", f"Asset file not found for '{asset.name}'.")
            return
        cleared = self._strip_background(asset)
        if cleared == 0:
            self._log_panel.append_log(
                f"No solid background found in '{asset.name}' (nothing made transparent)."
            )
            return
        self._log_panel.append_log(
            f"Made background transparent in '{asset.name}' ({cleared} pixels cleared)."
        )
        # The library file changed in place: refresh preview and re-render any
        # control/background that uses it.
        self._show_asset_preview(asset)
        if self._current_screen_id:
            self._scene.load_screen(self._current_screen())
        self._mark_live_dirty()

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
            self._mark_live_dirty()

    def _sprite_config_for_asset(self, asset) -> SpriteConfig | None:
        if self._project is None:
            return None
        try:
            if asset.sprite_config:
                return SpriteConfig.from_dict(asset.sprite_config)
            path = resolve_asset_path(self._project.root, asset)
            fw, fh, fc, cols = detect_sprite_grid(path)
            return SpriteConfig(frame_width=fw, frame_height=fh, frame_count=fc, columns=cols)
        except (ValueError, OSError) as exc:
            logger.warning("Sprite config fallback for %s: %s", asset.name, exc)
            return SpriteConfig()

    def _on_export_settings_changed(self) -> None:
        self._mark_live_dirty()

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
        if screen:
            control.z_index = max((c.z_index for c in screen.controls), default=-1) + 1

        def do():
            self._scene.add_control(control)

        def undo():
            self._scene.remove_control(control.id)

        self._undo.push(CallableCommand(do, undo))
        self._layers.set_screen(screen)
        self._scene.select_control(control.id)
        self._mark_live_dirty()

    def _on_canvas_selection(self) -> None:
        control = self._scene.get_selected_control()
        self._properties.set_control(control)
        if not self._restoring_selection:
            self._props_baseline = copy.deepcopy(control) if control else None
        self._layers.select_control(control.id if control else None)

    def _on_properties_changed(self) -> None:
        # Live edits update only the selected item in place; rebuilding the whole
        # canvas here janks pages with many sprite controls.
        sel = self._scene.get_selected_control()
        if sel and not self._scene.update_control(sel.id):
            self._scene.refresh_all()
        self._mark_live_dirty()

    def _on_property_commit(self) -> None:
        """Turn a finished Properties-panel edit into an undoable command."""
        control = self._scene.get_selected_control()
        if control is None:
            return
        baseline = self._props_baseline
        if baseline is None or baseline.id != control.id:
            self._props_baseline = copy.deepcopy(control)
            return
        before = baseline
        after = copy.deepcopy(control)
        if before.to_dict() == after.to_dict():
            return  # nothing actually changed (e.g. spurious editingFinished)

        def do():
            control.assign_from(after)
            self._refresh_after_control_edit(control.id)

        def undo():
            control.assign_from(before)
            self._refresh_after_control_edit(control.id)

        # The control already holds the "after" state from live editing, so register
        # the command without re-applying it.
        self._undo.push_applied(CallableCommand(do, undo))
        self._props_baseline = copy.deepcopy(control)
        self._set_dirty(True)

    def _on_geometry_committed(self, before: dict) -> None:
        """Make a drag/resize undoable. ``before`` maps control id -> (x, y, w, h)."""
        screen = self._current_screen()
        if not screen:
            return
        by_id = {c.id: c for c in screen.controls}
        after = {
            cid: (by_id[cid].x, by_id[cid].y, by_id[cid].width, by_id[cid].height)
            for cid in before
            if cid in by_id
        }

        def apply(state: dict) -> None:
            for cid, (x, y, w, h) in state.items():
                c = by_id.get(cid)
                if c is not None:
                    c.x, c.y, c.width, c.height = x, y, w, h
            self._refresh_canvas()

        self._undo.push_applied(CallableCommand(lambda: apply(after), lambda: apply(before)))
        self._set_dirty(True)

    def _refresh_after_control_edit(self, control_id: str) -> None:
        self._scene.refresh_all()
        self._scene.select_control(control_id)
        control = next(
            (c for c in (self._current_screen().controls if self._current_screen() else [])
             if c.id == control_id),
            None,
        )
        self._properties.set_control(control)
        self._props_baseline = copy.deepcopy(control) if control else None
        self._layers.set_screen(self._current_screen())
        self._mark_live_dirty()

    def _refresh_parameter_suggestions(self) -> None:
        if self._project and self._project.scan_result:
            self._properties.set_parameter_suggestions(
                self._project.scan_result.parameter_ids
            )

    def _mark_live_dirty(self) -> None:
        self._live_preview.mark_dirty()
        self._set_dirty(True)

    def _on_asset_clicked(self, asset_id: str, is_sprite: bool) -> None:
        if not self._project:
            return
        asset = self._project.manifest.get_asset(asset_id)
        if asset is None:
            return
        self._show_asset_preview(asset)
        target = self._scene.get_selected_control()
        if target is not None:
            self._offer_link_asset_to_control(
                target,
                asset,
                is_sprite,
                prompt="Assign this asset to the selected control?",
            )
            return
        self._assign_asset_id = asset_id
        self._assign_asset_is_sprite = is_sprite
        self._canvas.set_assign_mode(True)
        self._log_panel.append_log(
            f"Click a control on the canvas to assign '{asset.name}'. (Esc to cancel)",
        )

    def _on_control_clicked(self, control_id: str) -> None:
        if not self._project or not self._assign_asset_id:
            return
        screen = self._current_screen()
        if not screen:
            return
        target = next((c for c in screen.controls if c.id == control_id), None)
        if target is None:
            return
        asset = self._project.manifest.get_asset(self._assign_asset_id)
        if asset is None:
            self._clear_assign_mode()
            return
        self._offer_link_asset_to_control(
            target,
            asset,
            self._assign_asset_is_sprite,
            prompt="Assign this asset to the clicked control?",
        )

    def _offer_link_asset_to_control(
        self,
        control: Control,
        asset,
        is_sprite: bool,
        *,
        prompt: str | None = None,
    ) -> None:
        dlg = LinkAssetDialog(control, asset, self, prompt=prompt)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            self._log_panel.append_log("Asset link cancelled.")
            return
        self._link_asset_to_control(control, asset, is_sprite)
        self._clear_assign_mode()
        self._mark_live_dirty()

    def _clear_assign_mode(self) -> None:
        self._assign_asset_id = None
        self._assign_asset_is_sprite = False
        self._canvas.set_assign_mode(False)

    def _on_asset_dropped(
        self,
        asset_id: str,
        x: int,
        y: int,
        is_sprite: bool,
        target_control_id: str = "",
    ) -> None:
        if not self._project or not self._current_screen_id:
            return
        asset = self._project.manifest.get_asset(asset_id)
        if asset is None:
            return

        if target_control_id:
            screen = self._current_screen()
            if not screen:
                return
            target = next((c for c in screen.controls if c.id == target_control_id), None)
            if target is None:
                return
            self._offer_link_asset_to_control(
                target,
                asset,
                is_sprite,
                prompt="Drop detected on an existing control. Link this asset?",
            )
            return

        idx = self._palette.currentIndex()
        ctype, label = CONTROL_PALETTE[idx]
        use_sprite = is_sprite or asset.is_sprite_sheet
        sprite_config = self._sprite_config_for_asset(asset) if use_sprite else None
        if is_sprite or asset.is_sprite_sheet:
            ctype = ControlType.KNOB if idx == 0 else ctype
        screen = self._current_screen()
        if not screen:
            return
        z = max((c.z_index for c in screen.controls), default=-1) + 1
        w, h = (120, 24) if ctype == ControlType.LABEL else (64, 64)
        control = create_control(ctype, asset.name or label, x, y, w, h, asset_id, sprite_config)
        control.z_index = z
        control.mapping.screen_name = screen.name
        self._push_add_control(control)
        self._mark_live_dirty()

    def _link_asset_to_control(self, control: Control, asset, is_sprite: bool) -> None:
        use_sprite = is_sprite or asset.is_sprite_sheet
        sprite_config = self._sprite_config_for_asset(asset) if use_sprite else None
        before_asset = control.asset_id
        before_sprite = (
            control.sprite_config.to_dict() if control.sprite_config else None
        )

        def do():
            control.asset_id = asset.id
            control.sprite_config = sprite_config if use_sprite else None
            self._scene.refresh_all()
            self._scene.select_control(control.id)
            self._properties.set_control(control)

        def undo():
            control.asset_id = before_asset
            control.sprite_config = (
                SpriteConfig.from_dict(before_sprite) if before_sprite else None
            )
            self._scene.refresh_all()
            self._scene.select_control(control.id)
            self._properties.set_control(control)

        self._undo.push(CallableCommand(do, undo))
        label = control.mapping.cpp_variable or control.name
        self._log_panel.append_log(f"Linked asset '{asset.name}' → control '{label}'.")

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
        self._set_dirty(True)

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
        z = max((x.z_index for x in screen.controls), default=-1)
        for c in self._clipboard:
            nc = copy.deepcopy(c)
            nc.id = uuid.uuid4().hex[:12]
            nc.x += 20
            nc.y += 20
            nc.name = c.name + "_paste"
            z += 1
            nc.z_index = z
            new_controls.append(nc)

        def do():
            for nc in new_controls:
                self._scene.add_control(nc)

        def undo():
            for nc in new_controls:
                self._scene.remove_control(nc.id)

        self._undo.push(CallableCommand(do, undo))
        self._layers.set_screen(screen)
        self._mark_live_dirty()

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
        self._mark_live_dirty()

    def _refresh_canvas(self) -> None:
        screen = self._current_screen()
        if screen:
            self._scene.load_screen(screen)
        self._mark_live_dirty()

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
            self._mark_live_dirty()

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
        screens_added, mapped = rescan_project(self._project)
        self._refresh_ui()
        self._refresh_parameter_suggestions()
        if mapped or screens_added:
            self._set_dirty(True)
        msg = f"Rescan complete. {mapped} new mapping(s) added."
        if screens_added:
            msg += f" {screens_added} new screen(s) added."
        self._log_panel.append_log(msg)
        self._offer_import_project_assets()

    def _export(self) -> None:
        if not self._project:
            return
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

        save_project(self._project)
        self._set_dirty(False)

        lines = [f"Exported to: {result.export_dir}"]
        for f in result.files_written:
            lines.append(f"  {f}")
        if result.backup_dir:
            lines.append(f"Backup: {result.backup_dir}")
        self._log_panel.append_log("\n".join(lines))

        # Keep the dialog a fixed, dismissable size: a per-file list (250+
        # entries) grew the box past the screen and pushed OK out of reach.
        # The full list is in the log panel; offer it here under "Show Details".
        summary = f"{len(result.files_written)} file(s) written to:\n{result.export_dir}"
        if result.backup_dir:
            summary += f"\n\nBackup: {result.backup_dir}"
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Information)
        box.setWindowTitle("Export complete")
        box.setText(summary)
        box.setDetailedText("\n".join(lines))
        box.exec()
        self._refresh_git_status()

    def _commit(self) -> None:
        if not self._project:
            return
        GitCommitDialog(self._project.root, self).exec()
        self._refresh_git_status()

    def _refresh_git_status(self) -> None:
        if self._project:
            self._log_panel.set_git_status(get_status(self._project.root))

    def _show_theme_colors(self) -> None:
        if not self._project:
            QMessageBox.information(self, "No project", "Open a project first.")
            return
        dlg = ThemeColorsDialog(self._project.manifest, self)
        if dlg.exec():
            changed = dlg.result_colors() != self._project.manifest.theme_colors
            dlg.apply()
            if changed:
                self._set_dirty(True)
                self._mark_live_dirty()
            self._log_panel.append_log("Theme colors updated.")

    def _show_theme_diff(self) -> None:
        if not self._project:
            QMessageBox.information(self, "No project", "Open a project first.")
            return
        ThemeDiffDialog(self._project.root, self).exec()

    def _show_help(self) -> None:
        HelpDialog(self).exec()

    def _show_about(self) -> None:
        AboutDialog(self).exec()
