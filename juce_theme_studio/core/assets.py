"""Asset import and management."""

from __future__ import annotations

import shutil
import uuid
from pathlib import Path

from juce_theme_studio.core.manifest import AssetEntry, ThemeManifest
from juce_theme_studio.core.types import STUDIO_DIR

SUPPORTED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif", ".bmp"}
SUPPORTED_FONT_EXTENSIONS = {".ttf", ".otf", ".woff", ".woff2"}


def studio_assets_dir(project_root: Path) -> Path:
    return project_root / STUDIO_DIR / "assets"


def relative_asset_path(filename: str) -> str:
    return f"assets/{filename}"


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
    return project_root / STUDIO_DIR / entry.relative_path


def asset_exists(project_root: Path, entry: AssetEntry) -> bool:
    return resolve_asset_path(project_root, entry).is_file()


def _normalize_source_path(project_root: Path, source: str | Path) -> str:
    """Canonical project-relative path for duplicate detection."""
    path = Path(source)
    if path.is_absolute():
        try:
            path = path.resolve().relative_to(project_root.resolve())
        except ValueError:
            return str(path)
    return str(path).replace("\\", "/")


def is_asset_imported(manifest: ThemeManifest, project_root: Path, source: str | Path) -> bool:
    """Return True if this project file was already copied into the asset library."""
    rel = _normalize_source_path(project_root, source)
    for entry in manifest.assets:
        if not entry.original_source:
            continue
        if _normalize_source_path(project_root, entry.original_source) == rel:
            return True
    return False


def _looks_like_sprite_sheet(source: Path) -> bool:
    """Heuristic: filename or multi-frame layout suggests a sprite sheet."""
    name = source.stem.lower()
    if any(keyword in name for keyword in ("strip", "sprite", "spritesheet", "frames", "atlas")):
        return True
    try:
        from juce_theme_studio.core.sprite_detect import detect_sprite_sheet

        result = detect_sprite_sheet(source)
        return result.frame_count > 1
    except Exception:
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
