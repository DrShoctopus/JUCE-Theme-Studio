from __future__ import annotations

from pathlib import Path

import pytest

from juce_theme_studio.core.assets import import_asset
from juce_theme_studio.core.controls import create_control
from juce_theme_studio.core.manifest import Screen
from juce_theme_studio.core.project import load_project
from juce_theme_studio.core.sprites import SpriteConfig
from juce_theme_studio.core.types import ControlType


def _project_with_theme(fixture_project: Path):
    loaded = load_project(fixture_project)
    manifest = loaded.manifest
    entry = import_asset(
        manifest,
        fixture_project,
        fixture_project / "Resources" / "knob_strip.png",
        is_sprite_sheet=True,
    )
    screen = manifest.screens[0] if manifest.screens else Screen(id="s1", name="Main")
    if screen not in manifest.screens:
        manifest.screens.append(screen)
    control = create_control(
        ControlType.KNOB,
        "Gain",
        100,
        200,
        64,
        64,
        entry.id,
        SpriteConfig(frame_count=8, frame_width=64, frame_height=64),
    )
    control.mapping.cpp_variable = "gainSlider"
    control.mapping.parameter_id = "gain"
    screen.controls.append(control)
    return loaded


def test_load_project_creates_apply_history_directory(fixture_project: Path) -> None:
    loaded = load_project(fixture_project)

    assert (loaded.studio_dir / "applies").is_dir()


def test_managed_destination_rejects_path_escape(fixture_project: Path) -> None:
    loaded = _project_with_theme(fixture_project)

    from juce_theme_studio.core.managed_apply import plan_managed_apply

    with pytest.raises(ValueError, match="destination"):
        plan_managed_apply(
            loaded.manifest,
            loaded.root,
            destination_subdir="../Source/ThemeStudio",
        )


def test_checksum_changes_when_file_changes(tmp_path: Path) -> None:
    from juce_theme_studio.core.managed_apply import sha256_file

    path = tmp_path / "file.txt"
    path.write_text("one\n", encoding="utf-8")
    first = sha256_file(path)
    path.write_text("two\n", encoding="utf-8")

    assert sha256_file(path) != first
