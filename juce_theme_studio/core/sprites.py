"""Sprite sheet configuration and frame slicing."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from PIL import Image

from juce_theme_studio.core.types import ButtonMode, MeterOrientation, SpriteLayout


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


@dataclass
class SpriteConfig:
    """Configuration for slicing and mapping sprite sheet frames."""

    layout: SpriteLayout = SpriteLayout.HORIZONTAL_STRIP
    frame_count: int = 1
    frame_width: int = 64
    frame_height: int = 64
    columns: int = 1
    rows: int = 1
    state_names: list[str] = field(default_factory=list)
    default_frame: int = 0
    hover_frame: int | None = None
    active_frame: int | None = None
    disabled_frame: int | None = None
    min_value: float = 0.0
    max_value: float = 1.0
    bipolar: bool = False
    reversed: bool = False
    # Knob metadata
    start_angle_deg: float = -135.0
    end_angle_deg: float = 135.0
    # Button
    button_mode: ButtonMode = ButtonMode.MOMENTARY
    # Meter
    meter_orientation: MeterOrientation = MeterOrientation.VERTICAL
    peak_hold: bool = False
    min_db: float = -60.0
    max_db: float = 6.0
    warning_db: float = -6.0
    clip_db: float = 0.0
    # Slider
    slider_orientation: str = "horizontal"
    track_asset_id: str | None = None
    thumb_asset_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "layout": self.layout.value,
            "frame_count": self.frame_count,
            "frame_width": self.frame_width,
            "frame_height": self.frame_height,
            "columns": self.columns,
            "rows": self.rows,
            "state_names": list(self.state_names),
            "default_frame": self.default_frame,
            "hover_frame": self.hover_frame,
            "active_frame": self.active_frame,
            "disabled_frame": self.disabled_frame,
            "min_value": self.min_value,
            "max_value": self.max_value,
            "bipolar": self.bipolar,
            "reversed": self.reversed,
            "start_angle_deg": self.start_angle_deg,
            "end_angle_deg": self.end_angle_deg,
            "button_mode": self.button_mode.value,
            "meter_orientation": self.meter_orientation.value,
            "peak_hold": self.peak_hold,
            "min_db": self.min_db,
            "max_db": self.max_db,
            "warning_db": self.warning_db,
            "clip_db": self.clip_db,
            "slider_orientation": self.slider_orientation,
            "track_asset_id": self.track_asset_id,
            "thumb_asset_id": self.thumb_asset_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SpriteConfig:
        layout = data.get("layout", SpriteLayout.HORIZONTAL_STRIP.value)
        if isinstance(layout, str):
            try:
                layout = SpriteLayout(layout)
            except ValueError:
                layout = SpriteLayout.HORIZONTAL_STRIP
        button_mode_raw = str(data.get("button_mode", ButtonMode.MOMENTARY.value))
        try:
            button_mode = ButtonMode(button_mode_raw)
        except ValueError:
            button_mode = ButtonMode.MOMENTARY
        meter_raw = str(data.get("meter_orientation", MeterOrientation.VERTICAL.value))
        try:
            meter_orientation = MeterOrientation(meter_raw)
        except ValueError:
            meter_orientation = MeterOrientation.VERTICAL
        return cls(
            layout=layout,
            frame_count=int(data.get("frame_count", 1)),
            frame_width=int(data.get("frame_width", 64)),
            frame_height=int(data.get("frame_height", 64)),
            columns=int(data.get("columns", 1)),
            rows=int(data.get("rows", 1)),
            state_names=list(data.get("state_names", [])),
            default_frame=int(data.get("default_frame", 0)),
            hover_frame=_optional_int(data.get("hover_frame")),
            active_frame=_optional_int(data.get("active_frame")),
            disabled_frame=_optional_int(data.get("disabled_frame")),
            min_value=float(data.get("min_value", 0.0)),
            max_value=float(data.get("max_value", 1.0)),
            bipolar=bool(data.get("bipolar", False)),
            reversed=bool(data.get("reversed", False)),
            start_angle_deg=float(data.get("start_angle_deg", -135.0)),
            end_angle_deg=float(data.get("end_angle_deg", 135.0)),
            button_mode=button_mode,
            meter_orientation=meter_orientation,
            peak_hold=bool(data.get("peak_hold", False)),
            min_db=float(data.get("min_db", -60.0)),
            max_db=float(data.get("max_db", 6.0)),
            warning_db=float(data.get("warning_db", -6.0)),
            clip_db=float(data.get("clip_db", 0.0)),
            slider_orientation=str(data.get("slider_orientation", "horizontal")),
            track_asset_id=_optional_str(data.get("track_asset_id")),
            thumb_asset_id=_optional_str(data.get("thumb_asset_id")),
        )


def frame_index_for_value(config: SpriteConfig, normalized: float) -> int:
    """Map normalized value [0,1] to sprite frame index."""
    value = max(0.0, min(1.0, normalized))
    if config.reversed:
        value = 1.0 - value
    if config.bipolar:
        # Bipolar knobs: 0.5 maps to center frame; extremes at 0 and 1.
        value = abs(value - 0.5) * 2.0
    if config.frame_count <= 1:
        return config.default_frame
    idx = int(round(value * (config.frame_count - 1)))
    return max(0, min(config.frame_count - 1, idx))


def extract_frame(
    image_path: Path,
    config: SpriteConfig,
    frame_index: int,
) -> Image.Image:
    """Extract a single frame from a sprite sheet."""
    with Image.open(image_path) as source_img:
        img = source_img.convert("RGBA")
        x, y = frame_position(config, frame_index)
        box = (x, y, x + config.frame_width, y + config.frame_height)
        return img.crop(box).copy()


def frame_position(config: SpriteConfig, frame_index: int) -> tuple[int, int]:
    """Return top-left pixel position for frame index."""
    idx = max(0, min(config.frame_count - 1, frame_index))
    if config.layout == SpriteLayout.HORIZONTAL_STRIP:
        return idx * config.frame_width, 0
    if config.layout == SpriteLayout.VERTICAL_STRIP:
        return 0, idx * config.frame_height
    col = idx % max(1, config.columns)
    row = idx // max(1, config.columns)
    return col * config.frame_width, row * config.frame_height


def detect_sprite_grid(image_path: Path) -> tuple[int, int, int, int]:
    """Detect sprite grid via OpenCV (if available) or Pillow heuristics."""
    from juce_theme_studio.core.sprite_detect import detect_sprite_sheet

    result = detect_sprite_sheet(image_path)
    return result.frame_width, result.frame_height, result.frame_count, result.columns


class PreviewState(str, Enum):
    NORMAL = "normal"
    HOVER = "hover"
    ACTIVE = "active"
    DISABLED = "disabled"


def frame_for_button_state(config: SpriteConfig, state: PreviewState) -> int:
    """Resolve frame index for button preview state."""
    if state == PreviewState.DISABLED and config.disabled_frame is not None:
        return config.disabled_frame
    if state == PreviewState.ACTIVE and config.active_frame is not None:
        return config.active_frame
    if state == PreviewState.HOVER and config.hover_frame is not None:
        return config.hover_frame
    return config.default_frame
