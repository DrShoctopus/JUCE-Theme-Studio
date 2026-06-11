"""Theme manifest version diffing."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from juce_theme_studio.core.manifest import ThemeManifest


@dataclass
class DiffEntry:
    category: str  # screen | control | asset | setting
    action: str  # added | removed | changed
    path: str
    detail: str = ""
    old_value: str = ""
    new_value: str = ""


@dataclass
class ThemeDiffReport:
    entries: list[DiffEntry] = field(default_factory=list)
    left_label: str = "A"
    right_label: str = "B"

    @property
    def has_changes(self) -> bool:
        return bool(self.entries)

    def summary(self) -> str:
        added = sum(1 for e in self.entries if e.action == "added")
        removed = sum(1 for e in self.entries if e.action == "removed")
        changed = sum(1 for e in self.entries if e.action == "changed")
        return f"+{added} / -{removed} / ~{changed}"


def load_manifest_path(path: Path) -> ThemeManifest:
    return ThemeManifest.load(path)


def diff_manifests(
    left: ThemeManifest,
    right: ThemeManifest,
    *,
    left_label: str = "Before",
    right_label: str = "After",
) -> ThemeDiffReport:
    report = ThemeDiffReport(left_label=left_label, right_label=right_label)
    ld = left.to_dict()
    rd = right.to_dict()

    _diff_scalar(report, "setting", "grid_size", ld, rd)
    _diff_scalar(report, "setting", "snap_to_grid", ld, rd)

    _diff_list(
        report,
        "screen",
        ld.get("screens", []),
        rd.get("screens", []),
        key="id",
        label_key="name",
    )
    _diff_list(
        report,
        "asset",
        ld.get("assets", []),
        rd.get("assets", []),
        key="id",
        label_key="name",
    )

    _diff_controls(report, ld.get("screens", []), rd.get("screens", []))
    return report


def diff_manifest_files(path_a: Path, path_b: Path) -> ThemeDiffReport:
    a = load_manifest_path(path_a)
    b = load_manifest_path(path_b)
    return diff_manifests(
        a,
        b,
        left_label=path_a.name,
        right_label=path_b.name,
    )


def diff_against_backup(project_root: Path) -> ThemeDiffReport | None:
    """Compare current manifest to newest backup export ThemeLayout.json if present."""
    studio = project_root / ".juce_theme_studio"
    current = studio / "theme_project.json"
    if not current.is_file():
        return None

    backups = sorted((studio / "backups").glob("export_*"), reverse=True)
    for backup in backups:
        layout = backup / "ThemeLayout.json"
        if layout.is_file():
            return _diff_current_vs_layout(current, layout)

    return None


def _diff_current_vs_layout(manifest_path: Path, layout_path: Path) -> ThemeDiffReport:
    current = load_manifest_path(manifest_path)
    with layout_path.open(encoding="utf-8") as f:
        layout = json.load(f)
    report = ThemeDiffReport(left_label="backup export", right_label="current manifest")
    backup_screens = {s.get("name", ""): s for s in layout.get("screens", [])}
    cur_screens = {s.name: s for s in current.screens}

    for name in backup_screens:
        if name not in cur_screens:
            report.entries.append(
                DiffEntry("screen", "removed", name, "Screen removed since backup export")
            )

    for name, cur in cur_screens.items():
        if name not in backup_screens:
            report.entries.append(
                DiffEntry("screen", "added", name, "Screen added since backup export")
            )
            continue

        backup_ctrls = {
            c.get("name", ""): c for c in backup_screens[name].get("controls", [])
        }
        cur_ctrls = {c.name: c for c in cur.controls}

        for cname, bctrl in backup_ctrls.items():
            if cname not in cur_ctrls:
                report.entries.append(
                    DiffEntry(
                        "control",
                        "removed",
                        f"{name}/{cname}",
                        "Control removed since backup export",
                    )
                )
                continue
            match = cur_ctrls[cname]
            bounds = bctrl.get("bounds", {})
            if (
                match.x != bounds.get("x")
                or match.y != bounds.get("y")
                or match.width != bounds.get("width")
                or match.height != bounds.get("height")
            ):
                report.entries.append(
                    DiffEntry(
                        "control",
                        "changed",
                        f"{name}/{cname}",
                        "Bounds changed since backup export",
                        old_value=str(bounds),
                        new_value=f"{match.x},{match.y},{match.width},{match.height}",
                    )
                )

        for cname in cur_ctrls:
            if cname not in backup_ctrls:
                report.entries.append(
                    DiffEntry(
                        "control",
                        "added",
                        f"{name}/{cname}",
                        "Control added since backup export",
                    )
                )

    return report


def _diff_scalar(report: ThemeDiffReport, cat: str, key: str, left: dict, right: dict) -> None:
    lv, rv = left.get(key), right.get(key)
    if lv != rv:
        report.entries.append(
            DiffEntry(cat, "changed", key, f"{key} changed", str(lv), str(rv))
        )


def _diff_list(
    report: ThemeDiffReport,
    category: str,
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
    *,
    key: str,
    label_key: str,
) -> None:
    lm = {item[key]: item for item in left}
    rm = {item[key]: item for item in right}
    for kid, item in lm.items():
        if kid not in rm:
            report.entries.append(
                DiffEntry(category, "removed", item.get(label_key, kid), f"Removed {category}")
            )
    for kid, item in rm.items():
        if kid not in lm:
            report.entries.append(
                DiffEntry(category, "added", item.get(label_key, kid), f"Added {category}")
            )
        elif lm[kid] != item:
            report.entries.append(
                DiffEntry(
                    category,
                    "changed",
                    item.get(label_key, kid),
                    f"Modified {category}",
                )
            )


def _diff_controls(
    report: ThemeDiffReport,
    left_screens: list[dict],
    right_screens: list[dict],
) -> None:
    def ctrl_map(screens: list[dict]) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for s in screens:
            sname = s.get("name", s.get("id", ""))
            for c in s.get("controls", []):
                out[f"{sname}/{c.get('name', c.get('id', ''))}"] = c
        return out

    lm = ctrl_map(left_screens)
    rm = ctrl_map(right_screens)
    for path, c in lm.items():
        if path not in rm:
            report.entries.append(DiffEntry("control", "removed", path, "Control removed"))
    for path, c in rm.items():
        if path not in lm:
            report.entries.append(DiffEntry("control", "added", path, "Control added"))
        elif lm[path] != c:
            report.entries.append(
                DiffEntry("control", "changed", path, "Control properties changed"),
            )
