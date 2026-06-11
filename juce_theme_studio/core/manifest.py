"""Theme project manifest schema and serialization."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from juce_theme_studio.core.controls import Control
from juce_theme_studio.core.types import SCHEMA_VERSION


@dataclass
class Screen:
    """Editable screen/page in the theme project."""

    id: str
    name: str
    canvas_width: int = 800
    canvas_height: int = 600
    background_asset_id: str | None = None
    controls: list[Control] = field(default_factory=list)
    juce_component: str = ""
    source_file: str = ""
    manual: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "canvas_width": self.canvas_width,
            "canvas_height": self.canvas_height,
            "background_asset_id": self.background_asset_id,
            "controls": [c.to_dict() for c in self.controls],
            "juce_component": self.juce_component,
            "source_file": self.source_file,
            "manual": self.manual,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Screen:
        return cls(
            id=str(data["id"]),
            name=str(data.get("name", "Screen")),
            canvas_width=int(data.get("canvas_width", 800)),
            canvas_height=int(data.get("canvas_height", 600)),
            background_asset_id=data.get("background_asset_id"),
            controls=[Control.from_dict(c) for c in data.get("controls", [])],
            juce_component=str(data.get("juce_component", "")),
            source_file=str(data.get("source_file", "")),
            manual=bool(data.get("manual", False)),
        )


@dataclass
class AssetEntry:
    """Registered asset in the theme project."""

    id: str
    name: str
    relative_path: str
    asset_type: str = "image"
    is_sprite_sheet: bool = False
    original_source: str = ""
    sprite_config: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data: dict[str, Any] = {
            "id": self.id,
            "name": self.name,
            "relative_path": self.relative_path,
            "asset_type": self.asset_type,
            "is_sprite_sheet": self.is_sprite_sheet,
            "original_source": self.original_source,
        }
        if self.sprite_config is not None:
            data["sprite_config"] = self.sprite_config
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AssetEntry:
        return cls(
            id=str(data["id"]),
            name=str(data.get("name", "")),
            relative_path=str(data.get("relative_path", "")),
            asset_type=str(data.get("asset_type", "image")),
            is_sprite_sheet=bool(data.get("is_sprite_sheet", False)),
            original_source=str(data.get("original_source", "")),
            sprite_config=data.get("sprite_config"),
        )


@dataclass
class ExportSettings:
    """User preferences for export."""

    export_json: bool = True
    export_cpp: bool = True
    copy_assets: bool = True
    namespace: str = "ThemeStudio"
    output_subdir: str = "exports"

    def to_dict(self) -> dict[str, Any]:
        return {
            "export_json": self.export_json,
            "export_cpp": self.export_cpp,
            "copy_assets": self.copy_assets,
            "namespace": self.namespace,
            "output_subdir": self.output_subdir,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExportSettings:
        return cls(
            export_json=bool(data.get("export_json", True)),
            export_cpp=bool(data.get("export_cpp", True)),
            copy_assets=bool(data.get("copy_assets", True)),
            namespace=str(data.get("namespace", "ThemeStudio")),
            output_subdir=str(data.get("output_subdir", "exports")),
        )


@dataclass
class ThemeManifest:
    """Root manifest stored in .juce_theme_studio/theme_project.json."""

    schema_version: str = SCHEMA_VERSION
    project_root: str = "."
    screens: list[Screen] = field(default_factory=list)
    assets: list[AssetEntry] = field(default_factory=list)
    export_settings: ExportSettings = field(default_factory=ExportSettings)
    last_opened_screen_id: str | None = None
    grid_size: int = 8
    snap_to_grid: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "project_root": self.project_root,
            "screens": [s.to_dict() for s in self.screens],
            "assets": [a.to_dict() for a in self.assets],
            "export_settings": self.export_settings.to_dict(),
            "last_opened_screen_id": self.last_opened_screen_id,
            "grid_size": self.grid_size,
            "snap_to_grid": self.snap_to_grid,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ThemeManifest:
        return cls(
            schema_version=str(data.get("schema_version", SCHEMA_VERSION)),
            project_root=str(data.get("project_root", ".")),
            screens=[Screen.from_dict(s) for s in data.get("screens", [])],
            assets=[AssetEntry.from_dict(a) for a in data.get("assets", [])],
            export_settings=ExportSettings.from_dict(data.get("export_settings", {})),
            last_opened_screen_id=data.get("last_opened_screen_id"),
            grid_size=int(data.get("grid_size", 8)),
            snap_to_grid=bool(data.get("snap_to_grid", True)),
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
            f.write("\n")

    @classmethod
    def load(cls, path: Path) -> ThemeManifest:
        with path.open(encoding="utf-8") as f:
            return cls.from_dict(json.load(f))

    def get_screen(self, screen_id: str) -> Screen | None:
        for screen in self.screens:
            if screen.id == screen_id:
                return screen
        return None

    def get_asset(self, asset_id: str) -> AssetEntry | None:
        for asset in self.assets:
            if asset.id == asset_id:
                return asset
        return None
