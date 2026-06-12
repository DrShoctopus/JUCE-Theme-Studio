#!/usr/bin/env bash
# Build JUCE Theme Studio and (optionally) JUCE Live Preview, then package
# each into a distributable DMG.
#
# Usage:
#   ./packaging/build_macos_app.sh
#
# To include JuceLivePreview, point JUCE_DIR at your JUCE install:
#   JUCE_DIR=~/JUCE ./packaging/build_macos_app.sh
#
# Outputs (all in dist/):
#   JUCE_Theme_Studio_<version>.dmg
#   JuceLivePreview_<version>.dmg   (only if JUCE is found)

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

STUDIO_VERSION="0.2.0"
PREVIEW_VERSION="1.0.0"
DIST_DIR="$ROOT/dist"
mkdir -p "$DIST_DIR"

# ── Helper: wrap a .app bundle in a DMG with an /Applications shortcut ───────
make_dmg() {
    local app_path="$1"   # path to .app bundle
    local vol_name="$2"   # volume label shown when DMG is mounted
    local out_dmg="$3"    # destination .dmg path

    local staging
    staging="$(mktemp -d)"
    cp -r "$app_path" "$staging/"
    ln -s /Applications "$staging/Applications"

    hdiutil create \
        -srcfolder "$staging" \
        -volname "$vol_name" \
        -fs HFS+ \
        -format UDZO \
        -ov \
        "$out_dmg"

    rm -rf "$staging"
}

# ── 1. Build JUCE Theme Studio .app via PyInstaller ──────────────────────────
echo "==> Building JUCE Theme Studio .app …"
python -m pip install --quiet pyinstaller
pyinstaller packaging/macos_app.spec --noconfirm --clean

STUDIO_APP="$DIST_DIR/JUCE Theme Studio.app"
if [[ ! -d "$STUDIO_APP" ]]; then
    echo "ERROR: expected app bundle not found: $STUDIO_APP" >&2
    ls -la "$DIST_DIR/" >&2 || true
    exit 1
fi
echo "Built: $STUDIO_APP"

# ── 2. Package JUCE Theme Studio → DMG ───────────────────────────────────────
echo "==> Packaging JUCE Theme Studio DMG …"
STUDIO_DMG="$DIST_DIR/JUCE_Theme_Studio_${STUDIO_VERSION}.dmg"
make_dmg "$STUDIO_APP" "JUCE Theme Studio $STUDIO_VERSION" "$STUDIO_DMG"
echo "Created: $STUDIO_DMG"

# ── 3. Build JuceLivePreview via CMake (optional) ────────────────────────────
PREVIEW_SRC="$ROOT/examples/juce_live_preview"

# Locate JUCE: honour the env var first, then probe common install paths.
if [[ -n "${JUCE_DIR:-}" && -d "${JUCE_DIR:-}" ]]; then
    JUCE_FOUND="$JUCE_DIR"
else
    JUCE_FOUND=""
    for candidate in ~/JUCE ~/Library/JUCE /Applications/JUCE ~/Developer/JUCE; do
        if [[ -d "$candidate" ]]; then
            JUCE_FOUND="$candidate"
            break
        fi
    done
fi

if [[ -z "$JUCE_FOUND" ]]; then
    echo ""
    echo "NOTICE: JUCE not found — skipping JuceLivePreview build."
    echo "        Re-run with  JUCE_DIR=/path/to/JUCE  to include it."
else
    echo "==> Building JuceLivePreview (JUCE: $JUCE_FOUND) …"
    cmake -B "$PREVIEW_SRC/build" -S "$PREVIEW_SRC" \
          "-DJUCE_DIR=$JUCE_FOUND" \
          -DCMAKE_BUILD_TYPE=Release
    cmake --build "$PREVIEW_SRC/build" --config Release

    # juce_add_gui_app places the bundle under:
    #   <build>/<target>_artefacts/<Config>/<Product Name>.app
    PREVIEW_APP=""
    while IFS= read -r -d '' candidate; do
        PREVIEW_APP="$candidate"
        break
    done < <(find "$PREVIEW_SRC/build" -maxdepth 5 \
        \( -name "JUCE Live Preview.app" -o -name "JuceLivePreview.app" \) \
        -type d -print0 2>/dev/null)

    if [[ -n "$PREVIEW_APP" ]]; then
        echo "Built: $PREVIEW_APP"
        PREVIEW_DMG="$DIST_DIR/JuceLivePreview_${PREVIEW_VERSION}.dmg"
        make_dmg "$PREVIEW_APP" "JUCE Live Preview $PREVIEW_VERSION" "$PREVIEW_DMG"
        echo "Created: $PREVIEW_DMG"
    else
        echo "WARNING: JuceLivePreview .app not found in build output." >&2
    fi
fi

echo ""
echo "Done. Outputs in: $DIST_DIR"
