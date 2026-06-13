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


def test_managed_destination_rejects_windows_style_path_escape(fixture_project: Path) -> None:
    loaded = _project_with_theme(fixture_project)

    from juce_theme_studio.core.managed_apply import plan_managed_apply

    with pytest.raises(ValueError, match="destination"):
        plan_managed_apply(
            loaded.manifest,
            loaded.root,
            destination_subdir=r"Source\..\escape",
        )


@pytest.mark.parametrize(
    "destination_subdir",
    ["Source/./ThemeStudio", r"Source\ThemeStudio"],
)
def test_managed_destination_subdir_is_normalized(
    fixture_project: Path,
    destination_subdir: str,
) -> None:
    loaded = _project_with_theme(fixture_project)

    from juce_theme_studio.core.managed_apply import plan_managed_apply

    plan = plan_managed_apply(
        loaded.manifest,
        loaded.root,
        destination_subdir=destination_subdir,
        apply_id="apply123",
    )

    assert plan.destination_subdir == "Source/ThemeStudio"


@pytest.mark.parametrize(
    "unsafe_apply_id",
    ["", "../escape", "/absolute", ".", "..", "nested/id", r"nested\id"],
)
def test_managed_apply_rejects_unsafe_apply_id(
    fixture_project: Path,
    unsafe_apply_id: str,
) -> None:
    loaded = _project_with_theme(fixture_project)

    from juce_theme_studio.core.managed_apply import plan_managed_apply

    with pytest.raises(ValueError, match="apply_id"):
        plan_managed_apply(loaded.manifest, loaded.root, apply_id=unsafe_apply_id)


def test_checksum_changes_when_file_changes(tmp_path: Path) -> None:
    from juce_theme_studio.core.managed_apply import sha256_file

    path = tmp_path / "file.txt"
    path.write_text("one\n", encoding="utf-8")
    first = sha256_file(path)
    path.write_text("two\n", encoding="utf-8")

    assert sha256_file(path) != first


def test_apply_operation_round_trips_through_dict() -> None:
    from juce_theme_studio.core.managed_apply import ApplyOperation, ApplyOperationKind

    operation = ApplyOperation(
        kind=ApplyOperationKind.REPLACE,
        source_rel="generated/ThemeAssets.cpp",
        target_rel="Source/ThemeStudio/ThemeAssets.cpp",
        source_checksum="source-sha",
        target_checksum="target-sha",
        backup_rel="backups/ThemeAssets.cpp",
        message="replace managed file",
    )

    assert ApplyOperation.from_dict(operation.to_dict()) == operation


def test_apply_operation_from_dict_requires_source_checksum() -> None:
    from juce_theme_studio.core.managed_apply import ApplyOperation

    with pytest.raises(KeyError, match="source_checksum"):
        ApplyOperation.from_dict(
            {
                "kind": "replace",
                "source_rel": "generated/ThemeAssets.cpp",
                "target_rel": "Source/ThemeStudio/ThemeAssets.cpp",
            }
        )


def test_plan_managed_apply_stages_generated_files(fixture_project: Path) -> None:
    loaded = _project_with_theme(fixture_project)

    from juce_theme_studio.core.managed_apply import (
        ApplyOperationKind,
        plan_managed_apply,
    )

    plan = plan_managed_apply(loaded.manifest, loaded.root, apply_id="apply-one")

    assert plan.transaction_dir == loaded.root / ".juce_theme_studio" / "applies" / "apply-one"
    assert (plan.generated_dir / "ThemeLayout.json").is_file()
    assert (plan.generated_dir / "ThemeAssets.cpp").is_file()
    assert any(op.target_rel == "Source/ThemeStudio/ThemeLayout.json" for op in plan.operations)
    assert {op.kind for op in plan.operations} == {ApplyOperationKind.CREATE}


def test_plan_flags_existing_unmanaged_destination_as_conflict(
    fixture_project: Path,
) -> None:
    loaded = _project_with_theme(fixture_project)
    dest = fixture_project / "Source" / "ThemeStudio"
    dest.mkdir(parents=True)
    (dest / "ThemeLayout.json").write_text("hand edited\n", encoding="utf-8")

    from juce_theme_studio.core.managed_apply import (
        ApplyOperationKind,
        plan_managed_apply,
    )

    plan = plan_managed_apply(loaded.manifest, loaded.root, apply_id="conflict")

    conflict = next(op for op in plan.operations if op.target_rel.endswith("ThemeLayout.json"))
    assert conflict.kind == ApplyOperationKind.CONFLICT
    assert "unexpected content" in conflict.message
    assert plan.has_conflicts


def test_plan_uses_normalized_destination_when_generating_operations(
    fixture_project: Path,
) -> None:
    loaded = _project_with_theme(fixture_project)

    from juce_theme_studio.core.managed_apply import plan_managed_apply

    plan = plan_managed_apply(
        loaded.manifest,
        loaded.root,
        destination_subdir=r"Source\ThemeStudio",
        apply_id="normalized-plan",
    )

    assert plan.destination_subdir == "Source/ThemeStudio"
    assert all(op.target_rel.startswith("Source/ThemeStudio/") for op in plan.operations)


def test_plan_stages_even_when_manual_export_subdir_is_invalid(
    fixture_project: Path,
) -> None:
    loaded = _project_with_theme(fixture_project)
    loaded.manifest.export_settings.output_subdir = "../outside"

    from juce_theme_studio.core.managed_apply import plan_managed_apply

    plan = plan_managed_apply(loaded.manifest, loaded.root, apply_id="safe-staging")

    assert (plan.generated_dir / "ThemeLayout.json").is_file()
    assert not plan.validation.has_blocking_errors
