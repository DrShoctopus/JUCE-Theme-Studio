"""Control model definitions."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from typing import Any

from juce_theme_studio.core.sprites import SpriteConfig
from juce_theme_studio.core.types import ControlType


@dataclass
class ControlMapping:
    """Maps a visual control to JUCE code elements."""

    juce_class: str = ""
    cpp_variable: str = ""
    parameter_id: str = ""
    screen_name: str = ""
    tooltip: str = ""
    export_target: str = "generated"

    def to_dict(self) -> dict[str, Any]:
        return {
            "juce_class": self.juce_class,
            "cpp_variable": self.cpp_variable,
            "parameter_id": self.parameter_id,
            "screen_name": self.screen_name,
            "tooltip": self.tooltip,
            "export_target": self.export_target,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ControlMapping:
        return cls(
            juce_class=str(data.get("juce_class", "")),
            cpp_variable=str(data.get("cpp_variable", "")),
            parameter_id=str(data.get("parameter_id", "")),
            screen_name=str(data.get("screen_name", "")),
            tooltip=str(data.get("tooltip", "")),
            export_target=str(data.get("export_target", "generated")),
        )


@dataclass
class Control:
    """A placed control on a screen canvas."""

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    name: str = "Control"
    control_type: ControlType = ControlType.STATIC_IMAGE
    x: int = 0
    y: int = 0
    width: int = 64
    height: int = 64
    z_index: int = 0
    locked: bool = False
    visible: bool = True
    aspect_locked: bool = True
    asset_id: str | None = None
    sprite_config: SpriteConfig | None = None
    mapping: ControlMapping = field(default_factory=ControlMapping)
    # Preview state
    preview_value: float = 0.0
    preview_on: bool = False
    label_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "control_type": self.control_type.value,
            "x": self.x,
            "y": self.y,
            "width": self.width,
            "height": self.height,
            "z_index": self.z_index,
            "locked": self.locked,
            "visible": self.visible,
            "aspect_locked": self.aspect_locked,
            "asset_id": self.asset_id,
            "sprite_config": self.sprite_config.to_dict() if self.sprite_config else None,
            "mapping": self.mapping.to_dict(),
            "preview_value": self.preview_value,
            "preview_on": self.preview_on,
            "label_text": self.label_text,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Control:
        ctype = data.get("control_type", ControlType.STATIC_IMAGE.value)
        if isinstance(ctype, str):
            ctype = ControlType(ctype)
        sprite_raw = data.get("sprite_config")
        return cls(
            id=str(data.get("id", uuid.uuid4().hex[:12])),
            name=str(data.get("name", "Control")),
            control_type=ctype,
            x=int(data.get("x", 0)),
            y=int(data.get("y", 0)),
            width=int(data.get("width", 64)),
            height=int(data.get("height", 64)),
            z_index=int(data.get("z_index", 0)),
            locked=bool(data.get("locked", False)),
            visible=bool(data.get("visible", True)),
            aspect_locked=bool(data.get("aspect_locked", True)),
            asset_id=data.get("asset_id"),
            sprite_config=SpriteConfig.from_dict(sprite_raw) if sprite_raw else None,
            mapping=ControlMapping.from_dict(data.get("mapping", {})),
            preview_value=float(data.get("preview_value", 0.0)),
            preview_on=bool(data.get("preview_on", False)),
            label_text=str(data.get("label_text", "")),
        )


def create_control(
    control_type: ControlType,
    name: str,
    x: int = 0,
    y: int = 0,
    width: int = 64,
    height: int = 64,
    asset_id: str | None = None,
    sprite_config: SpriteConfig | None = None,
) -> Control:
    """Factory for new controls with sensible defaults."""
    if sprite_config is None and control_type in {
        ControlType.KNOB,
        ControlType.BUTTON,
        ControlType.TOGGLE_BUTTON,
        ControlType.SWITCH,
        ControlType.METER,
        ControlType.VU_METER,
        ControlType.GAIN_REDUCTION_METER,
        ControlType.SLIDER,
        ControlType.LED,
    }:
        sprite_config = SpriteConfig()
    return Control(
        name=name,
        control_type=control_type,
        x=x,
        y=y,
        width=width,
        height=height,
        asset_id=asset_id,
        sprite_config=sprite_config,
    )
