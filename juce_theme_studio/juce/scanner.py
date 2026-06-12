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


# --------------------------------------------------------------------------
# Project-wide class graph: detects screens that subclass a custom Component
# base (e.g. a shared ``PageBase``), handles the ``final`` keyword, multiple
# classes per file, and never mistakes an ``enum class`` for a screen.
# --------------------------------------------------------------------------

# A class/struct definition header, capturing name and base clause up to the
# opening brace. The optional leading ``enum`` group lets us reject enum
# classes. Forward declarations (``class Foo;``) lack a ``{`` and never match.
_CLASS_HEADER_PATTERN = re.compile(
    r"(?P<enum>\benum\s+)?\b(?:class|struct)\s+(?P<name>\w+)\b(?P<rest>[^{};]*)\{"
)

_ACCESS_KEYWORDS = {"public", "private", "protected", "virtual"}
_COMPONENT_BASES = {"juce::Component", "Component"}

# constexpr / const / #define integer constants used as setSize() arguments.
_INT_CONST_PATTERN = re.compile(
    r"(?:(?:static\s+)?(?:constexpr|const)\s+int|#define)\s+(\w+)\s*=?\s*(\d+)"
)
_SET_SIZE_PATTERN = re.compile(r"setSize\s*\(\s*([\w:]+)\s*,\s*([\w:]+)\s*\)")


@dataclass
class _ClassInfo:
    name: str
    bases: list[str]
    body: str
    source_file: str
    canvas_text: str = ""


def _split_top_level(text: str, sep: str = ",") -> list[str]:
    """Split on ``sep`` ignoring separators nested inside <>, (), or []."""
    parts: list[str] = []
    depth = 0
    cur: list[str] = []
    for ch in text:
        if ch in "<([":
            depth += 1
        elif ch in ">)]":
            depth = max(0, depth - 1)
        if ch == sep and depth == 0:
            parts.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append("".join(cur))
    return parts


def _normalize_base(spec: str) -> str:
    """``public juce::Component`` -> ``juce::Component`` (drops access keywords)."""
    tokens = [t for t in spec.replace("\n", " ").split() if t not in _ACCESS_KEYWORDS]
    if not tokens:
        return ""
    return re.split(r"[<\s]", tokens[0], maxsplit=1)[0].strip()


def _parse_bases(rest: str) -> list[str]:
    if ":" not in rest:
        return []
    clause = rest.split(":", 1)[1]
    return [b for b in (_normalize_base(p) for p in _split_top_level(clause)) if b]


def _class_body(text: str, open_idx: int) -> str:
    """Return the text between the brace at ``open_idx`` and its match, skipping
    comments and string/char literals so braces inside them do not unbalance."""
    depth = 0
    i = open_idx
    n = len(text)
    start = open_idx + 1
    while i < n:
        ch = text[i]
        two = text[i : i + 2]
        if two == "//":
            j = text.find("\n", i)
            i = n if j == -1 else j
            continue
        if two == "/*":
            j = text.find("*/", i + 2)
            i = n if j == -1 else j + 2
            continue
        if ch in ('"', "'"):
            i += 1
            while i < n:
                if text[i] == "\\":
                    i += 2
                    continue
                if text[i] == ch:
                    break
                i += 1
            i += 1
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start:i]
        i += 1
    return text[start:]


def _parse_classes_in_file(text: str, rel_path: str) -> list[_ClassInfo]:
    out: list[_ClassInfo] = []
    for m in _CLASS_HEADER_PATTERN.finditer(text):
        if m.group("enum"):
            continue
        out.append(
            _ClassInfo(
                name=m.group("name"),
                bases=_parse_bases(m.group("rest")),
                body=_class_body(text, m.end() - 1),
                source_file=rel_path,
            )
        )
    return out


