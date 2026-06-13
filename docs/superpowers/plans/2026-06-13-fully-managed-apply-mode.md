# Fully Managed Apply Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build milestone 1 of fully managed mode: preview, apply, record, and revert generated theme files inside a real JUCE project without relying on git.

**Architecture:** Keep export generation separate from project mutation. Refactor the exporter so it can write generated payloads into a staging directory, then add a managed apply layer that plans copy operations into `Source/ThemeStudio/`, records transaction metadata under `.juce_theme_studio/applies/`, and reverts using recorded backups and checksums.

**Tech Stack:** Python 3, PySide6, pytest, stdlib `pathlib`/`hashlib`/`json`/`shutil`, existing `ThemeManifest`, `ValidationReport`, exporter, git status helpers.

---

## File Structure

- Create: `juce_theme_studio/core/managed_apply.py`
  - Owns managed destination path validation, SHA-256 checksums, apply planning, transaction execution, apply-history loading, and revert.
- Create: `juce_theme_studio/gui/dialogs/apply_preview_dialog.py`
  - Shows the apply plan, conflicts, validation status, and file details before project writes.
- Create: `juce_theme_studio/tests/test_managed_apply.py`
  - Unit tests for planning, transaction writes, conflict detection, path safety, and revert behavior.
- Modify: `juce_theme_studio/juce/exporter.py`
  - Extract generated-file writing into a reusable staging writer while keeping current `export_theme()` behavior unchanged.
- Modify: `juce_theme_studio/core/project.py`
  - Create `.juce_theme_studio/applies/` when opening a project.
- Modify: `juce_theme_studio/gui/main_window.py`
  - Add toolbar/menu actions for Apply to Project and Revert Last Apply.
- Modify: `juce_theme_studio/gui/dialogs/help_dialog.py`
  - Document managed apply and revert.
- Modify: `juce_theme_studio/README.md`
  - Document managed apply and revert in the user guide.

This plan intentionally excludes marker-based CMake/source patching. It builds the reversible file transaction foundation first.

---

### Task 1: Refactor Exporter for Staged Writes

**Files:**
- Modify: `juce_theme_studio/juce/exporter.py`
- Test: `juce_theme_studio/tests/test_export.py`

- [ ] **Step 1: Add a failing staged-export test**

Append this test to `juce_theme_studio/tests/test_export.py`:

```python
def test_export_can_write_to_explicit_staging_directory(fixture_project: Path) -> None:
    _, manifest, _ = _project_with_knob(fixture_project)
    staging = fixture_project / ".juce_theme_studio" / "applies" / "preview" / "generated"

    from juce_theme_studio.juce.exporter import export_theme_to_directory

    result = export_theme_to_directory(manifest, fixture_project, staging)

    assert result.export_dir == staging
    assert (staging / "ThemeLayout.json").is_file()
    assert (staging / "ThemeAssets.cpp").is_file()
    assert (staging / "GeneratedThemeComponents.h").is_file()
    assert (staging / "assets").is_dir()
    assert any(path.endswith("ThemeLayout.json") for path in result.files_written)


def test_explicit_staging_directory_must_stay_inside_project_root(
    fixture_project: Path,
    tmp_path: Path,
) -> None:
    _, manifest, _ = _project_with_knob(fixture_project)

    from juce_theme_studio.juce.exporter import export_theme_to_directory

    with pytest.raises(ValueError, match="export directory"):
        export_theme_to_directory(manifest, fixture_project, tmp_path / "outside")
```

- [ ] **Step 2: Run the focused test and verify it fails**

Run:

```bash
pytest juce_theme_studio/tests/test_export.py::test_export_can_write_to_explicit_staging_directory -v
```

Expected: FAIL with an import error for `export_theme_to_directory`.

- [ ] **Step 3: Add the staged export function**

In `juce_theme_studio/juce/exporter.py`, add this function above `export_theme()`:

```python
def export_theme_to_directory(
    manifest: ThemeManifest,
    project_root: Path,
    export_dir: Path,
    *,
    force: bool = False,
) -> ExportResult:
    """Write generated theme files to an explicit directory without backup."""
    project_root = project_root.resolve()
    export_dir = export_dir.resolve()
    try:
        export_dir.relative_to(project_root)
    except ValueError as exc:
        raise ValueError(f"Invalid export directory: {export_dir}") from exc

    validation = validate_manifest(manifest, project_root)
    if validation.has_blocking_errors and not force:
        return ExportResult(export_dir=export_dir, validation=validation)

    export_dir.mkdir(parents=True, exist_ok=True)
    assets_out = export_dir / "assets"
    assets_out.mkdir(exist_ok=True)

    result = ExportResult(export_dir=export_dir, validation=validation)
    _write_export_payload(manifest, project_root, export_dir, assets_out, result)
    return result
```

Then add this helper below `export_theme()`:

```python
def _write_export_payload(
    manifest: ThemeManifest,
    project_root: Path,
    export_dir: Path,
    assets_out: Path,
    result: ExportResult,
) -> None:
    settings = manifest.export_settings
    ns = settings.namespace

    if settings.export_json:
        layout_path = export_dir / "ThemeLayout.json"
        layout_data = _build_layout_json(manifest)
        layout_path.write_text(json.dumps(layout_data, indent=2) + "\n", encoding="utf-8")
        result.files_written.append(str(layout_path.relative_to(project_root)))

    if settings.copy_assets:
        for asset in manifest.assets:
            src = resolve_asset_path(project_root, asset)
            if src.is_file():
                dest = assets_out / _exported_asset_filename(asset.relative_path)
                shutil.copy2(src, dest)
                result.files_written.append(str(dest.relative_to(project_root)))

    if settings.export_cpp:
        cpp_files = {
            "ThemeAssets.h": _gen_theme_assets_h(ns),
            "ThemeAssets.cpp": _gen_theme_assets_cpp(ns),
            "ThemeLookAndFeel.h": _gen_lookandfeel_h(ns),
            "ThemeLookAndFeel.cpp": _gen_lookandfeel_cpp(ns),
            "GeneratedThemeComponents.h": _gen_components_h(ns, manifest),
            "GeneratedThemeComponents.cpp": _gen_components_cpp(ns, manifest),
            "README-INTEGRATION.md": _gen_integration_readme(ns, manifest),
        }
        for filename, content in cpp_files.items():
            path = export_dir / filename
            _write_cpp(path, content, project_root, result)
```

Replace the duplicated payload-writing block inside `export_theme()` with:

```python
_write_export_payload(manifest, project_root, export_dir, assets_out, result)
```

Keep `_safe_export_dir()` unchanged for the existing manual export path.

- [ ] **Step 4: Run exporter tests**

Run:

```bash
pytest juce_theme_studio/tests/test_export.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add juce_theme_studio/juce/exporter.py juce_theme_studio/tests/test_export.py
git commit -m "Refactor exporter for staged theme writes"
```

---

### Task 2: Add Apply Models, Checksums, and Path Safety

**Files:**
- Create: `juce_theme_studio/core/managed_apply.py`
- Modify: `juce_theme_studio/core/project.py`
- Test: `juce_theme_studio/tests/test_managed_apply.py`

- [ ] **Step 1: Write failing tests for path safety and apply directory creation**

Create `juce_theme_studio/tests/test_managed_apply.py` with:

```python
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
```

- [ ] **Step 2: Run the tests and verify they fail**

Run:

```bash
pytest juce_theme_studio/tests/test_managed_apply.py -v
```

Expected: FAIL because `managed_apply.py` does not exist and `applies/` is not created.

- [ ] **Step 3: Create core models and helpers**

Create `juce_theme_studio/core/managed_apply.py` with:

```python
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
from juce_theme_studio.core.validation import ValidationReport, validate_manifest
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
            source_checksum=str(data.get("source_checksum", "")),
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
```

Continue the same file with these helper functions:

```python
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


def _rel(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")
```

- [ ] **Step 4: Create applies directory on project open**

In `juce_theme_studio/core/project.py`, change `ensure_studio_dirs()` so the subfolder tuple includes `"applies"`:

