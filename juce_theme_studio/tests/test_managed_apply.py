from __future__ import annotations

import json
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


def _write_apply_record(project_root: Path, apply_id: str, data: object) -> Path:
    path = project_root / ".juce_theme_studio" / "applies" / apply_id / "apply.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def _history_operation(target_rel: str, source_checksum: str) -> dict[str, str]:
    return {
        "kind": "replace",
        "source_rel": "ThemeLayout.json",
        "target_rel": target_rel,
        "source_checksum": source_checksum,
        "target_checksum": "",
        "backup_rel": "",
        "message": "",
    }


def _completed_record(
    operation: dict[str, str],
    *,
    completed_at: str = "2026-06-13T12:00:00+00:00",
    created_at: str = "2026-06-13T11:59:00+00:00",
) -> dict[str, object]:
    record = {
        "status": "completed",
        "created_at": created_at,
        "operations": [operation],
    }
    if completed_at:
        record["completed_at"] = completed_at
    return record


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


def test_plan_rejects_reused_apply_id(fixture_project: Path) -> None:
    loaded = _project_with_theme(fixture_project)

    from juce_theme_studio.core.managed_apply import plan_managed_apply

    plan_managed_apply(loaded.manifest, loaded.root, apply_id="reuse-me")

    with pytest.raises(FileExistsError, match="reuse-me"):
        plan_managed_apply(loaded.manifest, loaded.root, apply_id="reuse-me")


def test_plan_marks_matching_destination_unchanged(fixture_project: Path) -> None:
    loaded = _project_with_theme(fixture_project)

    from juce_theme_studio.core.managed_apply import ApplyOperationKind, plan_managed_apply

    seed = plan_managed_apply(loaded.manifest, loaded.root, apply_id="unchanged-seed")
    destination = loaded.root / "Source" / "ThemeStudio"
    destination.mkdir(parents=True)
    generated_layout = seed.generated_dir / "ThemeLayout.json"
    (destination / "ThemeLayout.json").write_bytes(generated_layout.read_bytes())

    plan = plan_managed_apply(loaded.manifest, loaded.root, apply_id="unchanged-plan")

    layout = next(op for op in plan.operations if op.target_rel.endswith("ThemeLayout.json"))
    assert layout.kind == ApplyOperationKind.UNCHANGED


def test_plan_replaces_when_latest_completed_record_matches_target_checksum(
    fixture_project: Path,
) -> None:
    loaded = _project_with_theme(fixture_project)
    target = loaded.root / "Source" / "ThemeStudio" / "ThemeLayout.json"
    target.parent.mkdir(parents=True)
    target.write_text("old managed layout\n", encoding="utf-8")

    from juce_theme_studio.core.managed_apply import (
        ApplyOperationKind,
        plan_managed_apply,
        sha256_file,
    )

    checksum = sha256_file(target)
    operation = _history_operation("Source/ThemeStudio/ThemeLayout.json", checksum)
    _write_apply_record(loaded.root, "managed-before", _completed_record(operation))

    plan = plan_managed_apply(loaded.manifest, loaded.root, apply_id="replace-plan")

    layout = next(op for op in plan.operations if op.target_rel.endswith("ThemeLayout.json"))
    assert layout.kind == ApplyOperationKind.REPLACE


def test_latest_completed_apply_uses_completed_timestamp_over_path_sort(
    fixture_project: Path,
) -> None:
    loaded = _project_with_theme(fixture_project)
    target = loaded.root / "Source" / "ThemeStudio" / "ThemeLayout.json"
    target.parent.mkdir(parents=True)
    target.write_text("newer managed layout\n", encoding="utf-8")

    from juce_theme_studio.core.managed_apply import (
        ApplyOperationKind,
        plan_managed_apply,
        sha256_file,
    )

    newer_checksum = sha256_file(target)
    newer = _history_operation("Source/ThemeStudio/ThemeLayout.json", newer_checksum)
    older = _history_operation("Source/ThemeStudio/ThemeLayout.json", "0" * 64)
    _write_apply_record(
        loaded.root,
        "a-newer",
        _completed_record(newer, completed_at="2026-06-13T12:00:00+00:00"),
    )
    _write_apply_record(
        loaded.root,
        "z-older",
        _completed_record(older, completed_at="2026-06-12T12:00:00+00:00"),
    )

    plan = plan_managed_apply(loaded.manifest, loaded.root, apply_id="timestamp-plan")

    layout = next(op for op in plan.operations if op.target_rel.endswith("ThemeLayout.json"))
    assert layout.kind == ApplyOperationKind.REPLACE


