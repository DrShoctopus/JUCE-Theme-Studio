"""Instrumented launcher to catch the 'sprites + zoom bar go dead' freeze.

Run it exactly like the app, but pointed at this file:

    PYTHONPATH=/Users/shoctopus/Documents/GitHub/juce_theme_studio \
      /Users/shoctopus/Documents/GitHub/juce_theme_studio/juce_theme_studio/.venv/bin/python \
      /Users/shoctopus/Documents/GitHub/juce_theme_studio/diagnose_input_freeze.py

Then reproduce your steps: open project, import sprite sheet, link sprite to a
control, go full screen, resize the sprite, click off it, then try to click
another sprite and the zoom bar.

Everything is written to  /tmp/jts_freeze.log  (and echoed to the console).
When the freeze happens, the last few PRESS lines show which Qt invariant broke:
  grabberItem   - a scene item still holds the mouse grab (should be None at rest)
  widgetGrab    - a widget still holds the mouse grab (should be None at rest)
  interactive   - if False, the view ignores item clicks (BAD)
  dragMode      - should be RubberBandDrag when idle (NoDrag = stuck assign mode)
  modal/popup   - a dialog/menu still thinks it is open (BAD)
  zoomBlock     - if True, the zoom slider is being ignored (BAD)
  hitItem       - did this press land on a control item? (None => press fell
                  through to the view => starts a rubber band instead of select)
Any line starting with !!! EXCEPTION is a crash inside a Qt event handler.
"""

from __future__ import annotations

import datetime as _dt
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtWidgets import QApplication, QWidget

LOG = Path("/tmp/jts_freeze.log")
_fh = LOG.open("a", encoding="utf-8")  # append: keep evidence across relaunches


def log(msg: str) -> None:
    line = f"{_dt.datetime.now():%H:%M:%S.%f}  {msg}"
    _fh.write(line + "\n")
    _fh.flush()
    print(line, flush=True)


def _excepthook(exc_type, exc, tb) -> None:
    log("!!! EXCEPTION (uncaught):\n" + "".join(traceback.format_exception(exc_type, exc, tb)))


sys.excepthook = _excepthook


class LoudApplication(QApplication):
    """Catch exceptions raised inside any event handler / slot."""

    def notify(self, receiver, event):  # noqa: ANN001
        try:
            return super().notify(receiver, event)
        except Exception:  # noqa: BLE001
            log(
                "!!! EXCEPTION inside event handler "
                f"(receiver={receiver.__class__.__name__}, event={event.type()}):\n"
                + traceback.format_exc()
            )
            return False


def _describe(window) -> str:
    from PySide6.QtWidgets import QApplication as QA

    scene = window._scene
    view = window._canvas
    grab_item = scene.mouseGrabberItem()
    grab_item_name = "None"
    if grab_item is not None:
        ctl = getattr(grab_item, "control", None)
        grab_item_name = getattr(ctl, "name", grab_item.__class__.__name__)
    return (
        f"grabberItem={grab_item_name} "
        f"widgetGrab={QWidget.mouseGrabber().__class__.__name__ if QWidget.mouseGrabber() else None} "
        f"interactive={view.isInteractive()} "
        f"dragMode={view.dragMode().name} "
        f"assignId={window._assign_asset_id} "
        f"modal={QA.activeModalWidget().__class__.__name__ if QA.activeModalWidget() else None} "
        f"popup={QA.activePopupWidget().__class__.__name__ if QA.activePopupWidget() else None} "
        f"zoomBlock={getattr(window, '_zoom_block', '?')} "
        f"fullscreen={window.isFullScreen()} zoom={view.current_zoom():.2f} "
        f"scroll=({view.horizontalScrollBar().value()},"
        f"{view.verticalScrollBar().value()})"
    )


