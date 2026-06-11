"""Heuristic JUCE project scanner."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from pathlib import Path

JUCE_INDICATORS = [
    "juce::Component",
    "paint(",
    "resized(",
    "addAndMakeVisible",
    "setBounds",
    "LookAndFeel",
    "Slider",
    "Button",
    "ImageButton",
    "Label",
]

CLASS_PATTERN = re.compile(
    r"class\s+(\w+)\s*(?::\s*(?:public|private|protected)\s+[\w:<>,\s]+)?\s*\{",
    re.MULTILINE,
)

COMPONENT_BASE_PATTERN = re.compile(
    r"class\s+(\w+)\s*:\s*public\s+juce::Component",
    re.MULTILINE,
)


@dataclass
class DetectedControl:
    cpp_variable: str
    juce_class: str
    line_number: int


@dataclass
class DetectedScreen:
    id: str
    name: str
    class_name: str
    source_file: str
    suggested_width: int = 800
    suggested_height: int = 600
    controls: list[DetectedControl] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class ScanResult:
    project_root: str
    jucer_files: list[str] = field(default_factory=list)
    cmake_files: list[str] = field(default_factory=list)
    source_dirs: list[str] = field(default_factory=list)
    resource_dirs: list[str] = field(default_factory=list)
    image_assets: list[str] = field(default_factory=list)
    cpp_files: list[str] = field(default_factory=list)
    screens: list[DetectedScreen] = field(default_factory=list)
    # APVTS parameter IDs found anywhere in the project.
    parameter_ids: list[str] = field(default_factory=list)
    # Component C++ variable -> parameter ID, from APVTS *Attachment constructors.
    attachments: dict[str, str] = field(default_factory=dict)


# juce::AudioParameterFloat ("gain", ...) or with a ParameterID{ "gain", 1 } wrapper,
# including std::make_unique<juce::AudioParameterFloat>(...).
PARAM_DEF_PATTERN = re.compile(
    r"AudioParameter(?:Float|Bool|Int|Choice|Double)\s*>?\s*\(\s*"
    r'(?:(?:juce::)?ParameterID\s*\{\s*)?"([^"]+)"'
)
# Old-style APVTS createAndAddParameter ("gain", ...).
PARAM_LEGACY_PATTERN = re.compile(r'createAndAddParameter\s*\(\s*"([^"]+)"')
# SliderAttachment (apvts, "gain", gainSlider) — also Button/ComboBox, and the
# std::make_unique<...Attachment>(...) form. Captures (paramID, componentVar).
ATTACHMENT_PATTERN = re.compile(
    r'(?:Slider|Button|ComboBox)Attachment\s*>?\s*[({]\s*'
    r'[\w:.\->()]+\s*,\s*"([^"]+)"\s*,\s*&?\s*(\w+)'
)


def extract_parameters(text: str) -> tuple[list[str], dict[str, str]]:
    """Return (parameter_ids, {component_variable: parameter_id}) from C++ source."""
    param_ids: list[str] = []
    seen: set[str] = set()

    def add(pid: str) -> None:
        if pid and pid not in seen:
            seen.add(pid)
            param_ids.append(pid)

    for match in PARAM_DEF_PATTERN.finditer(text):
        add(match.group(1))
    for match in PARAM_LEGACY_PATTERN.finditer(text):
        add(match.group(1))

    attachments: dict[str, str] = {}
    for match in ATTACHMENT_PATTERN.finditer(text):
        param_id, variable = match.group(1), match.group(2)
        add(param_id)
        attachments[variable] = param_id

    return param_ids, attachments


def _rel(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def scan_juce_project(project_root: Path) -> ScanResult:
    project_root = project_root.resolve()
    result = ScanResult(project_root=".")

    for jucer in project_root.rglob("*.jucer"):
        if STUDIO_IGNORE in jucer.parts:
            continue
        result.jucer_files.append(_rel(jucer, project_root))

    for cmake in project_root.rglob("CMakeLists.txt"):
        if STUDIO_IGNORE in cmake.parts:
            continue
        result.cmake_files.append(_rel(cmake, project_root))

    for dirname in ("Source", "Resources", "BinaryData"):
        d = project_root / dirname
        if d.is_dir():
            if dirname == "Source":
                result.source_dirs.append(dirname)
            else:
                result.resource_dirs.append(dirname)

    image_exts = {".png", ".jpg", ".jpeg", ".svg", ".webp", ".gif", ".bmp"}
    for path in project_root.rglob("*"):
        if STUDIO_IGNORE in path.parts:
            continue
        if path.suffix.lower() in image_exts and path.is_file():
            result.image_assets.append(_rel(path, project_root))

    cpp_files: list[Path] = []
    source_root = project_root / "Source"
    if source_root.is_dir():
        cpp_files = [p for p in source_root.rglob("*.cpp") if STUDIO_IGNORE not in p.parts]
        header_stems = {p.stem for p in source_root.rglob("*.cpp")}
        cpp_files += [
            p for p in source_root.rglob("*.h")
            if STUDIO_IGNORE not in p.parts and p.stem not in header_stems
        ]
    else:
        cpp_files = [
            p
            for p in project_root.rglob("*.cpp")
            if STUDIO_IGNORE not in p.parts and ".juce_theme_studio" not in str(p)
        ]

    seen_classes: set[str] = set()
    param_seen: set[str] = set()
    for cpp in cpp_files:
        result.cpp_files.append(_rel(cpp, project_root))
        screen = _analyze_cpp_file(cpp, project_root)
        if screen is not None and screen.class_name not in seen_classes:
            seen_classes.add(screen.class_name)
            result.screens.append(screen)

        # APVTS parameter IDs and attachments can live in any source file
        # (definitions in the processor, attachments in the editor).
        try:
            text = cpp.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        param_ids, attachments = extract_parameters(text)
        for pid in param_ids:
            if pid not in param_seen:
                param_seen.add(pid)
                result.parameter_ids.append(pid)
        result.attachments.update(attachments)

    return result


STUDIO_IGNORE = ".juce_theme_studio"


def _read_source_bundle(path: Path) -> str:
    """Combine .cpp and sibling .h/.hpp for analysis."""
    parts: list[str] = []
    try:
        parts.append(path.read_text(encoding="utf-8", errors="ignore"))
    except OSError:
        pass
    for extra in (path.with_suffix(".h"), path.with_suffix(".hpp")):
        if extra.is_file():
            try:
                parts.append(extra.read_text(encoding="utf-8", errors="ignore"))
            except OSError:
                pass
    return "\n".join(parts)


def _analyze_cpp_file(path: Path, root: Path) -> DetectedScreen | None:
    from juce_theme_studio.juce.scanner_ast import analyze_with_ast

    ast_screen = analyze_with_ast(path, root)
    if ast_screen is not None:
        return ast_screen

    text = _read_source_bundle(path)
    if not text:
        return None

    match = COMPONENT_BASE_PATTERN.search(text)
    if not match:
        # Fallback: class with paint + resized
        if "paint(" not in text or "resized(" not in text:
            return None
        classes = CLASS_PATTERN.findall(text)
        if not classes:
            return None
        class_name = classes[0]
        confidence = 0.4
    else:
        class_name = match.group(1)
        confidence = 0.8

    indicator_hits = sum(1 for ind in JUCE_INDICATORS if ind in text)
    confidence = min(1.0, confidence + indicator_hits * 0.02)

    controls = _extract_controls(text)

    width, height = _guess_canvas_size(text)

    return DetectedScreen(
        id=uuid.uuid4().hex[:12],
        name=class_name,
        class_name=class_name,
        source_file=_rel(path, root),
        suggested_width=width,
        suggested_height=height,
        controls=controls,
        confidence=confidence,
    )


def _extract_controls(text: str) -> list[DetectedControl]:
    controls: list[DetectedControl] = []
    patterns = [
        (r"juce::Slider\s+(\w+)", "juce::Slider"),
        (r"juce::TextButton\s+(\w+)", "juce::TextButton"),
        (r"juce::ToggleButton\s+(\w+)", "juce::ToggleButton"),
        (r"juce::ImageButton\s+(\w+)", "juce::ImageButton"),
        (r"juce::Label\s+(\w+)", "juce::Label"),
        (r"(\w+Knob)\s+(\w+)", "CustomKnob"),
    ]
    for line_no, line in enumerate(text.splitlines(), start=1):
        for pattern, juce_class in patterns:
            for m in re.finditer(pattern, line):
                var = m.group(2) if juce_class == "CustomKnob" else m.group(1)
                controls.append(DetectedControl(var, juce_class, line_no))
    seen: set[str] = set()
    deduped: list[DetectedControl] = []
    for control in controls:
        if control.cpp_variable not in seen:
            seen.add(control.cpp_variable)
            deduped.append(control)
    return deduped


def _guess_canvas_size(text: str) -> tuple[int, int]:
    m = re.search(r"setSize\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)", text)
    if m:
        return int(m.group(1)), int(m.group(2))
    m = re.search(r"setBounds\s*\(\s*0\s*,\s*0\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", text)
    if m:
        return int(m.group(1)), int(m.group(2))
    return 800, 600