```python
for sub in ("screens", "assets", "exports", "backups", "logs", "applies"):
    (studio / sub).mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 5: Add a temporary planner stub so path tests pass**

Append this to `managed_apply.py`:

```python
def plan_managed_apply(
    manifest: ThemeManifest,
    project_root: Path,
    *,
    destination_subdir: str = DEFAULT_DESTINATION_SUBDIR,
    apply_id: str | None = None,
) -> ApplyPlan:
    project_root = project_root.resolve()
    _safe_project_subdir(project_root, destination_subdir, label="destination")
    tx_id = apply_id or make_apply_id()
    transaction_dir = _applies_dir(project_root) / tx_id
    generated_dir = transaction_dir / "generated"
    return ApplyPlan(
        apply_id=tx_id,
        project_root=project_root,
        transaction_dir=transaction_dir,
        generated_dir=generated_dir,
        destination_subdir=destination_subdir,
        validation=validate_manifest(manifest, project_root),
    )
```

- [ ] **Step 6: Run focused tests**

Run:

```bash
pytest juce_theme_studio/tests/test_project.py juce_theme_studio/tests/test_managed_apply.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

Run:

```bash
git add juce_theme_studio/core/project.py juce_theme_studio/core/managed_apply.py juce_theme_studio/tests/test_managed_apply.py
git commit -m "Add managed apply safety primitives"
```

---

### Task 3: Implement Apply Planning and Conflict Detection

**Files:**
- Modify: `juce_theme_studio/core/managed_apply.py`
- Test: `juce_theme_studio/tests/test_managed_apply.py`

- [ ] **Step 1: Add failing apply-plan tests**

Append these tests to `juce_theme_studio/tests/test_managed_apply.py`:

```python
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
```

- [ ] **Step 2: Run new tests and verify they fail**

Run:

```bash
pytest juce_theme_studio/tests/test_managed_apply.py::test_plan_managed_apply_stages_generated_files juce_theme_studio/tests/test_managed_apply.py::test_plan_flags_existing_unmanaged_destination_as_conflict -v
```

Expected: FAIL because the planner does not stage exports or produce operations.

- [ ] **Step 3: Add apply record loading helpers**

Append this to `managed_apply.py` above `plan_managed_apply()`:

```python
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
```

- [ ] **Step 4: Replace planner stub with real planning**

Replace the body of `plan_managed_apply()` with:

```python
def plan_managed_apply(
    manifest: ThemeManifest,
    project_root: Path,
    *,
    destination_subdir: str = DEFAULT_DESTINATION_SUBDIR,
    apply_id: str | None = None,
) -> ApplyPlan:
    project_root = project_root.resolve()
    destination = _safe_project_subdir(project_root, destination_subdir, label="destination")
    tx_id = apply_id or make_apply_id()
    transaction_dir = _applies_dir(project_root) / tx_id
    generated_dir = transaction_dir / "generated"

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
        destination_subdir=destination_subdir,
        operations=operations,
        validation=validation,
    )
    _write_plan_record(plan)
    return plan
```

Add these helpers near the planner:

```python
def _generated_payload_files(generated_dir: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(generated_dir.rglob("*")):
        if path.is_file():
            rel_parts = path.relative_to(generated_dir).parts
            if rel_parts[0] == "assets" or path.name in MANAGED_OUTPUT_FILES or path.name == "README-INTEGRATION.md":
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
```

- [ ] **Step 5: Run apply planning tests**

Run:

```bash
pytest juce_theme_studio/tests/test_managed_apply.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add juce_theme_studio/core/managed_apply.py juce_theme_studio/tests/test_managed_apply.py
git commit -m "Plan managed theme apply operations"
```

---

### Task 4: Execute Apply Transactions

**Files:**
- Modify: `juce_theme_studio/core/managed_apply.py`
- Test: `juce_theme_studio/tests/test_managed_apply.py`

- [ ] **Step 1: Add failing apply execution tests**

Append these tests:

```python
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
    assert any(op["target_rel"] == "Source/ThemeStudio/ThemeLayout.json" for op in record["operations"])


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
```

- [ ] **Step 2: Run new tests and verify they fail**

Run:

```bash
pytest juce_theme_studio/tests/test_managed_apply.py::test_execute_managed_apply_copies_generated_files_and_records_completion juce_theme_studio/tests/test_managed_apply.py::test_execute_managed_apply_backs_up_replaced_file juce_theme_studio/tests/test_managed_apply.py::test_execute_managed_apply_aborts_when_target_changed_after_preview -v
```

