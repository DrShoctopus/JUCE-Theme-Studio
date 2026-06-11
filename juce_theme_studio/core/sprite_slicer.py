"""Slice sprite sheets into individual library assets."""

from __future__ import annotations

import uuid
from pathlib import Path

from juce_theme_studio.core.assets import relative_asset_path, studio_assets_dir
from juce_theme_studio.core.manifest import AssetEntry, ThemeManifest
from juce_theme_studio.core.sprites import SpriteConfig, extract_frame


def slice_sprite_sheet_to_library(
    manifest: ThemeManifest,
    project_root: Path,
    source_path: Path,
    sprite_config: SpriteConfig,
    *,
    base_name: str | None = None,
) -> list[AssetEntry]:
    """Extract each frame as a separate PNG asset in the library."""
    source_path = source_path.resolve()
    base_name = base_name or source_path.stem
    dest_dir = studio_assets_dir(project_root)
    dest_dir.mkdir(parents=True, exist_ok=True)

    try:
        rel_source = str(source_path.relative_to(project_root.resolve()))
    except ValueError:
        rel_source = str(source_path)

    entries: list[AssetEntry] = []
    for frame_index in range(sprite_config.frame_count):
        frame_img = extract_frame(source_path, sprite_config, frame_index)
        asset_id = uuid.uuid4().hex[:12]
        frame_name = f"{base_name}_frame_{frame_index:02d}"
        dest_filename = f"{asset_id}_{frame_name}.png"
        dest_path = dest_dir / dest_filename
        frame_img.save(dest_path, format="PNG")

        entry = AssetEntry(
            id=asset_id,
            name=frame_name,
            relative_path=relative_asset_path(dest_filename),
            asset_type="image",
            is_sprite_sheet=False,
            original_source=rel_source,
            sprite_config=None,
        )
        manifest.assets.append(entry)
        entries.append(entry)

    return entries
