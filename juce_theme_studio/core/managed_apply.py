"""Fully managed project apply and revert support."""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from juce_theme_studio.core.manifest import ThemeManifest
from juce_theme_studio.core.types import STUDIO_DIR
from juce_theme_studio.core.validation import ValidationReport
from juce_theme_studio.juce.exporter import export_theme_to_directory

DEFAULT_DESTINATION_SUBDIR = "Source/ThemeStudio"
APPLY_HISTORY_DIR = "applies"
MANAGED_OUTPUT_FILES = {
    "ThemeLayout.json",
    "ThemeAssets.h",
    "ThemeAssets.cpp",
    "ThemeLookAndFeel.h",
    "ThemeLookAndFeel.cpp",
    "GeneratedThemeComponents.h",
    "GeneratedThemeComponents.cpp",
}
_HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
_MANAGED_HISTORY_KINDS = {
    "create",
    "replace",
    "unchanged",
}


class ApplyOperationKind(str, Enum):
    CREATE = "create"
    REPLACE = "replace"
    UNCHANGED = "unchanged"
    CONFLICT = "conflict"


class ApplyStatus(str, Enum):
    PLANNED = "planned"
    COMPLETED = "completed"
    FAILED = "failed"
    REVERTED = "reverted"


@dataclass
class ApplyOperation:
    kind: ApplyOperationKind
    source_rel: str
    target_rel: str
    source_checksum: str
    target_checksum: str = ""
    backup_rel: str = ""
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "source_rel": self.source_rel,
            "target_rel": self.target_rel,
            "source_checksum": self.source_checksum,
            "target_checksum": self.target_checksum,
            "backup_rel": self.backup_rel,
            "message": self.message,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ApplyOperation:
        return cls(
            kind=ApplyOperationKind(str(data["kind"])),
            source_rel=str(data["source_rel"]),
            target_rel=str(data["target_rel"]),
            source_checksum=str(data["source_checksum"]),
            target_checksum=str(data.get("target_checksum", "")),
            backup_rel=str(data.get("backup_rel", "")),
            message=str(data.get("message", "")),
        )


@dataclass
class ApplyPlan:
    apply_id: str
    project_root: Path
    transaction_dir: Path
    generated_dir: Path
    destination_subdir: str
    operations: list[ApplyOperation] = field(default_factory=list)
    validation: ValidationReport | None = None
    status: ApplyStatus = ApplyStatus.PLANNED

    @property
    def has_conflicts(self) -> bool:
        return any(op.kind == ApplyOperationKind.CONFLICT for op in self.operations)

    @property
    def record_path(self) -> Path:
        return self.transaction_dir / "apply.json"


@dataclass
class ApplyResult:
    status: ApplyStatus
    record_path: Path
    files_written: list[str] = field(default_factory=list)
    backups: list[str] = field(default_factory=list)


def make_apply_id(now: datetime | None = None) -> str:
    stamp = now or datetime.now(timezone.utc)
    return stamp.strftime("%Y%m%d_%H%M%S_%f")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _studio_dir(project_root: Path) -> Path:
    return project_root / STUDIO_DIR


def _applies_dir(project_root: Path) -> Path:
    return _studio_dir(project_root) / APPLY_HISTORY_DIR


def _safe_project_subdir(project_root: Path, subdir: str, *, label: str) -> Path:
    normalized = subdir.replace("\\", "/")
    rel = Path(normalized)
    if not subdir.strip() or rel.is_absolute() or ".." in rel.parts:
        raise ValueError(f"Invalid {label}: {subdir!r}")
    root = project_root.resolve()
    dest = (root / rel).resolve()
    try:
        dest.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"Invalid {label}: {subdir!r}") from exc
    return dest


def _safe_apply_id(apply_id: str) -> str:
    rel = Path(apply_id)
    if (
        not apply_id.strip()
        or rel.is_absolute()
        or apply_id in {".", ".."}
        or "/" in apply_id
        or "\\" in apply_id
        or len(rel.parts) != 1
    ):
        raise ValueError(f"Invalid apply_id: {apply_id!r}")
    return apply_id