Expected: FAIL because `execute_managed_apply()` does not exist.

- [ ] **Step 3: Add apply result model and execution**

Append this to `managed_apply.py`:

```python
@dataclass
class ApplyResult:
    status: ApplyStatus
    record_path: Path
    files_written: list[str] = field(default_factory=list)
    backups: list[str] = field(default_factory=list)
```

Add this execution function:

```python
def execute_managed_apply(plan: ApplyPlan) -> ApplyResult:
    if plan.has_conflicts:
        _mark_record_status(plan.record_path, ApplyStatus.FAILED, "Plan contains conflicts")
        raise RuntimeError("Cannot apply while conflicts are present")

    _verify_plan_preconditions(plan)
    backup_root = plan.transaction_dir / "backups"
    backup_root.mkdir(parents=True, exist_ok=True)

    files_written: list[str] = []
    backups: list[str] = []
    completed_ops: list[ApplyOperation] = []

    try:
        for op in plan.operations:
            if op.kind == ApplyOperationKind.UNCHANGED:
                completed_ops.append(op)
                continue
            source = plan.generated_dir / op.source_rel
            target = plan.project_root / op.target_rel
            target.parent.mkdir(parents=True, exist_ok=True)

            if target.is_file():
                backup = backup_root / op.target_rel
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target, backup)
                op.backup_rel = _rel(backup, plan.project_root)
                backups.append(op.backup_rel)

            shutil.copy2(source, target)
            files_written.append(op.target_rel)
            completed_ops.append(op)
    except Exception as exc:
        _mark_record_status(plan.record_path, ApplyStatus.FAILED, str(exc))
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
```

Add these helpers:

```python
def _verify_plan_preconditions(plan: ApplyPlan) -> None:
    for op in plan.operations:
        target = plan.project_root / op.target_rel
        if not target.exists():
            if op.target_checksum:
                raise RuntimeError(f"{op.target_rel} changed since preview")
            continue
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


def _mark_record_status(record_path: Path, status: ApplyStatus, message: str) -> None:
    data = _read_apply_record(record_path) or {}
    data["status"] = status.value
    data["message"] = message
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
```

- [ ] **Step 4: Run managed apply tests**

Run:

```bash
pytest juce_theme_studio/tests/test_managed_apply.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add juce_theme_studio/core/managed_apply.py juce_theme_studio/tests/test_managed_apply.py
git commit -m "Execute managed apply transactions"
```

---

### Task 5: Implement Revert Last Apply

**Files:**
- Modify: `juce_theme_studio/core/managed_apply.py`
- Test: `juce_theme_studio/tests/test_managed_apply.py`

- [ ] **Step 1: Add failing revert tests**

Append these tests:

