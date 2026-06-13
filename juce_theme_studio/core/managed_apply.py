"""Fully managed project apply and revert support."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from juce_theme_studio.core.manifest import ThemeManifest
from juce_theme_studio.core.types import STUDIO_DIR
from juce_theme_studio.core.validation import ValidationReport, validate_manifest

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
    rel = Path(subdir)
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


def plan_managed_apply(
    manifest: ThemeManifest,
    project_root: Path,
    *,
    destination_subdir: str = DEFAULT_DESTINATION_SUBDIR,
    apply_id: str | None = None,
) -> ApplyPlan:
    project_root = project_root.resolve()
    destination_dir = _safe_project_subdir(
        project_root,
        destination_subdir,
        label="destination",
    )
    destination_rel = _rel(destination_dir, project_root)
    tx_id = _safe_apply_id(apply_id if apply_id is not None else make_apply_id())
    transaction_dir = _applies_dir(project_root) / tx_id
    generated_dir = transaction_dir / "generated"
    return ApplyPlan(
        apply_id=tx_id,
        project_root=project_root,
        transaction_dir=transaction_dir,
        generated_dir=generated_dir,
        destination_subdir=destination_rel,
        validation=validate_manifest(manifest, project_root),
    )
