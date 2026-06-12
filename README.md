# JUCE Theme Studio

> Visual theme editor for JUCE audio plugin and application projects.

JUCE Theme Studio is a standalone Python desktop application that lets you design,
preview, edit, and export JUCE plugin/app themes using sprite-sheet assets — all
without touching your original JUCE source files.

---

## Features

- **Visual canvas editor** — drag and drop controls onto a JUCE-sized canvas
- **12 control types** — Knob, Button, Toggle, Switch, Meter, VU Meter, GR Meter, Slider, LED, Static Image, Label, Background
- **Sprite sheet support** — import horizontal/vertical strips and grids; auto-detect frame count with OpenCV
- **JUCE code scanner** — auto-detect `juce::Component` screens and member variables from C++ source; extract APVTS parameter IDs
- **Smart layout tools** — snap guides, alignment, distribution, grid, nudge
- **Theme palette** — edit background, surface, primary, text, and meter colors
- **Export** — generate ready-to-use `ThemeLayout.json`, `ThemeAssets.h/cpp`, `ThemeLookAndFeel.h/cpp`, `GeneratedThemeComponents.h/cpp`
- **Live JUCE preview** — optional native companion app renders `ThemeLayout.json` in real time
- **Full undo/redo** — every edit is reversible
- **Git integration** — explicit commit dialog scoped to `.juce_theme_studio/`
- **Theme diff** — compare manifest versions before committing
- **Non-destructive** — all data lives in `.juce_theme_studio/`; original files are never modified

---

## Requirements

| Dependency | Version |
|---|---|
| Python | 3.11+ |
| PySide6 | 6.6+ |
| Pillow | 10.0+ |
| GitPython | 3.1+ |

Optional extras for advanced parsing and sprite detection:

```bash
pip install -e ".[full]"          # tree-sitter-cpp + opencv + libclang
pip install -e ".[parsing]"       # tree-sitter-cpp only
pip install -e ".[vision]"        # opencv-python-headless only
pip install -e ".[clang]"         # libclang only
```

---

## Installation

```bash
git clone https://github.com/DrShoctopus/JUCE-Theme-Studio.git
cd JUCE-Theme-Studio/juce_theme_studio
python -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Launch

```bash
juce-theme-studio
# or
python -m juce_theme_studio.app.main
```

---

## Quick Start

1. **Open a JUCE project** — click *Open Project* and select your project root.
2. **Import assets** — use *Import Asset*, *From Project*, or *Import Sprite Sheet*.
3. **Add controls** — pick a type from the Control Palette and click *Add Control*.
4. **Link assets** — click an asset, then click a control to assign.
5. **Set JUCE mappings** — fill in *JUCE class*, *C++ variable*, and *Parameter ID* in Properties.
6. **Export** — click *Export* to generate C++ and JSON files.
7. **Commit** — click *Commit* to version your theme data in Git.

See the full [User Guide](juce_theme_studio/README.md) for detailed instructions on every feature.

---

## Documentation

| Document | Description |
|---|---|
| [User Guide](juce_theme_studio/README.md) | Full installation, usage, and keyboard shortcuts |
| [Live Preview](juce_theme_studio/examples/juce_live_preview/README.md) | Build and use the native JUCE preview companion |
| [In-app Help](##) | *Help → User Guide* (F1) inside the application |

---

## Development

```bash
# Run tests
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -p pytest

# Lint
ruff check .

# Type check
mypy juce_theme_studio
```

---

## License

MIT License — Copyright © 2026 Shoctopus

See [LICENSE](LICENSE) for the full text.