def _guess_canvas_with_consts(text: str, consts: dict[str, int]) -> tuple[int, int]:
    """Resolve setSize(W, H) where arguments may be integer constants."""

    def resolve(token: str) -> int | None:
        if token.isdigit():
            return int(token)
        return consts.get(token.split("::")[-1])

    for m in _SET_SIZE_PATTERN.finditer(text):
        w, h = resolve(m.group(1)), resolve(m.group(2))
        if w and h:
            return w, h
    return _guess_canvas_size(text)


def _detect_screens(files: list[Path], root: Path) -> list[DetectedScreen]:
    classes: dict[str, _ClassInfo] = {}
    stem_text: dict[str, str] = {}
    consts: dict[str, int] = {}

    for path in files:
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        stem_text[path.stem] = stem_text.get(path.stem, "") + "\n" + text
        for name, value in _INT_CONST_PATTERN.findall(text):
            consts.setdefault(name, int(value))
        for info in _parse_classes_in_file(text, _rel(path, root)):
            classes.setdefault(info.name, info)  # first declaration wins

    for info in classes.values():
        stem = Path(info.source_file).stem
        info.canvas_text = info.body + "\n" + stem_text.get(stem, "")

    # Transitive closure of classes that ultimately derive from juce::Component.
    derived: set[str] = set()
    changed = True
    while changed:
        changed = False
        for info in classes.values():
            if info.name in derived:
                continue
            if any(b in _COMPONENT_BASES or b in derived for b in info.bases):
                derived.add(info.name)
                changed = True

    # A "page base" is a Component-derived class that >= 2 other Component-derived
    # classes inherit from (e.g. PageBase <- PedalsPage/AmpPage/CabPostPage).
    child_count: dict[str, int] = {}
    for info in classes.values():
        for base in info.bases:
            child_count[base] = child_count.get(base, 0) + 1
    page_bases = {n for n in derived if child_count.get(n, 0) >= 2}

    if page_bases:
        # The screens are the concrete pages, not the abstract base or the
        # widgets/container that merely derive from juce::Component directly.
        screen_infos = [
            c for c in classes.values() if c.name in derived and set(c.bases) & page_bases
        ]
        base_confidence = 0.85
    else:
        # Conventional layout: each class directly deriving from juce::Component
        # that is not itself used as a base by another class.
        screen_infos = [
            c
            for c in classes.values()
            if c.name in derived
            and (_COMPONENT_BASES & set(c.bases))
            and c.name not in child_count
        ]
        base_confidence = 0.8

    screen_infos.sort(key=lambda c: (c.source_file, c.name))
    screens: list[DetectedScreen] = []
    for info in screen_infos:
        hits = sum(1 for ind in JUCE_INDICATORS if ind in info.canvas_text)
        width, height = _guess_canvas_with_consts(info.canvas_text, consts)
        screens.append(
            DetectedScreen(
                id=uuid.uuid4().hex[:12],
                name=info.name,
                class_name=info.name,
                source_file=info.source_file,
                suggested_width=width,
                suggested_height=height,
                controls=_extract_controls(info.body),
                confidence=min(1.0, base_confidence + hits * 0.02),
            )
        )
    return screens


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

    # Gather every C++ source/header for the project-wide class graph. Class
    # declarations live in headers, so both extensions must be parsed together.
    code_exts = {".h", ".hpp", ".hh", ".hxx", ".cpp", ".cc", ".cxx", ".cppm"}
    cpp_exts = {".cpp", ".cc", ".cxx", ".cppm"}
    source_root = project_root / "Source"
    search_root = source_root if source_root.is_dir() else project_root
    all_source_files = [
        p
        for p in search_root.rglob("*")
        if p.is_file() and p.suffix.lower() in code_exts and STUDIO_IGNORE not in p.parts
    ]

    result.screens = _detect_screens(all_source_files, project_root)

    # APVTS parameter IDs and attachments can live in any source file
    # (definitions in the processor, attachments in the editor).
    param_seen: set[str] = set()
    for src in all_source_files:
        if src.suffix.lower() in cpp_exts:
            result.cpp_files.append(_rel(src, project_root))
        try:
            text = src.read_text(encoding="utf-8", errors="ignore")
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
