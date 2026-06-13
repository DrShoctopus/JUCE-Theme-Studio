"""Tests for manifest serialization."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from juce_theme_studio.core.controls import Control, create_control
from juce_theme_studio.core.manifest import Screen, ThemeManifest
from juce_theme_studio.core.sprites import SpriteConfig
from juce_theme_studio.core.types import ControlType, SpriteLayout


def test_manifest_roundtrip(tmp_path: Path) -> None:
    manifest = ThemeManifest(
        project_root=".",
        screens=[
            Screen(
                id="s1",
                name="Main",
                canvas_width=800,
                canvas_height=600,
                controls=[
                    create_control(ControlType.KNOB, "Gain", 10, 20, 64, 64, "a1", SpriteConfig(
                        layout=SpriteLayout.HORIZONTAL_STRIP,
                        frame_count=8,
                        frame_width=64,
                        frame_height=64,
                    )),
                ],
            )
        ],
    )
    path = tmp_path / "theme_project.json"
    manifest.save(path)
    loaded = ThemeManifest.load(path)
    assert loaded.schema_version == "1.0.0"
    assert len(loaded.screens) == 1
    assert loaded.screens[0].controls[0].name == "Gain"
    assert loaded.screens[0].controls[0].sprite_config is not None
    assert loaded.screens[0].controls[0].sprite_config.frame_count == 8


def test_manifest_save_preserves_existing_file_when_write_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "theme_project.json"
    path.write_text('{"old": true}\n', encoding="utf-8")
    manifest = ThemeManifest()

    def fail_dump(*args, **kwargs) -> None:  # noqa: ANN002, ANN003
        raise RuntimeError("boom")

    monkeypatch.setattr(json, "dump", fail_dump)

    with pytest.raises(RuntimeError, match="boom"):
        manifest.save(path)

    assert path.read_text(encoding="utf-8") == '{"old": true}\n'


def test_control_serialization() -> None:
    c = Control(name="Test", control_type=ControlType.BUTTON)
    data = c.to_dict()
    restored = Control.from_dict(data)
    assert restored.name == "Test"
    assert restored.control_type == ControlType.BUTTON
