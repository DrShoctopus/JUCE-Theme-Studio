# JUCE Theme Studio — User Guide

Standalone Python desktop application for designing, previewing, editing, and exporting
JUCE plugin and app themes using sprite-sheet assets.

---

## Table of Contents

1. [Requirements](#requirements)
2. [Installation](#installation)
3. [Launch](#launch)
4. [Opening a Project](#opening-a-project)
5. [Asset Library](#asset-library)
6. [Sprite Sheets](#sprite-sheets)
7. [Screens & Canvas](#screens--canvas)
8. [Adding Controls](#adding-controls)
9. [Properties Panel](#properties-panel)
10. [Preview Mode](#preview-mode)
11. [Layout Tools](#layout-tools)
12. [JUCE Code Scanning & Mapping](#juce-code-scanning--mapping)
13. [Theme Colors](#theme-colors)
14. [Export](#export)
15. [Live JUCE Preview](#live-juce-preview)
16. [Theme Diff](#theme-diff)
17. [Git Integration](#git-integration)
18. [Keyboard Shortcuts](#keyboard-shortcuts)
19. [Settings](#settings)
20. [Tests](#tests)
21. [Optional Extras](#optional-extras)
22. [Limitations](#limitations)
23. [Safety Guarantees](#safety-guarantees)

---

## Requirements

- Python 3.11+
- macOS, Linux, or Windows (PySide6 Qt stack)

---

## Installation

```bash
cd juce_theme_studio
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

---

## Launch

```bash
juce-theme-studio
# or
python -m juce_theme_studio.app.main
```

> **macOS note:** If the `juce-theme-studio` command is unavailable, use the
> `PYTHONPATH` form: `PYTHONPATH=. python -m juce_theme_studio.app.main`

---

## Opening a Project

1. Click **Open Project** in the toolbar (or **File → Open Project…**).
2. Select your JUCE project root — the folder containing `.jucer`,
   `CMakeLists.txt`, or `Source/`.
3. A non-destructive editor folder is created:

   ```text
   .juce_theme_studio/
     theme_project.json   — all layout, asset, and color data
     screens/             — per-screen metadata
     assets/              — imported image copies
     exports/             — generated C++ and JSON files
     backups/             — previous export snapshots
     logs/                — studio.log
   ```

4. Detected `juce::Component` screens appear in the **Screens** list.
   Use **New Screen** for manual layouts.

Your original source files and assets are **never** modified.

When you reopen a project, saved control positions and sizes are restored from
`theme_project.json`. Controls can be dragged and resized unless they are
**locked** (Layers panel) or **Preview Mode** is enabled.

---

## Asset Library

Images under your JUCE project (`Resources/`, `BinaryData/`, etc.) are detected on
open. You are prompted to copy them into the library if it is empty.

| Button | Action |
|---|---|
| **Import Asset** | Pick any PNG, JPG, WEBP, TTF, or OTF file from disk. |
| **From Project** | Copy all detected project images into `.juce_theme_studio/assets/` (skips already-imported files). |
| **Import Sprite Sheet** | Import a strip or grid image with frame configuration. |
| **Set Background** | Assign the selected asset as the screen's background image. |
| **Delete Asset** | Remove an asset from the library (shows usage warning if in use). |

### Assigning Assets to Controls

Three workflows are available:

1. **Click-to-assign** — click an asset in the library, then click a control on the
   canvas. Press **Esc** to cancel.
2. **Drag to empty canvas area** — creates a new control at the drop position,
   already linked to the asset.
3. **Drag onto existing control** — a *Link Asset to Control* dialog appears for
   confirmation.

---

## Sprite Sheets

1. Click **Import Sprite Sheet** in the Asset Library.
2. Select a PNG/JPG/WEBP strip or grid image.
3. Configure in the dialog:
   - **Layout** — Horizontal Strip, Vertical Strip, or Grid.
   - **Frame count** — total number of animation frames.
   - **Frame width / height** — pixel dimensions of one frame.
   - **Slice all frames into library** — saves each frame as a separate asset
     (`name_frame_00.png`, …). Useful for LED states and single-state images.
   - **Keep full sprite sheet** — retains the master strip/grid for strip-based
     controls (knobs, meters, sliders).

---

## Screens & Canvas

- **Screens list (left panel)** — click a screen to load it on the canvas.
  Auto-detected screens show `[ClassName]`; manual screens are tagged `(manual)`.
- **New Screen** — opens prompts for name, width, and height.
- **Fit** / **Fit Canvas** — zoom to fit the canvas in the viewport.
- **Screen Settings panel (right)** — edit canvas width and height.
- **Canvas navigation** — scroll wheel to zoom; middle-click drag or space+drag to pan.

---

## Adding Controls

1. Select a screen in the sidebar.
2. Pick a control type from **Control Palette**:

   | Type | Description |
   |---|---|
   | **Knob** | Rotary control driven by a sprite strip. |
   | **Button** | Momentary push button with hover/active/disabled states. |
   | **Toggle** | Latching on/off button. |
   | **Switch** | Horizontal or vertical flip switch. |
   | **Meter** | Generic level meter. |
   | **VU Meter** | VU-ballistics meter. |
   | **GR Meter** | Gain-reduction meter (inverted scale). |
   | **Slider** | Linear horizontal or vertical slider. |
   | **LED** | Indicator light with off/on sprite frames. |
   | **Image** | Static decorative image; no interaction. |
   | **Label** | Text label with configurable font and color. |
   | **Panel** | Background region. |

3. Optionally select an asset first — it will be linked on creation.
4. Click **Add Control**.
5. **Drag** to move; **drag the bottom-right handle** to resize.
6. Use the **Layers** panel for z-order, visibility, and lock.

### Multi-select

Hold **Shift** to add controls to the selection. **Ctrl/Cmd+A** selects all.

### Layers Panel

- **Visibility** (eye icon) — show/hide on canvas.
- **Lock** (padlock icon) — prevent drag/resize.
- **Drag rows** to reorder z-order.

---

## Properties Panel

Shown for the currently selected control. All edits are undoable.

### Geometry

| Field | Description |
|---|---|
| **X**, **Y** | Position from canvas top-left, in pixels. Matches `setBounds(x, y, w, h)`. |
| **W**, **H** | Width and height in pixels. |

### Sprite Sheet

Visible when a sprite sheet asset is linked.

| Field | Description |
|---|---|
| **Frame count** | Total frames in the strip/grid. |
| **Frame width / height** | Pixel size of one frame. |
| **Layout** | Horizontal Strip, Vertical Strip, or Grid. |
| **Columns** (Grid) | Number of columns in the grid. |
| **Preview state** | Normal / Hover / Active / Disabled frame preview. |
| **Value** (0–1) | Simulates knob/slider/meter position. |

### JUCE Mapping

| Field | Description |
|---|---|
| **JUCE class** | C++ type, e.g. `juce::Slider`. |
| **C++ variable** | Member variable name, e.g. `gainSlider`. |
| **Parameter ID** | APVTS parameter string, e.g. `"gain"`. Autocompleted from scanned attachments. |
| **Screen name** | Auto-set from the current screen. |

---

## Preview Mode

Toggle **Preview Mode** in the toolbar to simulate runtime appearance:

- Editing is disabled (no drag/resize).
- **Preview Simulation** panel (right) controls button state:
  Normal / Hover / Active / Disabled.
- **Value** in Properties simulates knob/slider/meter positions.

Coordinates use top-left origin matching JUCE `setBounds(x, y, w, h)`.

---

## Layout Tools

### Alignment (Layout menu)

Select 2+ controls then choose an alignment:

| Action | Description |
|---|---|
| Align Left | Left edges to leftmost control. |
| Align H Center | Horizontal centers aligned. |
| Align Right | Right edges to rightmost control. |
| Align Top | Top edges to topmost control. |
| Align V Center | Vertical centers aligned. |
| Align Bottom | Bottom edges to bottommost control. |
| Align to Canvas H Center | Center horizontally on canvas. |
| Align to Canvas V Center | Center vertically on canvas. |

### Distribute

Select 3+ controls:

- **Distribute Horizontally** — equal horizontal spacing.
- **Distribute Vertically** — equal vertical spacing.

### Smart Snap Guides

Blue guides appear while dragging when a control's edge or center aligns with another
control or the canvas. Configure in **File → Settings…**.

### Nudge

| Keys | Distance |
|---|---|
| Arrow keys | 1 px |
| Shift + Arrow keys | 8 px |

---

## JUCE Code Scanning & Mapping

On project open, the scanner reads `Source/` for:

- `juce::Component` subclasses → one screen per class.
- Member variables (`juce::Slider`, `juce::TextButton`, etc.) → placeholder controls
  with JUCE class and variable pre-filled.
- `AudioProcessorValueTreeState` `*Attachment` constructors → extract parameter IDs.
- Image file references → offered in the asset import prompt.

**Scanner backends** (used in order of precision):

1. **libclang** (optional) — full AST via Clang.
2. **tree-sitter-cpp** (optional) — fast incremental AST.
3. **Regex fallback** — always available.

### Refreshing Mappings

| Action | Description |
|---|---|
| **Project → Rescan Project** | Re-scan all C++ source; add new screens and mappings. |
| **Project → Sync JUCE Mappings** | Apply only new mappings; no new screens. |

Parameter IDs from scanned `*Attachment` calls are offered as autocomplete in the
**Parameter ID** field of the Properties panel.

---

## Theme Colors

**Project → Theme Colors…** opens the palette editor:

| Color | Usage |
|---|---|
| Background | Main window/plugin background. |
| Surface | Panel and widget backgrounds. |
| Primary | Accent color for interactive elements. |
| On-Primary | Text/icons on primary-colored surfaces. |
| Text | Default text color. |
| Meter (low / mid / high) | Meter segment colors. |

Values are embedded in `ThemeLayout.json` and applied at runtime by
`ThemeLookAndFeel`. Click **Restore Defaults** to reset.

---

## Export

1. Click **Export** (toolbar or **File → Export…**).
2. The **Export Preview** dialog shows files to be written and lists
   validation warnings or errors.
3. Confirm to write files to `.juce_theme_studio/exports/`.
4. Previous exports are backed up to `.juce_theme_studio/backups/`.

### Generated Files

| File | Description |
|---|---|
| `ThemeLayout.json` | Full layout, sprite config, and palette — loaded at runtime. |
| `ThemeAssets.h/cpp` | Loads images and slices sprite frames via `ImageCache`. |
| `ThemeLookAndFeel.h/cpp` | Draws sprite knobs/buttons/meters; applies palette colors. |
| `GeneratedThemeComponents.h/cpp` | `ThemeScreenComponent` renders a screen from JSON; `applyScreenLayout()` positions your components. |
| `README-INTEGRATION.md` | CMake snippet and usage example. |
| `assets/` | Copied image files. |

### Export Settings Panel

| Setting | Description |
|---|---|
| Export JSON | Include `ThemeLayout.json`. |
| Export C++ | Include the four C++ files. |
| Copy assets | Copy images to the export directory. |
| Namespace | C++ namespace (set globally in **Settings**). |
| Output subdirectory | Subdirectory under `exports/`. |

### Validation

Check the **Validation** tab in the Log Panel before exporting. Blocking errors prevent
export; warnings can be bypassed with confirmation.

---

## Live JUCE Preview

1. Build the companion: `examples/juce_live_preview/CMakeLists.txt` (requires JUCE).
2. In the **Live Preview** panel (right), browse to the built binary.
3. Enable **Auto-export on edit** to re-export on every canvas change.
4. Click **Launch Preview** — the companion renders `ThemeLayout.json` and reloads
   automatically on each export.

---

## Theme Diff

**Project → Theme Diff…** compares two theme manifest versions. Shows added, removed,
and modified screens, controls, and assets. Useful for reviewing changes before
committing.

---

## Git Integration

1. Click **Commit** in the toolbar (enabled only in Git repositories).
2. Review changed files under `.juce_theme_studio/`.
3. Preview diffs for any file.
4. Edit the commit message.
5. Check the confirmation box and press **OK**.

**The app never commits automatically.** A warning is shown when unrelated repository
changes are detected.

The **Git Status** tab in the Log Panel shows current status of `.juce_theme_studio/`
and updates after Save and Export.

---

## Keyboard Shortcuts

| Action | macOS | Windows / Linux |
|---|---|---|
| Save | Cmd+S | Ctrl+S |
| Undo | Cmd+Z | Ctrl+Z |
| Redo | Cmd+Shift+Z | Ctrl+Shift+Z |
| Copy | Cmd+C | Ctrl+C |
| Cut | Cmd+X | Ctrl+X |
| Paste | Cmd+V | Ctrl+V |
| Duplicate | Cmd+D | Ctrl+D |
| Delete | Delete | Delete |
| Select All | Cmd+A | Ctrl+A |
| Nudge 1px | Arrow keys | Arrow keys |
| Nudge 8px | Shift+Arrow | Shift+Arrow |
| Cancel assign | Esc | Esc |
| User Guide | F1 | F1 |

---

## Settings

**File → Settings…** (or **Settings** toolbar button):

| Setting | Description |
|---|---|
| Grid size | Background dot grid spacing in pixels. |
| Snap to grid | Snap control edges to grid while dragging. |
| C++ namespace | Namespace wrapping all generated code (default: `ThemeStudio`). |

---

## Tests

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -p pytest
```

Example fixture: `examples/mock_juce_project/`

---

## Optional Extras

```bash
pip install -e ".[full]"           # All optional backends
pip install -e ".[parsing]"        # tree-sitter-cpp
pip install -e ".[vision]"         # opencv-python-headless
pip install -e ".[clang]"          # libclang
```

| Backend | Benefit |
|---|---|
| **tree-sitter-cpp** / **libclang** | Precise C++ component and parameter scanning. Falls back to regex without them. |
| **opencv-python-headless** | Improved sprite frame auto-detection for ambiguous grids. |

---

## Limitations

- Native JUCE preview requires building the companion example with JUCE installed.
- libclang needs Xcode CLT paths on macOS for best results.
- SVG rendering depends on Qt/Pillow capabilities.
- WEBP requires Pillow built with WEBP support.

---

## Safety Guarantees

- Does **not** delete or rewrite original JUCE project files.
- Does **not** auto-commit.
- Uses relative paths in the manifest where possible.
- Logs all operations to the GUI and `.juce_theme_studio/logs/studio.log`.
- Generated C++ is written only to `.juce_theme_studio/exports/`; existing source
  files are never overwritten.

---

*Copyright © 2026 Shoctopus — MIT License*
