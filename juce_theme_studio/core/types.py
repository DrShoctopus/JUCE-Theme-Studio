"""Shared type definitions and enums."""

from __future__ import annotations

from enum import Enum


class ControlType(str, Enum):
    KNOB = "knob"
    BUTTON = "button"
    TOGGLE_BUTTON = "toggle_button"
    SWITCH = "switch"
    METER = "meter"
    VU_METER = "vu_meter"
    GAIN_REDUCTION_METER = "gain_reduction_meter"
    SLIDER = "slider"
    LED = "led"
    SCREEN = "screen"
    BACKGROUND = "background"
    STATIC_IMAGE = "static_image"
    LABEL = "label"


class SpriteLayout(str, Enum):
    HORIZONTAL_STRIP = "horizontal_strip"
    VERTICAL_STRIP = "vertical_strip"
    GRID = "grid"


class ButtonMode(str, Enum):
    MOMENTARY = "momentary"
    LATCHING = "latching"


class MeterOrientation(str, Enum):
    HORIZONTAL = "horizontal"
    VERTICAL = "vertical"


SCHEMA_VERSION = "1.0.0"
STUDIO_DIR = ".juce_theme_studio"
MANIFEST_FILENAME = "theme_project.json"