```python
def test_revert_last_apply_restores_modified_files_and_removes_created_files(
    fixture_project: Path,
) -> None:
    loaded = _project_with_theme(fixture_project)

    from juce_theme_studio.core.managed_apply import (
        execute_managed_apply,
        plan_managed_apply,
        revert_last_apply,
    )

    first = plan_managed_apply(loaded.manifest, loaded.root, apply_id="revert-first")
    execute_managed_apply(first)
    loaded.manifest.theme_colors["primary"] = "ff123456"
    second = plan_managed_apply(loaded.manifest, loaded.root, apply_id="revert-second")
    execute_managed_apply(second)

    layout = fixture_project / "Source" / "ThemeStudio" / "ThemeLayout.json"
    before_revert = layout.read_text(encoding="utf-8")
    result = revert_last_apply(fixture_project)

    assert result.files_restored
    assert layout.read_text(encoding="utf-8") != before_revert

    result = revert_last_apply(fixture_project)
    assert result.files_removed
    assert not layout.exists()


def test_revert_refuses_when_managed_file_changed_after_apply(fixture_project: Path) -> None:
    loaded = _project_with_theme(fixture_project)

    from juce_theme_studio.core.managed_apply import (
        execute_managed_apply,
        plan_managed_apply,
        revert_last_apply,
    )

    plan = plan_managed_apply(loaded.manifest, loaded.root, apply_id="revert-conflict")
    execute_managed_apply(plan)
    layout = fixture_project / "Source" / "ThemeStudio" / "ThemeLayout.json"
    layout.write_text("user changed after apply\n", encoding="utf-8")

    with pytest.raises(RuntimeError, match="changed after apply"):
        revert_last_apply(fixture_project)


def test_revert_force_restores_even_when_file_changed_after_apply(
    fixture_project: Path,
) -> None:
    loaded = _project_with_theme(fixture_project)

    from juce_theme_studio.core.managed_apply import (
        execute_managed_apply,
        plan_managed_apply,
        revert_last_apply,
    )

    first = plan_managed_apply(loaded.manifest, loaded.root, apply_id="force-first")
    execute_managed_apply(first)
    loaded.manifest.theme_colors["primary"] = "ff654321"
    second = plan_managed_apply(loaded.manifest, loaded.root, apply_id="force-second")
    execute_managed_apply(second)

    layout = fixture_project / "Source" / "ThemeStudio" / "ThemeLayout.json"
    layout.write_text("changed after apply\n", encoding="utf-8")
    result = revert_last_apply(fixture_project, force=True)

    assert result.files_restored
    assert "changed after apply" not in layout.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run new tests and verify they fail**

Run:

```bash
pytest juce_theme_studio/tests/test_managed_apply.py::test_revert_last_apply_restores_modified_files_and_removes_created_files juce_theme_studio/tests/test_managed_apply.py::test_revert_refuses_when_managed_file_changed_after_apply juce_theme_studio/tests/test_managed_apply.py::test_revert_force_restores_even_when_file_changed_after_apply -v
```

Expected: FAIL because `revert_last_apply()` does not exist.

- [ ] **Step 3: Add revert result and revert implementation**

Append this to `managed_apply.py`:

```python
@dataclass
class RevertResult:
    apply_id: str
    record_path: Path
    files_restored: list[str] = field(default_factory=list)
    files_removed: list[str] = field(default_factory=list)
```

Add this function:

```python
def revert_last_apply(project_root: Path, *, force: bool = False) -> RevertResult:
    project_root = project_root.resolve()
    record = latest_completed_apply(project_root)
    if record is None:
        raise RuntimeError("No completed managed apply to revert")

    apply_id = str(record["apply_id"])
    record_path = _applies_dir(project_root) / apply_id / "apply.json"
    operations = [ApplyOperation.from_dict(item) for item in record.get("operations", [])]

    restored: list[str] = []
    removed: list[str] = []
    for op in reversed(operations):
        target = project_root / op.target_rel
        current_checksum = sha256_file(target) if target.is_file() else ""
        if current_checksum and current_checksum != op.source_checksum and not force:
            raise RuntimeError(f"{op.target_rel} changed after apply")

        if op.backup_rel:
            backup = project_root / op.backup_rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(backup, target)
            restored.append(op.target_rel)
        elif op.kind == ApplyOperationKind.CREATE and target.is_file():
            target.unlink()
            removed.append(op.target_rel)

    data = _read_apply_record(record_path) or record
    data["status"] = ApplyStatus.REVERTED.value
    data["reverted_at"] = datetime.now(timezone.utc).isoformat()
    data["revert"] = {
        "files_restored": restored,
        "files_removed": removed,
        "force": force,
    }
    record_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return RevertResult(
        apply_id=apply_id,
        record_path=record_path,
        files_restored=restored,
        files_removed=removed,
    )
```

- [ ] **Step 4: Run revert tests**

Run:

```bash
pytest juce_theme_studio/tests/test_managed_apply.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add juce_theme_studio/core/managed_apply.py juce_theme_studio/tests/test_managed_apply.py
git commit -m "Revert managed theme applies"
```

---

### Task 6: Add Apply Preview Dialog

**Files:**
- Create: `juce_theme_studio/gui/dialogs/apply_preview_dialog.py`
- Test: `juce_theme_studio/tests/test_managed_apply.py`

- [ ] **Step 1: Add a focused dialog construction test**

Append this test to `juce_theme_studio/tests/test_managed_apply.py`:

```python
def test_apply_preview_dialog_shows_operations(qapp, fixture_project: Path) -> None:
    pytest.importorskip("PySide6")
    loaded = _project_with_theme(fixture_project)

    from juce_theme_studio.core.managed_apply import plan_managed_apply
    from juce_theme_studio.gui.dialogs.apply_preview_dialog import ApplyPreviewDialog

    plan = plan_managed_apply(loaded.manifest, loaded.root, apply_id="dialog")
    dialog = ApplyPreviewDialog(plan)

    assert dialog.windowTitle() == "Apply Preview"
    assert dialog.operation_count() == len(plan.operations)
