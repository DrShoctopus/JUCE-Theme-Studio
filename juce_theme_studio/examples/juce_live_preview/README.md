# JUCE Live Preview (companion app)

Optional native JUCE window that loads `ThemeLayout.json` exported by JUCE Theme Studio for runtime-accurate preview on macOS.

## Build (requires JUCE 7+)

```bash
# Install JUCE, then:
cd examples/juce_live_preview
cmake -B build -DCMAKE_BUILD_TYPE=Debug
cmake --build build
```

Binary: `build/JuceLivePreview`

## Use with Theme Studio

1. Build this target on your Mac.
2. In Theme Studio → **Live JUCE Preview** panel → browse to `JuceLivePreview`.
3. Enable **Auto-export on edit**.
4. Edits debounce-export to `.juce_theme_studio/exports/ThemeLayout.json`; the preview reloads when that file changes.

## CLI

```bash
./build/JuceLivePreview /path/to/.juce_theme_studio/exports/ThemeLayout.json
```

The preview watches the layout file's modification time and reloads when `ThemeLayout.json` changes.

## Note

This example provides a minimal JUCE shell. Wire `ThemeLayout.json` parsing into your `paint()` / `resized()` using the generated `ThemeStudio` C++ helpers from export for full fidelity.
