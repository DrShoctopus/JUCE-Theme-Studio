"""Asset import and management."""

from __future__ import annotations

import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from juce_theme_studio.core.manifest import AssetEntry, ThemeManifest
from juce_theme_studio.core.types import STUDIO_DIR

SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp"}
SUPPORTED_FONT_EXTENSIONS = {".ttf", ".otf", ".woff", ".woff2"}


def studio_assets_dir(project_root: Path) -> Path:
    return project_root / STUDIO_DIR / "assets"


def relative_asset_path(filename: str) -> str:
    return f"assets/{filename}"


def _asset_library_root(project_root: Path) -> Path:
    return studio_assets_dir(project_root).resolve()


def import_asset(
    manifest: ThemeManifest,
    project_root: Path,
    source_path: Path,
    *,
    name: str | None = None,
    is_sprite_sheet: bool = False,
) -> AssetEntry:
    """Copy asset into .juce_theme_studio/assets/ without modifying source."""
    source_path = source_path.resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"Asset not found: {source_path}")

    ext = source_path.suffix.lower()
    if ext in SUPPORTED_IMAGE_EXTENSIONS:
        asset_type = "image"
    elif ext in SUPPORTED_FONT_EXTENSIONS:
        asset_type = "font"
    else:
        asset_type = "other"

    dest_dir = studio_assets_dir(project_root)
    dest_dir.mkdir(parents=True, exist_ok=True)

    asset_id = uuid.uuid4().hex[:12]
    safe_name = name or source_path.stem
    dest_filename = f"{asset_id}_{source_path.name}"
    dest_path = dest_dir / dest_filename

    shutil.copy2(source_path, dest_path)

    try:
        rel_source = str(source_path.relative_to(project_root.resolve()))
    except ValueError:
        rel_source = str(source_path)

    entry = AssetEntry(
        id=asset_id,
        name=safe_name,
        relative_path=relative_asset_path(dest_filename),
        asset_type=asset_type,
        is_sprite_sheet=is_sprite_sheet,
        original_source=rel_source,
    )
    manifest.assets.append(entry)
    return entry


def resolve_asset_path(project_root: Path, entry: AssetEntry) -> Path:
    rel = Path(entry.relative_path)
    if rel.is_absolute():
        raise ValueError(f"Asset path points outside the asset library: {entry.relative_path}")

    path = (project_root / STUDIO_DIR / rel).resolve()
    try:
        path.relative_to(_asset_library_root(project_root))
    except ValueError as exc:
        raise ValueError(
            f"Asset path points outside the asset library: {entry.relative_path}"
        ) from exc
    return path


def asset_exists(project_root: Path, entry: AssetEntry) -> bool:
    try:
        return resolve_asset_path(project_root, entry).is_file()
    except ValueError:
        return False


def _normalize_source_path(project_root: Path, source: str | Path) -> str:
    """Canonical project-relative path for duplicate detection."""
    path = Path(source)
    if path.is_absolute():
        try:
            path = path.resolve().relative_to(project_root.resolve())
        except ValueError:
            return str(path)
    return str(path).replace("\\", "/")


@dataclass(frozen=True)
class AssetUsage:
    screen_name: str
    description: str


def get_asset_usages(manifest: ThemeManifest, asset_id: str) -> list[AssetUsage]:
    """Return where an asset is referenced in screens and controls."""
    usages: list[AssetUsage] = []
    for screen in manifest.screens:
        if screen.background_asset_id == asset_id:
            usages.append(AssetUsage(screen.name, "background"))
        for control in screen.controls:
            if control.asset_id == asset_id:
                label = control.mapping.cpp_variable or control.name or control.id
                usages.append(AssetUsage(screen.name, label))
    return usages


def delete_asset(
    manifest: ThemeManifest,
    project_root: Path,
    asset_id: str,
    *,
    clear_references: bool = False,
) -> AssetEntry | None:
    """Remove an asset from the library and delete its file on disk."""
    entry = manifest.get_asset(asset_id)
    if entry is None:
        return None

    path = resolve_asset_path(project_root, entry)
    if path.is_file():
        path.unlink()
    manifest.assets = [a for a in manifest.assets if a.id != asset_id]

    if clear_references:
        for screen in manifest.screens:
            if screen.background_asset_id == asset_id:
                screen.background_asset_id = None
            for control in screen.controls:
                if control.asset_id == asset_id:
                    control.asset_id = None

    return entry


def unimported_project_images(
    manifest: ThemeManifest,
    project_root: Path,
    image_paths: list[str],
) -> list[str]:
    """Return project image paths not yet copied into the asset library."""
    return [
        rel_path
        for rel_path in image_paths
        if not is_asset_imported(manifest, project_root, rel_path)
    ]


def _looks_like_sprite_sheet(source: Path) -> bool:
    """Heuristic: very wide or tall images are likely sprite strips."""
    try:
        with Image.open(source) as img:
            w, h = img.size
            return w > h * 3 or h > w * 3
    except Exception:
        return False


def is_asset_imported(manifest: ThemeManifest, project_root: Path, source: str | Path) -> bool:
    """Return True if this project file was already copied into the asset library."""
    rel = _normalize_source_path(project_root, source)
    for entry in manifest.assets:
        if not entry.original_source:
            continue
        if _normalize_source_path(project_root, entry.original_source) == rel:
            return True
    return False


def import_project_assets(
    manifest: ThemeManifest,
    project_root: Path,
    image_paths: list[str],
    *,
    skip_existing: bool = True,
) -> list[AssetEntry]:
    """Copy project image files into the asset library without modifying sources."""
    project_root = project_root.resolve()
    imported: list[AssetEntry] = []

    for rel_path in image_paths:
        if skip_existing and is_asset_imported(manifest, project_root, rel_path):
            continue
        source = project_root / rel_path
        if not source.is_file():
            continue
        entry = import_asset(
            manifest,
            project_root,
            source,
            name=source.stem,
            is_sprite_sheet=_looks_like_sprite_sheet(source),
        )
        imported.append(entry)

    return imported
