JUCE Theme Studio — macOS build
================================

WHAT YOU DOWNLOADED
-------------------
This DMG contains a macOS application built by GitHub Actions.
The app is ad-hoc signed but not notarized, so macOS Gatekeeper will
show a security prompt the first time you open it.

  JUCE Theme Studio.dmg
    The main theme editor. Mount, drag to Applications, launch.

  JuceLivePreview.dmg  (separate download, if that build was enabled)
    Optional companion app for live native JUCE preview.


INSTALL
-------
  1. Open the .dmg file.
  2. Drag the app to the Applications shortcut inside the DMG.
  3. Eject the DMG.
  4. Open the app — see Gatekeeper notes below if macOS blocks it.


GATEKEEPER — FIRST LAUNCH
--------------------------
macOS may show one of two security messages for ad-hoc-signed apps:

  MESSAGE: "JUCE Theme Studio cannot be opened because the developer
            cannot be verified."
  FIX:     Right-click (or Ctrl-click) the app → Open → Open

  MESSAGE: "JUCE Theme Studio is damaged and can't be opened."
  FIX:     Run this once in Terminal, then reopen the app:

             xattr -cr "/Applications/JUCE Theme Studio.app"

  ALTERNATIVE FOR EITHER:
    System Settings → Privacy & Security → scroll down → Open Anyway

You only need to do this once per app.


LIVE JUCE PREVIEW (optional)
----------------------------
  1. Mount and install JuceLivePreview from its DMG.
  2. Apply the same Gatekeeper fix above if needed.
  3. In Theme Studio: Live JUCE Preview panel → browse to
     JUCE Live Preview.app in /Applications
     (or select Contents/MacOS/JUCE Live Preview inside the bundle).


DEVELOPER INSTALL (alternative)
--------------------------------
If you prefer running from Python source instead of the .app:

  pip install juce_theme_studio-*.whl
  juce-theme-studio

Copyright (c) 2026 Shoctopus — MIT License
