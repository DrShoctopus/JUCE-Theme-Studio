"""Fully managed project apply and revert support."""

from __future__ import annotations

import hashlib
import json
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


def _read_apply_record(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None


def completed_apply_records(project_root: Path) -> list[dict[str, Any]]:
    applies = _applies_dir(project_root.resolve())
    records: list[dict[str, Any]] = []
    for path in sorted(applies.glob("*/apply.json")):
        record = _read_apply_record(path)
        if record and record.get("status") == ApplyStatus.COMPLETED.value:
            records.append(record)
    return records


def latest_completed_apply(project_root: Path) -> dict[str, Any] | None:
    records = completed_apply_records(project_root)
    return records[-1] if records else None


def _latest_managed_checksums(project_root: Path) -> dict[str, str]:
    latest = latest_completed_apply(project_root)
    if not latest:
        return {}
    checksums: dict[str, str] = {}
    for item in latest.get("operations", []):
        target = str(item.get("target_rel", ""))
        source_checksum = str(item.get("source_checksum", ""))
        if target and source_checksum:
            checksums[target] = source_checksum
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
