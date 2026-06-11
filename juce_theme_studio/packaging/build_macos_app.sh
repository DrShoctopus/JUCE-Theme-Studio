#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python -m pip install pyinstaller
pyinstaller packaging/macos_app.spec --noconfirm --clean

APP_PATH="dist/JUCE Theme Studio.app"
if [[ ! -d "$APP_PATH" ]]; then
  echo "Expected app bundle not found: $APP_PATH" >&2
  ls -la dist/ >&2 || true
  exit 1
fi

echo "Built: $APP_PATH"
