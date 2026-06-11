"""Headless project import diagnostic (no GUI required)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from juce_theme_studio.core.assets import import_project_assets
from juce_theme_studio.core.auto_link import auto_link_project_assets
from juce_theme_studio.core.project import load_project, save_project
from juce_theme_studio.core.validation import validate_manifest


def diagnose(project_root: Path, *, import_assets: bool, save: bool) -> int:
    project_root = project_root.resolve()
    if not project_root.is_dir():
        print(f"ERROR: Not a directory: {project_root}", file=sys.stderr)
        return 1

    print(f"Project: {project_root}")
    print("-" * 60)

    loaded = load_project(project_root)
    scan = loaded.scan_result
    manifest = loaded.manifest

    if scan is None:
        print("ERROR: Scanner returned no result.", file=sys.stderr)
        return 1

    print(f"Screens found: {len(scan.screens)}")
    for screen in scan.screens:
        print(f"  - {screen.class_name} ({screen.source_file})")
        print(f"    canvas: {screen.suggested_width}x{screen.suggested_height}")
        for ctrl in screen.controls:
            bounds = ""
            if ctrl.x is not None:
                bounds = f" @ ({ctrl.x},{ctrl.y},{ctrl.width},{ctrl.height})"
            print(f"    control: {ctrl.cpp_variable} [{ctrl.juce_class}]{bounds}")

    print(f"\nImages found: {len(scan.image_assets)}")
    for image in scan.image_assets:
        print(f"  - {image}")

    print(f"\nManifest screens: {len(manifest.screens)}")
    for screen in manifest.screens:
        controls = screen.controls
        linked = sum(1 for c in controls if c.asset_id)
        bg = "yes" if screen.background_asset_id else "no"
        print(f"  - {screen.name} [{screen.juce_component}]: {linked}/{len(controls)} linked, bg={bg}")

    if import_assets and scan.image_assets:
        imported = import_project_assets(manifest, project_root, scan.image_assets)
        print(f"\nImported {len(imported)} asset(s):")
        for entry in imported:
            sprite = " [sprite]" if entry.is_sprite_sheet else ""
            print(f"  - {entry.name}{sprite} ({entry.original_source})")

        linked = auto_link_project_assets(manifest, project_root)
        print(f"\nAuto-linked: {linked} assignment(s)")

        if save:
            save_project(loaded)
            print("\nSaved theme_project.json")

    print("\nControl asset status:")
    unlinked_controls = 0
    for screen in manifest.screens:
        for control in screen.controls:
            asset_label = control.asset_id or "(none — will show as colored block)"
            var = control.mapping.cpp_variable or control.name
            if not control.asset_id and control.control_type.value != "label":
                unlinked_controls += 1
            print(f"  - {screen.name}/{var}: {asset_label}")

    report = validate_manifest(manifest, project_root)
    print(f"\nValidation: {len(report.errors)} error(s), {len(report.warnings)} warning(s)")
    for item in report.errors + report.warnings:
        print(f"  [{item.level}] {item.message}")

    if unlinked_controls:
        print(
            f"\nResult: {unlinked_controls} control(s) still unlinked — "
            "they will appear as colored blocks until assets are assigned."
        )
        return 2

    print("\nResult: All non-label controls have assets assigned.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Diagnose JUCE Theme Studio project import.")
    parser.add_argument("project", type=Path, help="Path to JUCE project root")
    parser.add_argument(
        "--no-import",
        action="store_true",
        help="Scan only; do not import assets or auto-link",
    )
    parser.add_argument(
        "--save",
        action="store_true",
        help="Persist import/auto-link results to .juce_theme_studio/theme_project.json",
    )
    args = parser.parse_args(argv)
    return diagnose(args.project, import_assets=not args.no_import, save=args.save)


if __name__ == "__main__":
    raise SystemExit(main())
