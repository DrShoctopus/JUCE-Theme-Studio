from __future__ import annotations

import json
import shutil
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


def _write_history_backup(
    project_root: Path,
    apply_id: str,
    target_rel: str,
    content: str = "previous managed target\n",
) -> tuple[str, str]:
    from juce_theme_studio.core.managed_apply import sha256_file

    backup = (
        project_root
        / ".juce_theme_studio"
        / "applies"
        / apply_id
        / "backups"
        / target_rel
    )
    backup.parent.mkdir(parents=True, exist_ok=True)
    backup.write_text(content, encoding="utf-8")
    return str(backup.relative_to(project_root)).replace("\\", "/"), sha256_file(backup)


def _history_replace_operation(
    project_root: Path,
    apply_id: str,
    target_rel: str,
    source_checksum: str,
    backup_content: str = "previous managed target\n",
) -> dict[str, str]:
    operation = _history_operation(target_rel, source_checksum)
    backup_rel, target_checksum = _write_history_backup(
        project_root,
        apply_id,
        target_rel,
        backup_content,
    )
    operation["backup_rel"] = backup_rel
    operation["target_checksum"] = target_checksum
    return operation


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
    operation = _history_replace_operation(
        loaded.root,
        "managed-before",
        "Source/ThemeStudio/ThemeLayout.json",
        checksum,
    )
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
    newer = _history_replace_operation(
        loaded.root,
        "a-newer",
        "Source/ThemeStudio/ThemeLayout.json",
        newer_checksum,
    )
    older = _history_replace_operation(
        loaded.root,
        "z-older",
        "Source/ThemeStudio/ThemeLayout.json",
        "0" * 64,
    )
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
    newer = _history_replace_operation(
        loaded.root,
        "a-newer-created",
        "Source/ThemeStudio/ThemeLayout.json",
        newer_checksum,
    )
    older = _history_replace_operation(
        loaded.root,
        "z-older-created",
        "Source/ThemeStudio/ThemeLayout.json",
        "0" * 64,
    )
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


def test_partially_invalid_completed_record_is_ignored(fixture_project: Path) -> None:
    loaded = _project_with_theme(fixture_project)
    target = loaded.root / "Source" / "ThemeStudio" / "ThemeLayout.json"
    target.parent.mkdir(parents=True)
    target.write_text("hand edited\n", encoding="utf-8")

    from juce_theme_studio.core.managed_apply import (
        ApplyOperationKind,
        plan_managed_apply,
        sha256_file,
    )

    valid = _history_replace_operation(
        loaded.root,
        "partial-invalid",
        "Source/ThemeStudio/ThemeLayout.json",
        sha256_file(target),
    )
    invalid = _history_operation("../escape.json", sha256_file(target))
    _write_apply_record(
        loaded.root,
        "partial-invalid",
        {
            "status": "completed",
            "created_at": "2026-06-13T11:59:00+00:00",
            "completed_at": "2026-06-13T12:00:00+00:00",
            "operations": [valid, invalid],
        },
    )

    plan = plan_managed_apply(loaded.manifest, loaded.root, apply_id="partial-invalid-plan")

    layout = next(op for op in plan.operations if op.target_rel.endswith("ThemeLayout.json"))
    assert layout.kind == ApplyOperationKind.CONFLICT


