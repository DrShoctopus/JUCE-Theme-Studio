# PyInstaller spec for a standalone macOS .app bundle.
# Run from juce_theme_studio/: pyinstaller packaging/macos_app.spec --noconfirm

from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

block_cipher = None
root = Path(SPECPATH).parent

datas: list = []
binaries: list = []
hiddenimports: list = collect_submodules("juce_theme_studio")

for package in (
    "PySide6",
    "tree_sitter",
    "tree_sitter_cpp",
    "cv2",
    "PIL",
    "git",
    "gitdb",
    "smmap",
):
    pkg_datas, pkg_binaries, pkg_hidden = collect_all(package)
    datas += pkg_datas
    binaries += pkg_binaries
    hiddenimports += pkg_hidden

a = Analysis(
    [str(root / "app" / "main.py")],
    pathex=[str(root.parent), str(root)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="JUCE Theme Studio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="JUCE Theme Studio",
)

app = BUNDLE(
    coll,
    name="JUCE Theme Studio.app",
    icon=None,
    bundle_identifier="com.jucethemestudio.JuceThemeStudio",
    version="0.2.0",
)