```

If `qapp` is only defined in `test_main_window.py`, move that fixture to `juce_theme_studio/tests/conftest.py`:

```python
@pytest.fixture(scope="module")
def qapp():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
```

- [ ] **Step 2: Run the dialog test and verify it fails**

Run:

```bash
pytest juce_theme_studio/tests/test_managed_apply.py::test_apply_preview_dialog_shows_operations -v
```

Expected: FAIL because `ApplyPreviewDialog` does not exist.

- [ ] **Step 3: Create the dialog**

Create `juce_theme_studio/gui/dialogs/apply_preview_dialog.py`:

```python
"""Preview a managed apply transaction before project files are changed."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QPlainTextEdit,
    QSplitter,
    QVBoxLayout,
)

from juce_theme_studio.core.managed_apply import ApplyOperationKind, ApplyPlan


class ApplyPreviewDialog(QDialog):
    def __init__(self, plan: ApplyPlan, parent=None) -> None:
        super().__init__(parent)
        self._plan = plan
        self.setWindowTitle("Apply Preview")
        self.setMinimumSize(720, 520)

        layout = QVBoxLayout(self)
        conflicts = sum(1 for op in plan.operations if op.kind == ApplyOperationKind.CONFLICT)
        layout.addWidget(
            QLabel(
                f"{len(plan.operations)} managed file operation(s). "
                f"Conflicts: {conflicts}."
            )
        )

        split = QSplitter()
        self._list = QListWidget()
        for op in plan.operations:
            self._list.addItem(f"{op.kind.value.upper()}  {op.target_rel}")
        split.addWidget(self._list)

        self._detail = QPlainTextEdit()
        self._detail.setReadOnly(True)
        split.addWidget(self._detail)
        layout.addWidget(split)

        self._list.currentRowChanged.connect(self._show_detail)
        if plan.operations:
            self._list.setCurrentRow(0)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Apply")
        buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(not plan.has_conflicts)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def operation_count(self) -> int:
        return self._list.count()

    def _show_detail(self, row: int) -> None:
        if row < 0 or row >= len(self._plan.operations):
            self._detail.clear()
            return
        op = self._plan.operations[row]
        lines = [
            f"Action: {op.kind.value}",
            f"Target: {op.target_rel}",
            f"Source: {op.source_rel}",
            f"Generated checksum: {op.source_checksum}",
        ]
        if op.target_checksum:
            lines.append(f"Current checksum: {op.target_checksum}")
        if op.message:
            lines.append("")
            lines.append(op.message)
        self._detail.setPlainText("\n".join(lines))
```

- [ ] **Step 4: Run dialog test**

Run:

```bash
pytest juce_theme_studio/tests/test_managed_apply.py::test_apply_preview_dialog_shows_operations -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
git add juce_theme_studio/gui/dialogs/apply_preview_dialog.py juce_theme_studio/tests/test_managed_apply.py juce_theme_studio/tests/conftest.py
git commit -m "Add managed apply preview dialog"
```

---

### Task 7: Wire Apply and Revert into the Main Window

**Files:**
- Modify: `juce_theme_studio/gui/main_window.py`
- Test: `juce_theme_studio/tests/test_main_window.py`

- [ ] **Step 1: Add failing main-window wiring tests**

Append these tests to `juce_theme_studio/tests/test_main_window.py`:

```python
def test_main_window_has_apply_and_revert_actions(window) -> None:
    action_texts = [action.text() for action in window.findChildren(QAction)]

    assert "Apply to Project" in action_texts
    assert "Revert Last Apply" in action_texts


def test_apply_cancel_does_not_write_project_files(
    window,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from juce_theme_studio.gui import main_window as main_window_module

    class CancelApplyPreview:
        DialogCode = QDialog.DialogCode

        def __init__(self, *args, **kwargs) -> None:  # noqa: ANN002, ANN003
            pass

        def exec(self):
            return QDialog.DialogCode.Rejected

    calls: list[str] = []
    monkeypatch.setattr(main_window_module, "ApplyPreviewDialog", CancelApplyPreview)
    monkeypatch.setattr(
        main_window_module,
        "execute_managed_apply",
        lambda plan: calls.append(plan.apply_id),
    )

    window._apply_to_project()

    assert calls == []
```

Add `QAction` to the existing import line near the top of the file:

```python
from PySide6.QtGui import QAction
```

- [ ] **Step 2: Run main-window tests and verify they fail**

Run:

```bash
pytest juce_theme_studio/tests/test_main_window.py::test_main_window_has_apply_and_revert_actions juce_theme_studio/tests/test_main_window.py::test_apply_cancel_does_not_write_project_files -v
```

Expected: FAIL because actions and `_apply_to_project()` do not exist.

- [ ] **Step 3: Add imports and toolbar/menu actions**

In `juce_theme_studio/gui/main_window.py`, add imports:

```python
from juce_theme_studio.core.managed_apply import (
    execute_managed_apply,
    plan_managed_apply,
    revert_last_apply,
)
from juce_theme_studio.gui.dialogs.apply_preview_dialog import ApplyPreviewDialog
```

In `_build_toolbar()`, add this after the Export action loop:

```python
apply_act = QAction("Apply to Project", self)
apply_act.triggered.connect(self._apply_to_project)
tb.addAction(apply_act)
```

In `_build_menus()`, add this after `file_menu.addAction("Export...", self._export)`:

```python
file_menu.addAction("Apply to Project", self._apply_to_project)
file_menu.addAction("Revert Last Apply", self._revert_last_apply)
```

- [ ] **Step 4: Add apply and revert methods**

Add these methods near `_export()`:

```python
def _apply_to_project(self) -> None:
    if not self._project:
        QMessageBox.information(self, "No project", "Open a project first.")
        return

    report = validate_manifest(self._project.manifest, self._project.root)
    self._log_panel.set_validation(report)
    if report.has_blocking_errors:
        QMessageBox.warning(
            self,
            "Validation errors",
            "Resolve blocking validation errors before applying to the project.",
        )
        return

    status = get_status(self._project.root)
    if status.is_repo and status.has_unrelated_changes:
        reply = QMessageBox.question(
            self,
            "Uncommitted changes",
            "This repository has uncommitted changes outside .juce_theme_studio/.\n\n"
            "Continue with managed apply?",
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

    plan = plan_managed_apply(self._project.manifest, self._project.root)
    preview = ApplyPreviewDialog(plan, self)
    if preview.exec() != ApplyPreviewDialog.DialogCode.Accepted:
        return

    try:
        result = execute_managed_apply(plan)
    except Exception as exc:
        QMessageBox.critical(self, "Apply failed", str(exc))
        self._log_panel.append_log(f"Apply failed: {exc}")
        return

    save_project(self._project)
    self._set_dirty(False)
    self._log_panel.append_log(
        f"Applied {len(result.files_written)} file(s) to project.\n"
        f"Transaction: {result.record_path}"
    )
    QMessageBox.information(
        self,
        "Apply complete",
        f"Applied {len(result.files_written)} file(s) to the project.\n\n"
        f"Transaction: {result.record_path}",
    )
    self._refresh_git_status()


def _revert_last_apply(self) -> None:
    if not self._project:
        QMessageBox.information(self, "No project", "Open a project first.")
        return

    reply = QMessageBox.question(
        self,
        "Revert last apply",
        "Restore files from the latest completed managed apply transaction?",
    )
    if reply != QMessageBox.StandardButton.Yes:
        return

    try:
        result = revert_last_apply(self._project.root)
    except Exception as exc:
        QMessageBox.critical(self, "Revert failed", str(exc))
        self._log_panel.append_log(f"Revert failed: {exc}")
        return

    self._log_panel.append_log(
        f"Reverted apply {result.apply_id}.\n"
        f"Restored: {len(result.files_restored)} file(s)\n"
        f"Removed: {len(result.files_removed)} file(s)"
    )
    QMessageBox.information(
        self,
        "Revert complete",
        f"Restored {len(result.files_restored)} file(s).\n"
        f"Removed {len(result.files_removed)} file(s).",
    )
    self._refresh_git_status()
```

- [ ] **Step 5: Run main-window tests**

Run:

```bash
pytest juce_theme_studio/tests/test_main_window.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
git add juce_theme_studio/gui/main_window.py juce_theme_studio/tests/test_main_window.py
git commit -m "Wire managed apply into main window"
```

---

### Task 8: Document Managed Apply and Revert

**Files:**
- Modify: `juce_theme_studio/README.md`
- Modify: `juce_theme_studio/gui/dialogs/help_dialog.py`

- [ ] **Step 1: Update README managed workflow docs**

In `juce_theme_studio/README.md`, add a subsection after the current Export section:

```markdown
### Managed Apply

**Apply to Project** copies the generated runtime theme files into
`Source/ThemeStudio/` and records a transaction under
`.juce_theme_studio/applies/`.

Before writing project files, the Apply Preview shows every create, replace,
unchanged file, or conflict. Conflicts block apply until the destination file is
removed, restored, or manually reconciled.

Use **Revert Last Apply** to restore files from the latest completed apply. The
revert works without Git by using transaction backups and checksums. If a managed
file changed after apply, revert stops instead of overwriting it.
```

In the Safety Guarantees section, add:

```markdown
- Managed apply writes only inside the selected project root.
- Managed apply stores transaction records and backups in `.juce_theme_studio/applies/`.
- Revert works without Git and refuses to overwrite files changed after apply.
```

- [ ] **Step 2: Update in-app help**

In `juce_theme_studio/gui/dialogs/help_dialog.py`, find the Export help HTML and add a short Managed Apply subsection with the same user-facing facts:

```html
<h3>Managed Apply</h3>
<p><b>Apply to Project</b> copies generated runtime files into
<code>Source/ThemeStudio/</code> and records a reversible transaction under
<code>.juce_theme_studio/applies/</code>.</p>
<p>The preview lists creates, replacements, unchanged files, and conflicts before
anything in the project is modified. Use <b>Revert Last Apply</b> to restore the
latest completed transaction.</p>
```

- [ ] **Step 3: Run a documentation sanity check**

Run:

```bash
rg -n "Managed Apply|Revert Last Apply|Source/ThemeStudio" juce_theme_studio/README.md juce_theme_studio/gui/dialogs/help_dialog.py
```

Expected: Matches in both files.

- [ ] **Step 4: Commit**

Run:

```bash
git add juce_theme_studio/README.md juce_theme_studio/gui/dialogs/help_dialog.py
git commit -m "Document managed apply workflow"
```

---

### Task 9: Final Verification

**Files:**
- No code files changed in this task.

- [ ] **Step 1: Run focused test suite**

Run:

```bash
pytest juce_theme_studio/tests/test_export.py juce_theme_studio/tests/test_project.py juce_theme_studio/tests/test_managed_apply.py juce_theme_studio/tests/test_main_window.py -v
```

Expected: PASS.

- [ ] **Step 2: Run full test suite**

Run:

```bash
pytest
```

Expected: PASS.

- [ ] **Step 3: Check formatting of changed files**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 4: Inspect final changed files**

Run:

```bash
git status --short
git log --oneline -6
```

Expected: clean worktree, with commits for exporter staging, safety primitives, planning, apply execution, revert, GUI wiring, and docs.

---

## Self-Review Notes

- Spec coverage: milestone 1 covers staged managed apply to `Source/ThemeStudio/`, transaction manifest, backups, preview, revert last apply, path safety, checksum protection, and git dirty-state warnings.
- Deferred scope: marker-based CMake/source patching is explicitly milestone 2 and is not implemented in this plan.
- Type consistency: plan uses `ApplyPlan`, `ApplyOperation`, `ApplyOperationKind`, `ApplyStatus`, `ApplyResult`, and `RevertResult` consistently across core, dialog, and main-window tasks.
