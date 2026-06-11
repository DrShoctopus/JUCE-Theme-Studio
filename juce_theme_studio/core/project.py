"""JUCE project loading and studio folder management."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from juce_theme_studio.core.logging_config import setup_logging
from juce_theme_studio.core.manifest import ThemeManifest
from juce_theme_studio.core.types import MANIFEST_FILENAME, STUDIO_DIR
from juce_theme_studio.juce.scanner import ScanResult, scan_juce_project


@dataclass
class LoadedProject:
    """An opened JUCE project with theme studio state."""

    root: Path
    studio_dir: Path
    manifest: ThemeManifest
    scan_result: ScanResult | None = None

    @property
    def manifest_path(self) -> Path:
        return self.studio_dir / MANIFEST_FILENAME


def ensure_studio_dirs(project_root: Path) -> Path:
    """Create .juce_theme_studio/ subfolders if missing."""
    studio = project_root / STUDIO_DIR
    for sub in ("screens", "assets", "exports", "backups", "logs"):
        (studio / sub).mkdir(parents=True, exist_ok=True)
    return studio


def load_project(project_root: Path) -> LoadedProject:
    """Open or initialize a JUCE theme project."""
    project_root = project_root.resolve()
    if not project_root.is_dir():
        raise NotADirectoryError(f"Not a directory: {project_root}")

    studio_dir = ensure_studio_dirs(project_root)
    setup_logging(studio_dir)
    manifest_path = studio_dir / MANIFEST_FILENAME

    scan_result = scan_juce_project(project_root)

    if manifest_path.exists():
        manifest = ThemeManifest.load(manifest_path)
        manifest.project_root = "."
        _merge_scanned_screens(manifest, scan_result)
    else:
        manifest = ThemeManifest(project_root=".")
        _populate_from_scan(manifest, scan_result)

    return LoadedProject(
        root=project_root,
        studio_dir=studio_dir,
        manifest=manifest,
        scan_result=scan_result,
    )


def save_project(loaded: LoadedProject) -> None:
    """Persist manifest to disk."""
    loaded.manifest.save(loaded.manifest_path)


def _populate_from_scan(manifest: ThemeManifest, scan: ScanResult) -> None:
    from juce_theme_studio.core.manifest import Screen

    for detected in scan.screens:
        manifest.screens.append(
            Screen(
                id=detected.id,
                name=detected.name,
                canvas_width=detected.suggested_width,
                canvas_height=detected.suggested_height,
                juce_component=detected.class_name,
                source_file=detected.source_file,
                manual=False,
            )
        )


def _merge_scanned_screens(manifest: ThemeManifest, scan: ScanResult) -> None:
    """Add newly detected screens without removing user edits."""
    existing_components = {s.juce_component for s in manifest.screens if s.juce_component}
    from juce_theme_studio.core.manifest import Screen

    for detected in scan.screens:
        if detected.class_name and detected.class_name in existing_components:
            continue
        manifest.screens.append(
            Screen(
                id=detected.id,
                name=detected.name,
                canvas_width=detected.suggested_width,
                canvas_height=detected.suggested_height,
                juce_component=detected.class_name,
                source_file=detected.source_file,
                manual=False,
            )
        )


def create_manual_screen(manifest: ThemeManifest, name: str, width: int = 800, height: int = 600):
    """Add a blank user-created screen."""
    import uuid

    from juce_theme_studio.core.manifest import Screen

    screen = Screen(
        id=uuid.uuid4().hex[:12],
        name=name,
        canvas_width=width,
        canvas_height=height,
        manual=True,
    )
    manifest.screens.append(screen)
    return screen
