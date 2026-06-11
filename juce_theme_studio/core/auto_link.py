"""Heuristic auto-linking of imported assets to scanned controls."""

from __future__ import annotations

import re
from pathlib import Path

from juce_theme_studio.core.assets import resolve_asset_path
from juce_theme_studio.core.controls import Control
from juce_theme_studio.core.manifest import AssetEntry, Screen, ThemeManifest
from juce_theme_studio.core.sprites import SpriteConfig, detect_sprite_grid
from juce_theme_studio.core.types import ControlType

_BACKGROUND_KEYWORDS = ("background", "backdrop", "wallpaper")
_BACKGROUND_SHORT = ("bg",)

_TYPE_KEYWORDS: dict[ControlType, tuple[str, ...]] = {
    ControlType.KNOB: ("knob", "dial", "rotary"),
    ControlType.SLIDER: ("slider", "fader"),
    ControlType.BUTTON: ("button", "btn"),
    ControlType.TOGGLE_BUTTON: ("toggle", "button", "btn"),
    ControlType.SWITCH: ("switch", "toggle"),
    ControlType.METER: ("meter", "vu"),
    ControlType.VU_METER: ("vu", "meter"),
    ControlType.GAIN_REDUCTION_METER: ("gr", "gain", "meter"),
    ControlType.LED: ("led", "indicator"),
    ControlType.LABEL: ("label", "title", "text"),
    ControlType.STATIC_IMAGE: ("image", "icon", "logo"),
}

_IDENTIFIER_RE = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?=[A-Z][a-z]|\b)|\d+")


def _split_identifiers(name: str) -> set[str]:
    parts = _IDENTIFIER_RE.findall(name)
    return {part.lower() for part in parts if part}


def _asset_tokens(asset: AssetEntry) -> set[str]:
    tokens = _split_identifiers(asset.name)
    if asset.original_source:
        tokens |= _split_identifiers(Path(asset.original_source).stem)
    return tokens


def _is_background_asset(asset: AssetEntry) -> bool:
    tokens = _asset_tokens(asset)
    if any(keyword in tokens for keyword in _BACKGROUND_KEYWORDS):
        return True
    return any(token in _BACKGROUND_SHORT for token in tokens)


def _score_control_asset(control: Control, asset: AssetEntry) -> float:
    if _is_background_asset(asset):
        return -1.0

    score = 0.0
    var_name = control.mapping.cpp_variable or control.name
    var_tokens = _split_identifiers(var_name)
    asset_tokens = _asset_tokens(asset)

    overlap = var_tokens & asset_tokens
    score += len(overlap) * 2.0

    type_keywords = _TYPE_KEYWORDS.get(control.control_type, ())
    for keyword in type_keywords:
        if keyword in asset.name.lower() or keyword in " ".join(asset_tokens):
            score += 3.0
            break

    if asset.is_sprite_sheet and control.control_type in {
        ControlType.KNOB,
        ControlType.BUTTON,
        ControlType.TOGGLE_BUTTON,
        ControlType.SLIDER,
        ControlType.METER,
        ControlType.VU_METER,
        ControlType.GAIN_REDUCTION_METER,
        ControlType.LED,
        ControlType.SWITCH,
    }:
        score += 1.0

    return score


def sprite_config_for_asset(project_root: Path, asset: AssetEntry) -> SpriteConfig | None:
    """Build sprite config for a sprite-sheet asset."""
    if not asset.is_sprite_sheet:
        return None
    if asset.sprite_config:
        return SpriteConfig.from_dict(asset.sprite_config)
    path = resolve_asset_path(project_root, asset)
    if not path.is_file():
        return None
    fw, fh, fc, cols = detect_sprite_grid(path)
    return SpriteConfig(frame_width=fw, frame_height=fh, frame_count=fc, columns=cols)


def link_control_to_asset(
    control: Control,
    asset: AssetEntry,
    project_root: Path,
) -> None:
    """Assign asset (and sprite config when needed) to a control."""
    control.asset_id = asset.id
    if asset.is_sprite_sheet:
        control.sprite_config = sprite_config_for_asset(project_root, asset)


def auto_link_screen_assets(
    screen: Screen,
    assets: list[AssetEntry],
    project_root: Path,
    *,
    used_asset_ids: set[str],
) -> int:
    """Link unassigned controls on one screen to best-matching assets."""
    linked = 0
    available = [a for a in assets if a.id not in used_asset_ids and not _is_background_asset(a)]

    for control in screen.controls:
        if control.asset_id:
            continue
        best_asset: AssetEntry | None = None
        best_score = 0.0
        for asset in available:
            score = _score_control_asset(control, asset)
            if score > best_score:
                best_score = score
                best_asset = asset
        if best_asset is None or best_score < 2.0:
            continue
        link_control_to_asset(control, best_asset, project_root)
        used_asset_ids.add(best_asset.id)
        available = [a for a in available if a.id != best_asset.id]
        linked += 1
    return linked


def auto_link_backgrounds(
    screens: list[Screen],
    assets: list[AssetEntry],
    *,
    used_asset_ids: set[str],
) -> int:
    """Assign background images to screens that do not have one."""
    backgrounds = [
        a for a in assets if _is_background_asset(a) and a.id not in used_asset_ids
    ]
    if not backgrounds:
        return 0

    linked = 0
    for screen in screens:
        if screen.background_asset_id:
            continue
        screen.background_asset_id = backgrounds[0].id
        used_asset_ids.add(backgrounds[0].id)
        linked += 1
        break
    return linked


def auto_link_project_assets(manifest: ThemeManifest, project_root: Path) -> int:
    """Link imported assets to scanned controls and screen backgrounds."""
    if not manifest.assets:
        return 0

    used_asset_ids = {
        c.asset_id
        for screen in manifest.screens
        for c in screen.controls
        if c.asset_id
    }
    used_asset_ids |= {
        s.background_asset_id
        for s in manifest.screens
        if s.background_asset_id
    }

    linked = auto_link_backgrounds(manifest.screens, manifest.assets, used_asset_ids=used_asset_ids)
    for screen in manifest.screens:
        linked += auto_link_screen_assets(
            screen,
            manifest.assets,
            project_root,
            used_asset_ids=used_asset_ids,
        )
    return linked