def test_completed_apply_records_ignore_replace_with_invalid_target_checksum(
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

    apply_id = "bad-target-checksum"
    operation = _history_replace_operation(
        loaded.root,
        apply_id,
        "Source/ThemeStudio/ThemeLayout.json",
        sha256_file(target),
    )
    operation["target_checksum"] = "not-a-checksum"
    _write_apply_record(loaded.root, apply_id, _completed_record(operation))

    plan = plan_managed_apply(loaded.manifest, loaded.root, apply_id="bad-target-plan")

    layout = next(op for op in plan.operations if op.target_rel.endswith("ThemeLayout.json"))
    assert layout.kind == ApplyOperationKind.CONFLICT


def test_completed_apply_records_ignore_replace_without_backup_rel(
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

    apply_id = "missing-backup-rel"
    operation = _history_replace_operation(
        loaded.root,
        apply_id,
        "Source/ThemeStudio/ThemeLayout.json",
        sha256_file(target),
    )
    operation["backup_rel"] = ""
    _write_apply_record(loaded.root, apply_id, _completed_record(operation))

    plan = plan_managed_apply(loaded.manifest, loaded.root, apply_id="missing-backup-plan")

    layout = next(op for op in plan.operations if op.target_rel.endswith("ThemeLayout.json"))
    assert layout.kind == ApplyOperationKind.CONFLICT


def test_completed_apply_records_ignore_replace_when_backup_missing(
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

    apply_id = "backup-missing"
    operation = _history_replace_operation(
        loaded.root,
        apply_id,
        "Source/ThemeStudio/ThemeLayout.json",
        sha256_file(target),
    )
    (loaded.root / operation["backup_rel"]).unlink()
    _write_apply_record(loaded.root, apply_id, _completed_record(operation))

    plan = plan_managed_apply(loaded.manifest, loaded.root, apply_id="backup-missing-plan")

    layout = next(op for op in plan.operations if op.target_rel.endswith("ThemeLayout.json"))
    assert layout.kind == ApplyOperationKind.CONFLICT


def test_completed_apply_records_ignore_replace_when_backup_checksum_mismatches(
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

    apply_id = "backup-checksum-mismatch"
    operation = _history_replace_operation(
        loaded.root,
        apply_id,
        "Source/ThemeStudio/ThemeLayout.json",
        sha256_file(target),
    )
    (loaded.root / operation["backup_rel"]).write_text("different backup\n", encoding="utf-8")
    _write_apply_record(loaded.root, apply_id, _completed_record(operation))

    plan = plan_managed_apply(loaded.manifest, loaded.root, apply_id="backup-mismatch-plan")

    layout = next(op for op in plan.operations if op.target_rel.endswith("ThemeLayout.json"))
    assert layout.kind == ApplyOperationKind.CONFLICT


def test_completed_apply_records_ignore_mismatched_apply_id(fixture_project: Path) -> None:
    loaded = _project_with_theme(fixture_project)
    target = loaded.root / "Source" / "ThemeStudio" / "ThemeLayout.json"
    target.parent.mkdir(parents=True)
    target.write_text("managed layout\n", encoding="utf-8")

    from juce_theme_studio.core.managed_apply import completed_apply_records, sha256_file

    operation = _history_operation("Source/ThemeStudio/ThemeLayout.json", sha256_file(target))
    record = _completed_record(operation)
    record["apply_id"] = "../unsafe"
    _write_apply_record(loaded.root, "trusted-directory", record)

    assert completed_apply_records(loaded.root) == []


def test_completed_apply_records_ignore_symlinked_transaction_directory(
    fixture_project: Path,
) -> None:
    loaded = _project_with_theme(fixture_project)
    target = loaded.root / "Source" / "ThemeStudio" / "ThemeLayout.json"
    target.parent.mkdir(parents=True)
    target.write_text("hand edited\n", encoding="utf-8")

    from juce_theme_studio.core.managed_apply import (
        ApplyOperationKind,
        completed_apply_records,
        plan_managed_apply,
        sha256_file,
    )

    forged = fixture_project.parent / "forged-history"
    forged.mkdir()
    operation = _history_operation("Source/ThemeStudio/ThemeLayout.json", sha256_file(target))
    record = _completed_record(operation)
    record["apply_id"] = "fake-id"
    (forged / "apply.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    applies = loaded.root / ".juce_theme_studio" / "applies"
    (applies / "fake-id").symlink_to(forged, target_is_directory=True)

    assert completed_apply_records(loaded.root) == []

    plan = plan_managed_apply(loaded.manifest, loaded.root, apply_id="symlink-history-plan")

    layout = next(op for op in plan.operations if op.target_rel.endswith("ThemeLayout.json"))
    assert layout.kind == ApplyOperationKind.CONFLICT


def test_latest_completed_apply_remains_discoverable_when_target_becomes_symlink(
    fixture_project: Path,
) -> None:
    loaded = _project_with_theme(fixture_project)

    from juce_theme_studio.core.managed_apply import (
        execute_managed_apply,
        latest_completed_apply,
        plan_managed_apply,
    )

    plan = plan_managed_apply(loaded.manifest, loaded.root, apply_id="target-link-history")
    execute_managed_apply(plan)
    target = loaded.root / "Source" / "ThemeStudio" / "ThemeLayout.json"
    redirected = fixture_project.parent / "linked-theme-layout.json"
    redirected.write_text("outside target\n", encoding="utf-8")
    target.unlink()
    target.symlink_to(redirected)

    record = latest_completed_apply(loaded.root)

    assert record is not None
    assert record["apply_id"] == "target-link-history"


def test_execute_managed_apply_copies_generated_files_and_records_completion(
    fixture_project: Path,
) -> None:
    loaded = _project_with_theme(fixture_project)

    from juce_theme_studio.core.managed_apply import (
        ApplyStatus,
        execute_managed_apply,
        plan_managed_apply,
    )

    plan = plan_managed_apply(loaded.manifest, loaded.root, apply_id="apply-copy")
    result = execute_managed_apply(plan)

    layout = fixture_project / "Source" / "ThemeStudio" / "ThemeLayout.json"
    assets = fixture_project / "Source" / "ThemeStudio" / "assets"
    record = json.loads(plan.record_path.read_text(encoding="utf-8"))
    assert result.status == ApplyStatus.COMPLETED
    assert layout.is_file()
    assert assets.is_dir()
    assert record["status"] == "completed"
    assert any(
        op["target_rel"] == "Source/ThemeStudio/ThemeLayout.json" for op in record["operations"]
    )


def test_execute_managed_apply_preserves_created_at_in_completed_record(
    fixture_project: Path,
) -> None:
    loaded = _project_with_theme(fixture_project)

    from juce_theme_studio.core.managed_apply import execute_managed_apply, plan_managed_apply

    plan = plan_managed_apply(loaded.manifest, loaded.root, apply_id="completed-created-at")
    planned_record = json.loads(plan.record_path.read_text(encoding="utf-8"))

    execute_managed_apply(plan)

    completed_record = json.loads(plan.record_path.read_text(encoding="utf-8"))
    assert completed_record["created_at"] == planned_record["created_at"]


def test_execute_managed_apply_backs_up_replaced_file(fixture_project: Path) -> None:
    loaded = _project_with_theme(fixture_project)

    from juce_theme_studio.core.managed_apply import execute_managed_apply, plan_managed_apply

    first = plan_managed_apply(loaded.manifest, loaded.root, apply_id="first")
    execute_managed_apply(first)
    target = fixture_project / "Source" / "ThemeStudio" / "ThemeLayout.json"
    original = target.read_text(encoding="utf-8")

    loaded.manifest.theme_colors["primary"] = "ffff0000"
    second = plan_managed_apply(loaded.manifest, loaded.root, apply_id="second")
    execute_managed_apply(second)

    backups = list((second.transaction_dir / "backups").rglob("ThemeLayout.json"))
    assert backups
    assert backups[0].read_text(encoding="utf-8") == original


def test_execute_managed_apply_aborts_when_target_changed_after_preview(
    fixture_project: Path,
) -> None:
    loaded = _project_with_theme(fixture_project)

    from juce_theme_studio.core.managed_apply import execute_managed_apply, plan_managed_apply

    first = plan_managed_apply(loaded.manifest, loaded.root, apply_id="first-change")
    execute_managed_apply(first)
    loaded.manifest.theme_colors["primary"] = "ff00ff00"
    second = plan_managed_apply(loaded.manifest, loaded.root, apply_id="second-change")
    target = fixture_project / "Source" / "ThemeStudio" / "ThemeLayout.json"
    target.write_text("changed after preview\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="changed since preview"):
        execute_managed_apply(second)


def test_execute_managed_apply_refuses_conflicted_plan(fixture_project: Path) -> None:
    loaded = _project_with_theme(fixture_project)
    dest = fixture_project / "Source" / "ThemeStudio"
    dest.mkdir(parents=True)
    (dest / "ThemeLayout.json").write_text("hand edited\n", encoding="utf-8")

    from juce_theme_studio.core.managed_apply import execute_managed_apply, plan_managed_apply

    plan = plan_managed_apply(loaded.manifest, loaded.root, apply_id="conflict-exec")

    with pytest.raises(RuntimeError, match="conflicts"):
        execute_managed_apply(plan)
    record = json.loads(plan.record_path.read_text(encoding="utf-8"))
    assert record["status"] == "failed"


def test_execute_managed_apply_does_not_copy_missing_source_file(
    fixture_project: Path,
) -> None:
    loaded = _project_with_theme(fixture_project)

    from juce_theme_studio.core.managed_apply import execute_managed_apply, plan_managed_apply

    plan = plan_managed_apply(loaded.manifest, loaded.root, apply_id="missing-source")
    (plan.generated_dir / "ThemeLayout.json").unlink()

    with pytest.raises(RuntimeError, match="source"):
        execute_managed_apply(plan)
    assert not (fixture_project / "Source" / "ThemeStudio" / "ThemeLayout.json").exists()


def test_execute_managed_apply_aborts_when_source_changed_after_preview(
    fixture_project: Path,
) -> None:
    loaded = _project_with_theme(fixture_project)

    from juce_theme_studio.core.managed_apply import execute_managed_apply, plan_managed_apply

    plan = plan_managed_apply(loaded.manifest, loaded.root, apply_id="changed-source")
    (plan.generated_dir / "ThemeLayout.json").write_text("changed source\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="source file changed since preview"):
        execute_managed_apply(plan)
    assert not (fixture_project / "Source" / "ThemeStudio" / "ThemeLayout.json").exists()


def test_execute_managed_apply_rejects_symlinked_generated_source_file(
    fixture_project: Path,
) -> None:
    loaded = _project_with_theme(fixture_project)

    from juce_theme_studio.core.managed_apply import execute_managed_apply, plan_managed_apply

    plan = plan_managed_apply(loaded.manifest, loaded.root, apply_id="source-file-link")
    layout = next(op for op in plan.operations if op.target_rel.endswith("ThemeLayout.json"))
    source = plan.generated_dir / layout.source_rel
    redirected_source = fixture_project.parent / "redirected-layout-source.json"
    redirected_source.write_bytes(source.read_bytes())
    source.unlink()
    source.symlink_to(redirected_source)

    with pytest.raises(RuntimeError, match="symlink"):
        execute_managed_apply(plan)

    record = json.loads(plan.record_path.read_text(encoding="utf-8"))
    assert record["status"] == "failed"
    assert "symlink" in record["message"]
    assert not (fixture_project / layout.target_rel).exists()


def test_execute_managed_apply_rejects_symlinked_generated_source_parent(
    fixture_project: Path,
) -> None:
    loaded = _project_with_theme(fixture_project)

    from juce_theme_studio.core.managed_apply import execute_managed_apply, plan_managed_apply

    plan = plan_managed_apply(loaded.manifest, loaded.root, apply_id="source-parent-link")
    asset = next(op for op in plan.operations if op.source_rel.startswith("assets/"))
    source = plan.generated_dir / asset.source_rel
    redirected_assets = fixture_project.parent / "redirected-assets-source"
    redirected_asset = redirected_assets / Path(asset.source_rel).relative_to("assets")
    redirected_asset.parent.mkdir(parents=True)
    redirected_asset.write_bytes(source.read_bytes())
    assets_dir = plan.generated_dir / "assets"
    shutil.rmtree(assets_dir)
    assets_dir.symlink_to(redirected_assets, target_is_directory=True)

    with pytest.raises(RuntimeError, match="symlink"):
        execute_managed_apply(plan)

    record = json.loads(plan.record_path.read_text(encoding="utf-8"))
    assert record["status"] == "failed"
    assert "symlink" in record["message"]
    assert not (fixture_project / asset.target_rel).exists()


def test_execute_managed_apply_aborts_when_unchanged_source_deleted_after_preview(
    fixture_project: Path,
) -> None:
    loaded = _project_with_theme(fixture_project)

    from juce_theme_studio.core.managed_apply import execute_managed_apply, plan_managed_apply

    seed = plan_managed_apply(loaded.manifest, loaded.root, apply_id="unchanged-source-seed")
    destination = fixture_project / "Source" / "ThemeStudio"
    destination.mkdir(parents=True)
    generated_layout = seed.generated_dir / "ThemeLayout.json"
    (destination / "ThemeLayout.json").write_bytes(generated_layout.read_bytes())

    plan = plan_managed_apply(loaded.manifest, loaded.root, apply_id="unchanged-source-drift")
    (plan.generated_dir / "ThemeLayout.json").unlink()

    with pytest.raises(RuntimeError, match="source"):
        execute_managed_apply(plan)
    record = json.loads(plan.record_path.read_text(encoding="utf-8"))
    assert record["status"] == "failed"


def test_execute_managed_apply_aborts_when_unchanged_source_changed_after_preview(
    fixture_project: Path,
) -> None:
    loaded = _project_with_theme(fixture_project)

    from juce_theme_studio.core.managed_apply import execute_managed_apply, plan_managed_apply

    first = plan_managed_apply(loaded.manifest, loaded.root, apply_id="unchanged-change-first")
    execute_managed_apply(first)
    second = plan_managed_apply(loaded.manifest, loaded.root, apply_id="unchanged-change-second")
    layout = next(op for op in second.operations if op.target_rel.endswith("ThemeLayout.json"))
    (second.generated_dir / layout.source_rel).write_text(
        "changed unchanged source\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="source file changed since preview"):
        execute_managed_apply(second)
    record = json.loads(second.record_path.read_text(encoding="utf-8"))
    assert record["status"] == "failed"


def test_execute_managed_apply_failed_record_preserves_partial_recovery_metadata(
    fixture_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded = _project_with_theme(fixture_project)

    from juce_theme_studio.core import managed_apply as managed_apply_module
    from juce_theme_studio.core.managed_apply import (
        ApplyOperationKind,
        execute_managed_apply,
        plan_managed_apply,
        sha256_file,
    )

    first = plan_managed_apply(loaded.manifest, loaded.root, apply_id="partial-first")
    execute_managed_apply(first)
    second = plan_managed_apply(loaded.manifest, loaded.root, apply_id="partial-second")
    replace_ops = second.operations[:2]
    for op in replace_ops:
        op.kind = ApplyOperationKind.REPLACE
        op.source_checksum = sha256_file(second.generated_dir / op.source_rel)
        op.target_checksum = sha256_file(fixture_project / op.target_rel)

    real_copy2 = managed_apply_module.shutil.copy2
    target_writes: list[Path] = []

    def fail_second_target_copy(src: Path, dst: Path) -> Path:
        target = Path(dst)
        if target.is_relative_to(fixture_project / "Source" / "ThemeStudio"):
            target_writes.append(target)
            if len(target_writes) == 2:
                raise OSError("simulated copy failure")
        return real_copy2(src, dst)

    monkeypatch.setattr(managed_apply_module.shutil, "copy2", fail_second_target_copy)

    with pytest.raises(OSError, match="simulated copy failure"):
        execute_managed_apply(second)

    record = json.loads(second.record_path.read_text(encoding="utf-8"))
    backup_rels = [op["backup_rel"] for op in record["operations"] if op["backup_rel"]]
    assert record["status"] == "failed"
    assert record["files_written"] == [replace_ops[0].target_rel]
    assert record["files_touched"] == [op.target_rel for op in replace_ops]
    assert len(record["backups"]) >= 2
    assert any(rel.endswith(replace_ops[0].target_rel) for rel in backup_rels)
    assert any(rel.endswith(replace_ops[1].target_rel) for rel in backup_rels)


def test_execute_managed_apply_failed_record_when_completion_record_write_fails(
    fixture_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded = _project_with_theme(fixture_project)

    from juce_theme_studio.core import managed_apply as managed_apply_module
    from juce_theme_studio.core.managed_apply import (
        ApplyOperationKind,
        ApplyStatus,
        execute_managed_apply,
        plan_managed_apply,
    )

    first = plan_managed_apply(loaded.manifest, loaded.root, apply_id="complete-fail-first")
    execute_managed_apply(first)
    loaded.manifest.theme_colors["primary"] = "ff778899"
    second = plan_managed_apply(loaded.manifest, loaded.root, apply_id="complete-fail-second")
    expected_written = [
        op.target_rel for op in second.operations if op.kind != ApplyOperationKind.UNCHANGED
    ]
    assert expected_written

    def fail_completed_record(plan: managed_apply_module.ApplyPlan) -> None:
        raise RuntimeError(f"simulated completed record failure for {plan.apply_id}")

    monkeypatch.setattr(managed_apply_module, "_write_completed_record", fail_completed_record)

    with pytest.raises(RuntimeError, match="simulated completed record failure"):
        execute_managed_apply(second)

    record = json.loads(second.record_path.read_text(encoding="utf-8"))
    backup_rels = [op["backup_rel"] for op in record["operations"] if op["backup_rel"]]
    assert second.status == ApplyStatus.FAILED
    assert record["status"] == "failed"
    assert "simulated completed record failure" in record["message"]
    assert record["files_written"] == expected_written
    assert record["files_touched"] == expected_written
    assert record["backups"]
    assert all(
        any(rel.endswith(target_rel) for rel in backup_rels) for target_rel in expected_written
    )


def test_execute_managed_apply_fails_when_copied_target_checksum_mismatches(
    fixture_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded = _project_with_theme(fixture_project)

    from juce_theme_studio.core import managed_apply as managed_apply_module
    from juce_theme_studio.core.managed_apply import execute_managed_apply, plan_managed_apply

    plan = plan_managed_apply(loaded.manifest, loaded.root, apply_id="bad-copy")
    target_rel = next(op.target_rel for op in plan.operations if op.target_rel.endswith(".json"))
    real_copy2 = managed_apply_module.shutil.copy2

    def corrupt_managed_copy(src: Path, dst: Path) -> Path:
        destination = Path(dst)
        if Path(src) == plan.generated_dir / "ThemeLayout.json":
            destination.write_text("wrong target content\n", encoding="utf-8")
            return destination
        return real_copy2(src, dst)

    monkeypatch.setattr(managed_apply_module.shutil, "copy2", corrupt_managed_copy)

    with pytest.raises(RuntimeError, match="checksum"):
        execute_managed_apply(plan)

    record = json.loads(plan.record_path.read_text(encoding="utf-8"))
    assert record["status"] == "failed"
    assert target_rel not in record["files_written"]
    assert target_rel in record["files_touched"]


def test_execute_managed_apply_records_unverified_write_after_replace_checksum_failure(
    fixture_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded = _project_with_theme(fixture_project)

    from juce_theme_studio.core import managed_apply as managed_apply_module
    from juce_theme_studio.core.managed_apply import execute_managed_apply, plan_managed_apply

    plan = plan_managed_apply(loaded.manifest, loaded.root, apply_id="unverified-write")
    target_rel = next(op.target_rel for op in plan.operations if op.target_rel.endswith(".json"))
    target = fixture_project / target_rel
    real_sha256 = managed_apply_module.sha256_file
    corrupted = False

    def corrupt_replaced_target(path: Path) -> str:
        nonlocal corrupted
        candidate = Path(path)
        if candidate == target and target.exists() and not corrupted:
            target.write_text("corrupt after replace\n", encoding="utf-8")
            corrupted = True
        return real_sha256(candidate)

    monkeypatch.setattr(managed_apply_module, "sha256_file", corrupt_replaced_target)

    with pytest.raises(RuntimeError, match="checksum"):
        execute_managed_apply(plan)

    record = json.loads(plan.record_path.read_text(encoding="utf-8"))
    assert target.read_text(encoding="utf-8") == "corrupt after replace\n"
    assert record["status"] == "failed"
    assert target_rel not in record["files_written"]
    assert target_rel in record["files_touched"]
    assert record["unverified_writes"] == [
        {
            "target_rel": target_rel,
            "observed_checksum": real_sha256(target),
        }
    ]


def test_execute_managed_apply_fails_before_overwrite_when_backup_checksum_mismatches(
    fixture_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded = _project_with_theme(fixture_project)

    from juce_theme_studio.core import managed_apply as managed_apply_module
    from juce_theme_studio.core.managed_apply import execute_managed_apply, plan_managed_apply

    first = plan_managed_apply(loaded.manifest, loaded.root, apply_id="backup-first")
    execute_managed_apply(first)
    target = fixture_project / "Source" / "ThemeStudio" / "ThemeLayout.json"
    original = target.read_text(encoding="utf-8")

    loaded.manifest.theme_colors["primary"] = "ff334455"
    second = plan_managed_apply(loaded.manifest, loaded.root, apply_id="backup-corrupt")
    real_copy2 = managed_apply_module.shutil.copy2

    def corrupt_backup_copy(src: Path, dst: Path) -> Path:
        destination = Path(dst)
        if destination.is_relative_to(second.transaction_dir / "backups"):
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text("corrupt backup\n", encoding="utf-8")
            return destination
        return real_copy2(src, dst)

    monkeypatch.setattr(managed_apply_module.shutil, "copy2", corrupt_backup_copy)

    with pytest.raises(RuntimeError, match="backup checksum mismatch"):
        execute_managed_apply(second)

    record = json.loads(second.record_path.read_text(encoding="utf-8"))
    assert target.read_text(encoding="utf-8") == original
    assert record["status"] == "failed"
    assert "backup checksum mismatch" in record["message"]
    assert "Source/ThemeStudio/ThemeLayout.json" not in record["files_touched"]


def test_execute_managed_apply_rejects_symlinked_backup_directory(
    fixture_project: Path,
) -> None:
    loaded = _project_with_theme(fixture_project)

    from juce_theme_studio.core.managed_apply import execute_managed_apply, plan_managed_apply

    first = plan_managed_apply(loaded.manifest, loaded.root, apply_id="backup-link-first")
    execute_managed_apply(first)
    loaded.manifest.theme_colors["primary"] = "ff556677"
    second = plan_managed_apply(loaded.manifest, loaded.root, apply_id="backup-link-second")
    redirected = fixture_project.parent / "redirected-backups"
    redirected.mkdir()
    (second.transaction_dir / "backups").symlink_to(redirected, target_is_directory=True)

    with pytest.raises(RuntimeError, match="symlink"):
        execute_managed_apply(second)

    record = json.loads(second.record_path.read_text(encoding="utf-8"))
    assert not any(redirected.rglob("*"))
    assert record["status"] == "failed"


def test_execute_managed_apply_rejects_symlinked_record_path(
    fixture_project: Path,
) -> None:
    loaded = _project_with_theme(fixture_project)

    from juce_theme_studio.core.managed_apply import execute_managed_apply, plan_managed_apply

    plan = plan_managed_apply(loaded.manifest, loaded.root, apply_id="record-link")
    redirected_record = fixture_project.parent / "redirected-apply.json"
    redirected_record.write_text("outside record\n", encoding="utf-8")
    plan.record_path.unlink()
    plan.record_path.symlink_to(redirected_record)

    with pytest.raises(RuntimeError, match="symlink"):
        execute_managed_apply(plan)

    assert redirected_record.read_text(encoding="utf-8") == "outside record\n"
    assert not (fixture_project / "Source" / "ThemeStudio" / "ThemeLayout.json").exists()


def test_execute_managed_apply_rejects_record_symlink_before_completed_record_write(
    fixture_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded = _project_with_theme(fixture_project)

    from juce_theme_studio.core import managed_apply as managed_apply_module
    from juce_theme_studio.core.managed_apply import execute_managed_apply, plan_managed_apply

    plan = plan_managed_apply(loaded.manifest, loaded.root, apply_id="complete-record-link")
    redirected_record = fixture_project.parent / "complete-redirected-apply.json"
    redirected_record.write_text("outside completed record\n", encoding="utf-8")
    real_copy_target = managed_apply_module._safe_copy_target_file
    swapped = False

    def swap_record_before_completed_write(
        plan_arg: managed_apply_module.ApplyPlan,
        op: managed_apply_module.ApplyOperation,
        source: Path,
        target: Path,
        **kwargs: object,
    ) -> str:
        nonlocal swapped
        result = real_copy_target(plan_arg, op, source, target, **kwargs)
        if not swapped:
            plan.record_path.unlink()
            plan.record_path.symlink_to(redirected_record)
            swapped = True
        return result

    monkeypatch.setattr(
        managed_apply_module,
        "_safe_copy_target_file",
        swap_record_before_completed_write,
    )

    with pytest.raises(RuntimeError, match="symlink"):
        execute_managed_apply(plan)

    assert redirected_record.read_text(encoding="utf-8") == "outside completed record\n"
    assert plan.record_path.is_symlink()


def test_execute_managed_apply_rejects_record_symlink_before_failed_record_write(
    fixture_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded = _project_with_theme(fixture_project)

    from juce_theme_studio.core import managed_apply as managed_apply_module
    from juce_theme_studio.core.managed_apply import execute_managed_apply, plan_managed_apply

    plan = plan_managed_apply(loaded.manifest, loaded.root, apply_id="failed-record-link")
    redirected_record = fixture_project.parent / "failed-redirected-apply.json"
    redirected_record.write_text("outside failed record\n", encoding="utf-8")
    real_copy2 = managed_apply_module.shutil.copy2

    def corrupt_after_record_swap(src: Path, dst: Path) -> Path:
        destination = Path(dst)
        if Path(src) == plan.generated_dir / "ThemeLayout.json":
            plan.record_path.unlink()
            plan.record_path.symlink_to(redirected_record)
            destination.write_text("wrong target content\n", encoding="utf-8")
            return destination
        return real_copy2(src, dst)

    monkeypatch.setattr(managed_apply_module.shutil, "copy2", corrupt_after_record_swap)

    with pytest.raises(RuntimeError):
        execute_managed_apply(plan)

    assert redirected_record.read_text(encoding="utf-8") == "outside failed record\n"
    assert plan.record_path.is_symlink()


def test_execute_managed_apply_rejects_target_swapped_to_symlink_before_write(
    fixture_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded = _project_with_theme(fixture_project)

    from juce_theme_studio.core import managed_apply as managed_apply_module
    from juce_theme_studio.core.managed_apply import execute_managed_apply, plan_managed_apply

    first = plan_managed_apply(loaded.manifest, loaded.root, apply_id="swap-link-first")
    execute_managed_apply(first)
    loaded.manifest.theme_colors["primary"] = "ff667788"
    second = plan_managed_apply(loaded.manifest, loaded.root, apply_id="swap-link-second")
    layout = next(op for op in second.operations if op.target_rel.endswith("ThemeLayout.json"))
    target = fixture_project / layout.target_rel
    redirected = target.parent / "redirected-layout.json"
    redirected_original = "redirected original\n"
    redirected.write_text(redirected_original, encoding="utf-8")
    source = second.generated_dir / layout.source_rel
    real_copy2 = managed_apply_module.shutil.copy2
    swapped = False

    def swap_target_before_copy(src: Path, dst: Path) -> Path:
        nonlocal swapped
        if Path(src) == source and not swapped:
            target.unlink()
            target.symlink_to(redirected)
            swapped = True
        return real_copy2(src, dst)

    monkeypatch.setattr(managed_apply_module.shutil, "copy2", swap_target_before_copy)

    with pytest.raises(RuntimeError, match="symlink"):
        execute_managed_apply(second)

    record = json.loads(second.record_path.read_text(encoding="utf-8"))
    assert redirected.read_text(encoding="utf-8") == redirected_original
    assert target.is_symlink()
    assert record["status"] == "failed"


def test_execute_managed_apply_rejects_symlinked_target_file(
    fixture_project: Path,
) -> None:
    loaded = _project_with_theme(fixture_project)

    from juce_theme_studio.core.managed_apply import execute_managed_apply, plan_managed_apply

    first = plan_managed_apply(loaded.manifest, loaded.root, apply_id="symlink-file-first")
    execute_managed_apply(first)
    target = fixture_project / "Source" / "ThemeStudio" / "ThemeLayout.json"
    original = target.read_text(encoding="utf-8")

    loaded.manifest.theme_colors["primary"] = "ff445566"
    second = plan_managed_apply(loaded.manifest, loaded.root, apply_id="symlink-file-second")
    linked_target = fixture_project / "Source" / "ThemeStudio" / "linked-target.json"
    linked_target.write_text(original, encoding="utf-8")
    target.unlink()
    target.symlink_to(linked_target)

    with pytest.raises(RuntimeError, match="symlink"):
        execute_managed_apply(second)

    record = json.loads(second.record_path.read_text(encoding="utf-8"))
    assert linked_target.read_text(encoding="utf-8") == original
    assert target.is_symlink()
    assert record["status"] == "failed"


def test_execute_managed_apply_rejects_symlinked_destination_directory(
    fixture_project: Path,
) -> None:
    loaded = _project_with_theme(fixture_project)

    from juce_theme_studio.core.managed_apply import execute_managed_apply, plan_managed_apply

    plan = plan_managed_apply(loaded.manifest, loaded.root, apply_id="symlink-parent")
    source_dir = fixture_project / "Source"
    source_dir.mkdir(parents=True, exist_ok=True)
    destination = source_dir / "ThemeStudio"
    redirected = fixture_project / "RedirectedThemeStudio"
    redirected.mkdir()
    destination.symlink_to(redirected, target_is_directory=True)

    with pytest.raises(RuntimeError, match="symlink"):
        execute_managed_apply(plan)

    record = json.loads(plan.record_path.read_text(encoding="utf-8"))
    assert not (redirected / "ThemeLayout.json").exists()
    assert destination.is_symlink()
    assert record["status"] == "failed"


def test_plan_managed_apply_rejects_symlinked_destination_before_planning(
    fixture_project: Path,
) -> None:
    loaded = _project_with_theme(fixture_project)
    source_dir = fixture_project / "Source"
    source_dir.mkdir(parents=True, exist_ok=True)
    destination = source_dir / "ThemeStudio"
    redirected = fixture_project / "RedirectedThemeStudio"
    redirected.mkdir()
    destination.symlink_to(redirected, target_is_directory=True)

    from juce_theme_studio.core.managed_apply import plan_managed_apply

    with pytest.raises(ValueError, match="symlink"):
        plan_managed_apply(loaded.manifest, loaded.root, apply_id="symlink-before-plan")

    assert not (redirected / "ThemeLayout.json").exists()


def test_plan_managed_apply_marks_symlinked_target_conflict_without_hashing_it(
    fixture_project: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loaded = _project_with_theme(fixture_project)
    target = fixture_project / "Source" / "ThemeStudio" / "ThemeLayout.json"
    target.parent.mkdir(parents=True)
    redirected = fixture_project.parent / "redirected-layout.json"
    redirected.write_text("outside project target\n", encoding="utf-8")
    target.symlink_to(redirected)

    from juce_theme_studio.core import managed_apply as managed_apply_module
    from juce_theme_studio.core.managed_apply import ApplyOperationKind, plan_managed_apply

    real_sha256 = managed_apply_module.sha256_file

    def reject_symlink_checksum(path: Path) -> str:
        candidate = Path(path)
        if candidate == target:
            raise AssertionError("planner must not checksum symlinked target")
        return real_sha256(candidate)

    monkeypatch.setattr(managed_apply_module, "sha256_file", reject_symlink_checksum)

    plan = plan_managed_apply(loaded.manifest, loaded.root, apply_id="target-link-plan")

    layout = next(op for op in plan.operations if op.target_rel.endswith("ThemeLayout.json"))
    assert layout.kind == ApplyOperationKind.CONFLICT
    assert layout.target_checksum == ""
    assert "symlink" in layout.message
