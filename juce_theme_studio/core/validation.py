"""Pre-export validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from juce_theme_studio.core.assets import asset_exists
from juce_theme_studio.core.manifest import ThemeManifest
from juce_theme_studio.core.types import ControlType


@dataclass
class ValidationIssue:
    level: str  # "error" | "warning"
    message: str
    screen_id: str | None = None
    control_id: str | None = None


@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.level == "warning"]

    @property
    def has_blocking_errors(self) -> bool:
        return bool(self.errors)

    def add(
        self,
        level: str,
        message: str,
        screen_id: str | None = None,
        control_id: str | None = None,
    ) -> None:
        self.issues.append(ValidationIssue(level, message, screen_id, control_id))


def validate_manifest(manifest: ThemeManifest, project_root: Path) -> ValidationReport:
    report = ValidationReport()

    if not project_root.is_dir():
        report.add("error", f"Project root is not readable: {project_root}")
        return report

    studio_dir = project_root / ".juce_theme_studio"
    if not studio_dir.is_dir():
        report.add("warning", "Studio directory does not exist yet; it will be created on save.")

    for asset_entry in manifest.assets:
        if not asset_exists(project_root, asset_entry):
            report.add("error", f"Missing asset file: {asset_entry.relative_path}")

    if not manifest.screens:
        report.add("warning", "No screens defined in project.")

    for screen in manifest.screens:
        names_seen: dict[str, str] = {}
        for control in screen.controls:
            if not control.name.strip():
                report.add("warning", "Control has no name.", screen.id, control.id)

            if control.name in names_seen:
                report.add(
                    "warning",
                    f"Duplicate control name '{control.name}'.",
                    screen.id,
                    control.id,
                )
            names_seen[control.name] = control.id

            if control.asset_id:
                control_asset = manifest.get_asset(control.asset_id)
                if control_asset is None:
                    report.add("error", "Control references unknown asset.", screen.id, control.id)
                elif not asset_exists(project_root, control_asset):
                    report.add("error", "Broken asset path for control.", screen.id, control.id)

            if control.sprite_config:
                sc = control.sprite_config
                if sc.frame_count < 1:
                    report.add("error", "Invalid frame count (< 1).", screen.id, control.id)
                if sc.frame_width < 1 or sc.frame_height < 1:
                    report.add("error", "Invalid frame dimensions.", screen.id, control.id)

            if control.control_type in {ControlType.KNOB, ControlType.SLIDER}:
                if not control.mapping.parameter_id:
                    report.add(
                        "warning",
                        f"Knob/slider '{control.name}' has no parameter ID.",
                        screen.id,
                        control.id,
                    )

            out_of_bounds = (
                control.x + control.width > screen.canvas_width
                or control.y + control.height > screen.canvas_height
            )
            if out_of_bounds:
                report.add(
                    "warning",
                    f"Control '{control.name}' extends outside canvas bounds.",
                    screen.id,
                    control.id,
                )

            if not control.mapping.cpp_variable and not control.mapping.juce_class:
                report.add(
                    "warning",
                    f"Control '{control.name}' is unmapped to JUCE code.",
                    screen.id,
                    control.id,
                )

    return report
