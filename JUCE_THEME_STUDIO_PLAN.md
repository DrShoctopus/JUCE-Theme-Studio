# JUCE Theme Studio — Implementation Plan

## Overview

Standalone Python desktop editor for designing, previewing, editing, and exporting JUCE plugin/app themes using sprite-sheet assets. All theme data lives in a non-destructive `.juce_theme_studio/` folder inside the loaded JUCE project.

## Architecture

```
juce_theme_studio/
├── app/           # Entry point, application bootstrap
├── core/          # Domain models, manifest, assets, sprites, undo, validation
├── gui/           # PySide6 UI: main window, canvas, panels
├── juce/          # Project scanner, C++ / JSON export
├── git_tools/     # Git status, diff, stage, commit (explicit only)
├── tests/         # pytest unit/integration tests
└── examples/      # Mock JUCE fixture project for tests
```

### Key design decisions

| Area | Choice | Rationale |
|------|--------|-----------|
| GUI | PySide6 + QGraphicsScene | Real-time drag/resize, layers, zoom/pan |
| Persistence | Versioned JSON manifest | Human-readable, relative paths |
| Safety | Never touch original assets/code | Copy to `.juce_theme_studio/assets/` |
| Export | Generate into `exports/` first | Preview + backup before integration |
| Coordinates | Top-left origin, pixel units | Matches JUCE `setBounds` |

## Phase 1 — Foundation ✅

- [x] `pyproject.toml` with PySide6, Pillow, GitPython, pytest, ruff
- [x] Manifest schema v1.0.0 (`core/manifest.py`)
- [x] Project loader/creator (`core/project.py`)
- [x] Asset import/copy (`core/assets.py`)
- [x] Main window layout (toolbar, sidebars, canvas, bottom panel)
- [x] Editable canvas with background + static image controls
- [x] Move/resize, grid snap, zoom/pan

## Phase 2 — Sprite Controls ✅

- [x] Sprite sheet config (strip/grid, frames, states)
- [x] Control types: knob, button, toggle, switch, meter, slider, LED, label, background
- [x] Properties inspector (numeric bounds, sprite settings)
- [x] Layer tree (show/hide, lock, z-order)
- [x] Undo/redo command stack
- [x] Preview simulation (value sliders, button states, preview vs edit mode)

## Phase 3 — JUCE Project Scanner ✅

- [x] Scan `.jucer`, `CMakeLists.txt`, `Source/`, `Resources/`, `BinaryData/`
- [x] Heuristic C++ screen detection (`juce::Component`, `paint`, `resized`, etc.)
- [x] Populate sidebar with detected + manual screens
- [x] Auto-mapping metadata fields on controls

## Phase 4 — Export ✅

- [x] `ThemeLayout.json`
- [x] Generated C++ helpers (`ThemeAssets`, `ThemeLookAndFeel`, `GeneratedThemeComponents`)
- [x] Asset copy to export folder
- [x] Backup system (`backups/`)
- [x] Validation report (warnings + blocking errors)

## Phase 5 — Git Commit Flow ✅

- [x] Detect repo, show branch/status
- [x] Diff preview for selected files
- [x] Backup branch option
- [x] Stage + commit only on explicit button press

## Phase 6 — Polish ✅

- [x] Keyboard shortcuts (undo/redo, delete, duplicate, save)
- [x] Alignment helpers
- [x] File logging to `.juce_theme_studio/logs/`
- [x] README with full usage
- [x] Example fixture project
- [x] Core tests (serialization, sprites, scanner, export, validation)

## MVP acceptance path

1. Launch GUI → `python -m juce_theme_studio.app.main`
2. Open `examples/mock_juce_project/`
3. Import background + sprite sheet
4. Add knob/button/meter controls
5. Move/resize on canvas
6. Save → reload preserves state
7. Export → `ThemeLayout.json` + C++ in `exports/`
8. Git panel shows status; commit requires confirmation

## Limitations (documented in README)

- Preview approximates JUCE rendering; does not embed JUCE runtime
- C++ scanner is heuristic, not a full AST parse
- SVG preview uses rasterized fallback where Qt SVG is unavailable
- WEBP requires Pillow with WEBP support

## Future improvements

- tree-sitter-cpp / libclang for precise C++ mapping
- OpenCV-assisted sprite frame detection
- Live JUCE plugin preview bridge
- Theme diff across versions
- Multi-screen template library