def _rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def _safe_relative_record_path(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.replace("\\", "/")
    rel = Path(normalized)
    if not value.strip() or rel.is_absolute() or not rel.parts or ".." in rel.parts:
        return None
    return str(rel).replace("\\", "/")


def _safe_record_target_rel(project_root: Path, value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        return _rel(_safe_project_subdir(project_root, value, label="target"), project_root)
    except ValueError:
        return None


def _safe_record_backup_rel(
    project_root: Path,
    value: Any,
    *,
    backup_root: Path | None = None,
) -> str:
    if not value:
        return ""
    if not isinstance(value, str):
        return ""
    try:
        backup = _safe_project_subdir(project_root, value, label="backup")
    except ValueError:
        return ""
    if backup_root is not None:
        try:
            backup.relative_to(backup_root.resolve())
        except ValueError:
            return ""
    return _rel(backup, project_root)


def _is_sha256_checksum(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(ch in _HEX_DIGITS for ch in value)


def _record_timestamp(record: dict[str, Any]) -> datetime | None:
    for key in ("completed_at", "created_at"):
        value = record.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        try:
            stamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            continue
        if stamp.tzinfo is None:
            return stamp.replace(tzinfo=timezone.utc)
        return stamp.astimezone(timezone.utc)
    return None


def _validated_history_operation(
    project_root: Path,
    item: Any,
    *,
    backup_root: Path | None = None,
) -> dict[str, Any] | None:
    if not isinstance(item, dict):
        return None

    kind = str(item.get("kind", ""))
    if kind not in _MANAGED_HISTORY_KINDS:
        return None

    source_rel = _safe_relative_record_path(item.get("source_rel"))
    target_rel = _safe_record_target_rel(project_root, item.get("target_rel"))
    source_checksum = item.get("source_checksum")
    if source_rel is None or target_rel is None or not _is_sha256_checksum(source_checksum):
        return None

    operation = dict(item)
    operation["kind"] = kind
    operation["source_rel"] = source_rel
    operation["target_rel"] = target_rel
    operation["source_checksum"] = source_checksum.lower()
    operation["backup_rel"] = _safe_record_backup_rel(
        project_root,
        item.get("backup_rel"),
        backup_root=backup_root,
    )
    return operation


def _validated_completed_record(
    project_root: Path,
    record: dict[str, Any] | None,
    *,
    record_path: Path | None = None,
) -> dict[str, Any] | None:
    if not isinstance(record, dict) or record.get("status") != ApplyStatus.COMPLETED.value:
        return None
    trusted_apply_id = None
    if record_path is not None:
        try:
            trusted_apply_id = _safe_apply_id(record_path.parent.name)
        except ValueError:
            return None
        record_apply_id = record.get("apply_id")
        if record_apply_id is not None and record_apply_id != trusted_apply_id:
            return None

    operations = record.get("operations")
    if not isinstance(operations, list):
        return None

    backup_root = record_path.parent / "backups" if record_path is not None else None
    valid_operations = [
        operation
        for item in operations
        if (
            operation := _validated_history_operation(
                project_root,
                item,
                backup_root=backup_root,
            )
        )
        is not None
    ]
    if not valid_operations:
        return None

    sanitized = dict(record)
    if trusted_apply_id is not None:
        sanitized["apply_id"] = trusted_apply_id
        sanitized["record_path"] = str(record_path)
        sanitized["transaction_dir"] = str(record_path.parent)
    sanitized["status"] = ApplyStatus.COMPLETED.value
    sanitized["operations"] = valid_operations
    return sanitized


def _read_apply_record(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        with path.open(encoding="utf-8") as handle:
            record = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    return record if isinstance(record, dict) else None


def completed_apply_records(project_root: Path) -> list[dict[str, Any]]:
    project_root = project_root.resolve()
    applies = _applies_dir(project_root)
    records: list[tuple[bool, datetime, str, dict[str, Any]]] = []
    for path in sorted(applies.glob("*/apply.json")):
        record = _validated_completed_record(
            project_root,
            _read_apply_record(path),
            record_path=path,
        )
        if record is None:
            continue
        timestamp = _record_timestamp(record)
        records.append(
            (
                timestamp is not None,
                timestamp or datetime.min.replace(tzinfo=timezone.utc),
                str(path),
                record,
            )
        )
    records.sort(key=lambda item: (item[0], item[1], item[2]))
    return [record for _, _, _, record in records]


def latest_completed_apply(project_root: Path) -> dict[str, Any] | None:
    records = completed_apply_records(project_root)
    return records[-1] if records else None


def _latest_managed_checksums(project_root: Path) -> dict[str, str]:
    latest = latest_completed_apply(project_root)
    if not latest:
        return {}
    checksums: dict[str, str] = {}
    for item in latest.get("operations", []):
        operation = _validated_history_operation(project_root, item)
        if operation:
            checksums[operation["target_rel"]] = operation["source_checksum"]
    return checksums


def _generated_payload_files(generated_dir: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(generated_dir.rglob("*")):
        if path.is_file():
            rel_parts = path.relative_to(generated_dir).parts
            if (
                rel_parts[0] == "assets"
                or path.name in MANAGED_OUTPUT_FILES
                or path.name == "README-INTEGRATION.md"
            ):
                files.append(path)
    return files


def _validation_to_dict(validation: ValidationReport | None) -> dict[str, Any]:
    if validation is None:
        return {"issues": []}
    return {
        "issues": [
            {
                "level": issue.level,
                "message": issue.message,
                "screen_id": issue.screen_id,
                "control_id": issue.control_id,
            }
            for issue in validation.issues
        ]
    }


def _write_plan_record(plan: ApplyPlan) -> None:
    plan.transaction_dir.mkdir(parents=True, exist_ok=True)
    data = {
        "apply_id": plan.apply_id,
        "status": plan.status.value,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(plan.project_root),
        "destination_subdir": plan.destination_subdir,
        "generated_dir": _rel(plan.generated_dir, plan.project_root),
        "validation": _validation_to_dict(plan.validation),
        "operations": [op.to_dict() for op in plan.operations],
    }
    plan.record_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def plan_managed_apply(
    manifest: ThemeManifest,
    project_root: Path,
    *,
    destination_subdir: str = DEFAULT_DESTINATION_SUBDIR,
    apply_id: str | None = None,
) -> ApplyPlan:
    project_root = project_root.resolve()
    destination = _safe_project_subdir(project_root, destination_subdir, label="destination")
    tx_id = _safe_apply_id(apply_id if apply_id is not None else make_apply_id())
    transaction_dir = _applies_dir(project_root) / tx_id
    if transaction_dir.exists():
        raise FileExistsError(f"Apply transaction already exists for apply_id {tx_id!r}")
    generated_dir = transaction_dir / "generated"
    destination_rel = _rel(destination, project_root)

    export_result = export_theme_to_directory(manifest, project_root, generated_dir, force=True)
    validation = export_result.validation

    managed_checksums = _latest_managed_checksums(project_root)
    operations: list[ApplyOperation] = []
    for source in _generated_payload_files(generated_dir):
        source_rel = _rel(source, generated_dir)
        if source.name == "README-INTEGRATION.md":
            continue
        target = destination / source_rel
        target_rel = _rel(target, project_root)
        source_checksum = sha256_file(source)
        target_checksum = sha256_file(target) if target.is_file() else ""

        if not target.exists():
            kind = ApplyOperationKind.CREATE
            message = "Create managed file"
        elif target_checksum == source_checksum:
            kind = ApplyOperationKind.UNCHANGED
            message = "Already matches generated output"
        elif managed_checksums.get(target_rel) == target_checksum:
            kind = ApplyOperationKind.REPLACE
            message = "Replace previously managed file"
        else:
            kind = ApplyOperationKind.CONFLICT
            message = "Destination exists with unexpected content"

        operations.append(
            ApplyOperation(
                kind=kind,
                source_rel=source_rel,
                target_rel=target_rel,
                source_checksum=source_checksum,
                target_checksum=target_checksum,
                message=message,
            )
        )

    plan = ApplyPlan(
        apply_id=tx_id,
        project_root=project_root,
        transaction_dir=transaction_dir,
        generated_dir=generated_dir,
        destination_subdir=destination_rel,
        operations=operations,
        validation=validation,
    )
    _write_plan_record(plan)
    return plan


def execute_managed_apply(plan: ApplyPlan) -> ApplyResult:
    if plan.has_conflicts:
        _write_failed_record(plan, "Plan contains conflicts")
        raise RuntimeError("Cannot apply while conflicts are present")

    files_written: list[str] = []
    files_touched: list[str] = []
    backups: list[str] = []
    completed_ops: list[ApplyOperation] = []

    try:
        _verify_plan_preconditions(plan)
        backup_root = plan.transaction_dir / "backups"
        backup_root.mkdir(parents=True, exist_ok=True)

        for op in plan.operations:
            if op.kind == ApplyOperationKind.UNCHANGED:
                completed_ops.append(op)
                continue

            source = _operation_source_path(plan, op)
            target = _operation_target_path(plan, op)
            target_rel = _rel(target, plan.project_root)
            target.parent.mkdir(parents=True, exist_ok=True)

            if target.is_file():
                backup = backup_root / target_rel
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
                backup_rel = _rel(backup, plan.project_root)
                if sha256_file(backup) != op.target_checksum:
                    raise RuntimeError(f"{op.target_rel} backup checksum mismatch")
                op.backup_rel = backup_rel
                backups.append(backup_rel)

            files_touched.append(target_rel)
            shutil.copy2(source, target)
            if sha256_file(target) != op.source_checksum:
                raise RuntimeError(f"{op.target_rel} copied checksum mismatch")
            files_written.append(target_rel)
            completed_ops.append(op)
    except Exception as exc:
        _write_failed_record(
            plan,
            str(exc),
            files_written=files_written,
            files_touched=files_touched,
            backups=backups,
        )
        raise

    plan.status = ApplyStatus.COMPLETED
    plan.operations = completed_ops
    _write_completed_record(plan)
    return ApplyResult(
        status=ApplyStatus.COMPLETED,
        record_path=plan.record_path,
        files_written=files_written,
        backups=backups,
    )


def _operation_source_path(plan: ApplyPlan, op: ApplyOperation) -> Path:
    source_rel = _safe_relative_record_path(op.source_rel)
    if source_rel is None:
        raise RuntimeError(f"Invalid source path for {op.target_rel}: {op.source_rel}")
    return plan.generated_dir / source_rel


def _operation_target_path(plan: ApplyPlan, op: ApplyOperation) -> Path:
    return _safe_project_subdir(plan.project_root, op.target_rel, label="target")


def _reject_symlinked_target_components(plan: ApplyPlan, op: ApplyOperation) -> None:
    target_rel = _safe_relative_record_path(op.target_rel)
    if target_rel is None:
        raise RuntimeError(f"Invalid target path for {op.target_rel}: {op.target_rel}")

    current = plan.project_root.resolve()
    for part in Path(target_rel).parts:
        current = current / part
        if current.is_symlink():
            symlink_rel = _rel(current, plan.project_root)
            raise RuntimeError(f"{op.target_rel} changed since preview: symlink at {symlink_rel}")
        if not current.exists():
            break


def _verify_plan_preconditions(plan: ApplyPlan) -> None:
    for op in plan.operations:
        source = _operation_source_path(plan, op)
        if op.kind != ApplyOperationKind.UNCHANGED and not source.is_file():
            raise RuntimeError(f"Missing source file for {op.target_rel}: {source}")
        if op.kind != ApplyOperationKind.UNCHANGED and sha256_file(source) != op.source_checksum:
            raise RuntimeError(f"{op.target_rel} source file changed since preview")

        _reject_symlinked_target_components(plan, op)
        target = _operation_target_path(plan, op)
        if not target.exists():
            if op.target_checksum:
                raise RuntimeError(f"{op.target_rel} changed since preview")
            continue
        if not target.is_file():
            raise RuntimeError(f"{op.target_rel} changed since preview")

        current = sha256_file(target)
        if current != op.target_checksum:
            raise RuntimeError(f"{op.target_rel} changed since preview")


def _write_completed_record(plan: ApplyPlan) -> None:
    data = {
        "apply_id": plan.apply_id,
        "status": ApplyStatus.COMPLETED.value,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(plan.project_root),
        "destination_subdir": plan.destination_subdir,
        "generated_dir": _rel(plan.generated_dir, plan.project_root),
        "validation": _validation_to_dict(plan.validation),
        "operations": [op.to_dict() for op in plan.operations],
    }
    plan.record_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def _write_failed_record(
    plan: ApplyPlan,
    message: str,
    *,
    files_written: list[str] | None = None,
    files_touched: list[str] | None = None,
    backups: list[str] | None = None,
) -> None:
    existing = _read_apply_record(plan.record_path) or {}
    data = {
        "apply_id": plan.apply_id,
        "status": ApplyStatus.FAILED.value,
        "message": message,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "project_root": str(plan.project_root),
        "destination_subdir": plan.destination_subdir,
        "generated_dir": _rel(plan.generated_dir, plan.project_root),
        "validation": _validation_to_dict(plan.validation),
        "operations": [op.to_dict() for op in plan.operations],
        "files_written": files_written or [],
        "files_touched": files_touched or [],
        "backups": backups or [],
    }
    if isinstance(existing.get("created_at"), str):
        data["created_at"] = existing["created_at"]
    plan.status = ApplyStatus.FAILED
    plan.record_path.parent.mkdir(parents=True, exist_ok=True)
    plan.record_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