class MouseSpy(QObject):
    def __init__(self, window) -> None:
        super().__init__()
        self.window = window
        self.viewport = window._canvas.viewport()
        self.slider = window._zoom_slider

    def eventFilter(self, obj, event):  # noqa: ANN001
        et = event.type()
        if et == QEvent.Type.WindowStateChange and obj is self.window:
            log(
                f"### WINDOW STATE CHANGE: fullscreen={self.window.isFullScreen()} "
                f"state={self.window.windowState()}"
            )
        if et in (QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease):
            from PySide6.QtWidgets import QGraphicsItem

            from juce_theme_studio.gui.canvas_items import ControlGraphicsItem

            who = "?"
            if obj is self.viewport:
                who = "canvas"
            elif obj is self.slider or obj is getattr(self.slider, "parent", lambda: None)():
                who = "zoomSlider"
            elif obj.__class__.__name__ == "QSlider":
                who = "zoomSlider"
            kind = "PRESS" if et == QEvent.Type.MouseButtonPress else "release"
            extra = ""
            if obj is self.viewport and hasattr(event, "position"):
                view = self.window._canvas
                scene = self.window._scene
                sp = view.mapToScene(event.position().toPoint())
                hit_item = None
                for it in scene.items(sp):
                    if isinstance(it, ControlGraphicsItem):
                        hit_item = it
                        break
                extra = f" scenePos=({sp.x():.0f},{sp.y():.0f})"
                if hit_item is None:
                    # Press fell through: name the nearest control so we can tell
                    # a sloppy click from a sprite whose clickable rect is wrong.
                    near = None
                    best = 1e18
                    if scene.screen:
                        for c in scene.screen.controls:
                            dx = max(c.x - sp.x(), 0, sp.x() - (c.x + c.width))
                            dy = max(c.y - sp.y(), 0, sp.y() - (c.y + c.height))
                            d = dx * dx + dy * dy
                            if d < best:
                                best, near = d, c
                    extra += (
                        f" hitItem=None nearest={near.name if near else None}"
                        f"@{best ** 0.5:.0f}px" if near else " hitItem=None"
                    )
                else:
                    c = hit_item.control
                    movable = bool(
                        hit_item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable
                    )
                    desync = (
                        abs(hit_item.pos().x() - c.x) > 1
                        or abs(hit_item.pos().y() - c.y) > 1
                        or abs(hit_item.rect().width() - c.width) > 1
                        or abs(hit_item.rect().height() - c.height) > 1
                    )
                    extra += (
                        f" hitItem={c.name} movable={movable} locked={c.locked} "
                        f"visible={c.visible} itemPreview={hit_item.preview_mode} "
                        f"ctl=({c.x},{c.y} {c.width}x{c.height}) "
                        f"item=({hit_item.pos().x():.0f},{hit_item.pos().y():.0f} "
                        f"{hit_item.rect().width():.0f}x{hit_item.rect().height():.0f})"
                        f"{' DESYNC!' if desync else ''}"
                    )
            if who in ("canvas", "zoomSlider"):
                log(f"{kind:6s} {who:10s}{extra}  {_describe(self.window)}")
        return False


def _wrap(obj, name, before=None, after=None):
    orig = getattr(obj, name)

    def wrapped(*a, **k):
        if before:
            before(*a, **k)
        try:
            return orig(*a, **k)
        finally:
            if after:
                after(*a, **k)

    setattr(obj, name, wrapped)


def main() -> int:
    from juce_theme_studio.core.logging_config import setup_logging
    from juce_theme_studio.gui.canvas import CanvasScene
    from juce_theme_studio.gui.main_window import MainWindow

    setup_logging()
    log(f"=== diagnose_input_freeze started; log file: {LOG} ===")

    app = LoudApplication(sys.argv)
    app.setApplicationName("JUCE Theme Studio (DIAG)")

    # Log every full scene rebuild (these recreate all items; a rebuild fired
    # from inside a mouse-press/modal is the prime suspect).
    _wrap(
        CanvasScene,
        "load_screen",
        before=lambda self, *a, **k: log(
            f">>> CanvasScene.load_screen (rebuild) grabber="
            f"{self.mouseGrabberItem() is not None}"
        ),
    )

    window = MainWindow()
    window.show()

    # Native-truth monitor: once per second compare the real NSWindow frame
    # against Qt's cached geometry; log only when something changes. Any
    # disagreement here IS the input offset.
    from PySide6.QtCore import QTimer

    last = {"sig": None}

    def _native_state():
        try:
            import ctypes

            import objc

            view = objc.objc_object(c_void_p=ctypes.c_void_p(int(window.winId())))
            nswin = view.window()
            if nswin is None:
                return None, None
            f = nswin.frame()
            try:
                origin, size = f.origin, f.size
                frame = (int(origin.x), int(origin.y), int(size.width), int(size.height))
            except AttributeError:  # older pyobjc returns nested tuples
                frame = (int(f[0][0]), int(f[0][1]), int(f[1][0]), int(f[1][1]))
            fs = bool(int(nswin.styleMask()) & (1 << 14))
            return fs, frame
        except Exception as exc:  # noqa: BLE001
            return f"ERR:{exc}", None

    def _poll_native():
        wh = window.windowHandle()
        qt_geo = wh.geometry() if wh else None
        native_fs, native_frame = _native_state()
        sig = (str(native_fs), str(native_frame), str(qt_geo),
               window.isFullScreen())
        if sig != last["sig"]:
            last["sig"] = sig
            log(
                f"~~~ window: nativeFS={native_fs} nativeFrame={native_frame} "
                f"qtGeo={qt_geo} isFullScreen()={window.isFullScreen()}"
            )

    mon = QTimer(window)
    mon.setInterval(1000)
    mon.timeout.connect(_poll_native)
    mon.start()

    # Log preview-mode flips: they silently strip ItemIsMovable from every item.
    # (Wrapped on the scene because the toolbar action's signal connection holds
    # the original bound method - wrapping window._toggle_preview would not fire.)
    _wrap(
        window._scene,
        "set_preview_mode",
        before=lambda enabled, *a, **k: log(f"### scene.set_preview_mode({enabled})"),
    )

    # Log when the asset-link dialog opens (it runs a nested loop; if it opens
    # while a canvas press is being handled, that is the corruption window).
    _wrap(
        window,
        "_offer_link_asset_to_control",
        before=lambda *a, **k: log(
            "=== _offer_link_asset_to_control: opening LinkAssetDialog.exec() "
            f"(nested loop). {_describe(window)}"
        ),
        after=lambda *a, **k: log("=== _offer_link_asset_to_control: returned"),
    )

    spy = MouseSpy(window)
    app.installEventFilter(spy)
    log("Instrumentation installed. Reproduce the bug now.")
    log(f"Idle state: {_describe(window)}")

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
