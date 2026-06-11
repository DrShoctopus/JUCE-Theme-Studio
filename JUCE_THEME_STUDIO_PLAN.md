# JUCE Theme Studio — Implementation Plan

## Overview

Standalone Python desktop editor for designing, previewing, editing, and exporting JUCE plugin/app themes using sprite-sheet assets. All theme data lives in a non-destructive `.juce_theme_studio/` folder inside the loaded JUCE project.

## Architecture

```
juce_theme_studio/
├── app/           # Entry point
├── core/          # Domain models, alignment, snap, mapping, validation
├── gui/           # PySide6 UI, canvas, panels, dialogs
├── juce/          # Project scanner, C++ / JSON export
├── git_tools/     # Git status, diff, stage, commit (explicit only)
├── tests/         # pytest unit tests
└── examples/      # Mock JUCE fixture project
```

## Completed Phases

### Phase 1–6 ✅
Foundation, sprite controls, scanner, export, git flow, polish (see git history).

### Phase 7 — Editor Completeness ✅

- [x] Smart snap guides (grid + edge/center alignment while dragging)
- [x] Alignment menu (left/center/right/top/middle/bottom, canvas align)
- [x] Distribute horizontally / vertically
- [x] Copy / cut / paste / select all
- [x] Arrow-key nudge (Shift = 8px)
- [x] Screen settings panel (name, canvas size)
- [x] Export settings panel
- [x] Settings dialog (grid, snap, C++ namespace)
- [x] Export preview dialog before writing files
- [x] Sprite import configuration dialog
- [x] Auto-map scanned JUCE controls on project open
- [x] Project → Sync / Rescan mappings
- [x] Git backup branch button in commit dialog
- [x] Properties: layer visible/lock, sprite state frames
- [x] Scanner deduplication (.h skipped when .cpp exists)

## Usage

```bash
cd juce_theme_studio
pip install -e ".[dev]"
juce-theme-studio
```

## Tests

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -p pytest
```

## Phase 8 — Advanced Features ✅

- [x] tree-sitter-cpp + libclang optional C++ scanners (`juce/scanner_ast.py`)
- [x] OpenCV sprite auto-slice with Pillow fallback (`core/sprite_detect.py`)
- [x] Drag-and-drop assets onto canvas (`gui/widgets/asset_list.py`)
- [x] Theme version diffing (`core/theme_diff.py`, `ThemeDiffDialog`)
- [x] Live JUCE preview bridge + `examples/juce_live_preview/` companion app
