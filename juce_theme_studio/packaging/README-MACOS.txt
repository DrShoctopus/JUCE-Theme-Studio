JUCE Theme Studio — macOS build
================================

WHAT YOU DOWNLOADED
-------------------
This zip contains a macOS application (.app) built by GitHub Actions.
It is unsigned, so macOS Gatekeeper may block it the first time you open it.

JUCE Theme Studio.app
  The main theme editor. Double-click to launch.

JUCE Live Preview.app (separate zip, if you enabled that build)
  Optional companion app for live native JUCE preview. In Theme Studio,
  point Live JUCE Preview to this app.


FIRST LAUNCH (unsigned app)
---------------------------
If macOS says the app "cannot be opened" or is from an unidentified developer:

  1. Right-click the .app → Open → Open again
     — or —
  2. System Settings → Privacy & Security → Open Anyway

You only need to do this once per app.


INSTALL
-------
  1. Unzip the download.
  2. Drag JUCE Theme Studio.app to Applications (or run from Downloads).
  3. Open the app using the steps above if Gatekeeper blocks it.


LIVE JUCE PREVIEW (optional)
----------------------------
  1. Unzip JUCE-Live-Preview-macOS.zip.
  2. In Theme Studio: Live JUCE Preview panel → browse to JUCE Live Preview.app
     (select the app bundle, or Contents/MacOS/JUCE Live Preview).


DEVELOPER INSTALL (alternative)
-------------------------------
If you prefer Python instead of the .app, use the python-wheel-macos artifact:

  pip install juce_theme_studio-*.whl
  juce-theme-studio