def test_latest_completed_apply_falls_back_to_created_timestamp(
    fixture_project: Path,
) -> None:
    loaded = _project_with_theme(fixture_project)
    target = loaded.root / "Source" / "ThemeStudio" / "ThemeLayout.json"
    target.parent.mkdir(parents=True)
    target.write_text("created timestamp managed layout\n", encoding="utf-8")

    from juce_theme_studio.core.managed_apply import (
        ApplyOperationKind,
        plan_managed_apply,
        sha256_file,
    )

    newer_checksum = sha256_file(target)
    newer = _history_operation("Source/ThemeStudio/ThemeLayout.json", newer_checksum)
    older = _history_operation("Source/ThemeStudio/ThemeLayout.json", "0" * 64)
    _write_apply_record(
        loaded.root,
        "a-newer-created",
        _completed_record(
            newer,
            completed_at="",
            created_at="2026-06-13T12:00:00+00:00",
        ),
    )
    _write_apply_record(
        loaded.root,
        "z-older-created",
        _completed_record(
            older,
            completed_at="",
            created_at="2026-06-12T12:00:00+00:00",
        ),
    )

    plan = plan_managed_apply(loaded.manifest, loaded.root, apply_id="created-time-plan")

    layout = next(op for op in plan.operations if op.target_rel.endswith("ThemeLayout.json"))
    assert layout.kind == ApplyOperationKind.REPLACE


def test_malformed_completed_records_are_ignored_and_conflict_remains_conflict(
    fixture_project: Path,
) -> None:
    loaded = _project_with_theme(fixture_project)
    target = loaded.root / "Source" / "ThemeStudio" / "ThemeLayout.json"
    target.parent.mkdir(parents=True)
    target.write_text("hand edited\n", encoding="utf-8")

    from juce_theme_studio.core.managed_apply import (
        ApplyOperationKind,
        plan_managed_apply,
        sha256_file,
    )

    target_checksum = sha256_file(target)
    _write_apply_record(loaded.root, "aa-array", [])
    _write_apply_record(loaded.root, "ab-string", "oops")
    _write_apply_record(
        loaded.root,
        "ac-null-operations",
        {"status": "completed", "operations": None},
    )
    _write_apply_record(
        loaded.root,
        "ad-bogus-operations",
        {
            "status": "completed",
            "operations": [
                "oops",
                {
                    "kind": "replace",
                    "source_rel": "ThemeLayout.json",
                    "target_rel": "../Source/ThemeStudio/ThemeLayout.json",
                    "source_checksum": target_checksum,
                },
                {
                    "kind": "replace",
                    "source_rel": "ThemeLayout.json",
                    "target_rel": r"Source\..\ThemeStudio\ThemeLayout.json",
                    "source_checksum": target_checksum,
                },
                {
                    "kind": "replace",
                    "source_rel": "ThemeLayout.json",
                    "target_rel": "Source/ThemeStudio/ThemeLayout.json",
                    "source_checksum": "not-a-checksum",
                },
            ],
        },
    )
    _write_apply_record(
        loaded.root,
        "zz-invalid-authorizer",
        {
            "status": "completed",
            "operations": [
                {
                    "target_rel": "Source/ThemeStudio/ThemeLayout.json",
                    "source_checksum": target_checksum,
                }
            ],
        },
    )

    plan = plan_managed_apply(loaded.manifest, loaded.root, apply_id="malformed-plan")

    layout = next(op for op in plan.operations if op.target_rel.endswith("ThemeLayout.json"))
    assert layout.kind == ApplyOperationKind.CONFLICT
