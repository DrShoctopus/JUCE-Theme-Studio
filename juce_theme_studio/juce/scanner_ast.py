"""AST-based C++ scanning via tree-sitter-cpp and optional libclang."""

from __future__ import annotations

import logging
import re
import uuid
from pathlib import Path

from juce_theme_studio.juce.scanner import (
    DetectedControl,
    DetectedScreen,
    _guess_canvas_size,
    _read_source_bundle,
    _rel,
)

logger = logging.getLogger(__name__)

_JUCE_MEMBER_TYPES: list[tuple[str, str]] = [
    ("juce::Slider", "juce::Slider"),
    ("juce::TextButton", "juce::TextButton"),
    ("juce::ToggleButton", "juce::ToggleButton"),
    ("juce::ImageButton", "juce::ImageButton"),
    ("juce::Label", "juce::Label"),
    ("juce::ComboBox", "juce::ComboBox"),
    ("juce::DrawableButton", "juce::DrawableButton"),
]

_treesitter_available: bool | None = None
_libclang_available: bool | None = None


def treesitter_available() -> bool:
    global _treesitter_available
    if _treesitter_available is None:
        try:
            import tree_sitter_cpp  # noqa: F401
            from tree_sitter import Language, Parser  # noqa: F401

            _treesitter_available = True
        except ImportError:
            _treesitter_available = False
    return _treesitter_available


def libclang_available() -> bool:
    global _libclang_available
    if _libclang_available is None:
        try:
            import clang.cindex  # noqa: F401

            _libclang_available = True
        except ImportError:
            _libclang_available = False
    return _libclang_available


def analyze_with_ast(path: Path, root: Path) -> DetectedScreen | None:
    """Try tree-sitter, then libclang; return None if both unavailable."""
    text = _read_source_bundle(path)
    if not text:
        return None

    if treesitter_available():
        screen = _analyze_treesitter(path, root, text)
        if screen is not None:
            screen.confidence = min(1.0, screen.confidence + 0.15)
            return screen

    if libclang_available():
        screen = _analyze_libclang(path, root, text)
        if screen is not None:
            screen.confidence = min(1.0, screen.confidence + 0.2)
            return screen

    return None


def _analyze_treesitter(path: Path, root: Path, text: str) -> DetectedScreen | None:
    try:
        import tree_sitter_cpp
        from tree_sitter import Language, Parser

        cpp_lang = tree_sitter_cpp.language()
        if callable(cpp_lang):
            cpp_lang = cpp_lang()
        lang = Language(cpp_lang)
        parser = Parser(lang)
        tree = parser.parse(text.encode("utf-8"))
    except Exception as exc:
        logger.debug("tree-sitter parse failed: %s", exc)
        return None

    class_name: str | None = None
    controls: list[DetectedControl] = []

    for node in _walk(tree.root_node):
        ntype = node.type
        snippet = _node_text(text, node)

        if ntype == "class_specifier" and "juce::Component" in snippet:
            m = re.search(r"class\s+(\w+)", snippet)
            if m:
                class_name = m.group(1)

        if ntype in ("field_declaration", "declaration"):
            for juce_type, label in _JUCE_MEMBER_TYPES:
                if juce_type in snippet:
                    m = re.search(rf"{re.escape(juce_type)}\s+(\w+)", snippet)
                    if m:
                        line = text[: node.start_byte].count("\n") + 1
                        controls.append(DetectedControl(m.group(1), label, line))

        if ntype == "function_definition" and "setBounds" in snippet:
            m = re.search(r"(\w+)\.setBounds\s*\(", snippet)
            if m:
                var = m.group(1)
                if not any(c.cpp_variable == var for c in controls):
                    line = text[: node.start_byte].count("\n") + 1
                    controls.append(DetectedControl(var, "juce::Component", line))

    if not class_name:
        return None

    width, height = _guess_canvas_size(text)
    return DetectedScreen(
        id=uuid.uuid4().hex[:12],
        name=class_name,
        class_name=class_name,
        source_file=_rel(path, root),
        suggested_width=width,
        suggested_height=height,
        controls=_dedupe_controls(controls),
        confidence=0.9,
    )


def _analyze_libclang(path: Path, root: Path, text: str) -> DetectedScreen | None:
    try:
        import clang.cindex as clang
    except ImportError:
        return None

    try:
        index = clang.Index.create()
        args = [
            "-x", "c++", "-std=c++17", "-I/usr/include",
            "-I/Applications/Xcode.app/Contents/Developer/Toolchains/"
            "XcodeDefault.xctoolchain/usr/include/c++/v1",
        ]
        tu = index.parse(str(path), args=args, unsaved_files=[(str(path), text)])
    except Exception as exc:
        logger.debug("libclang parse failed: %s", exc)
        return None

    class_name: str | None = None
    controls: list[DetectedControl] = []

    def visit(cursor) -> None:
        nonlocal class_name
        if cursor.kind == clang.CursorKind.CLASS_DECL:
            spell = cursor.spelling or ""
            for child in cursor.get_children():
                if child.kind == clang.CursorKind.CXX_BASE_SPECIFIER:
                    base = child.type.spelling
                    if "juce::Component" in base or "Component" in base:
                        class_name = spell
        if cursor.kind == clang.CursorKind.FIELD_DECL:
            ctype = cursor.type.spelling
            for juce_type, label in _JUCE_MEMBER_TYPES:
                if juce_type in ctype or ctype.endswith(juce_type.split("::")[-1]):
                    controls.append(
                        DetectedControl(cursor.spelling, label, cursor.location.line)
                    )
        for child in cursor.get_children():
            visit(child)

    try:
        visit(tu.cursor)
    except Exception as exc:
        logger.debug("libclang walk failed: %s", exc)
        return None

    if not class_name:
        return None

    width, height = _guess_canvas_size(text)
    return DetectedScreen(
        id=uuid.uuid4().hex[:12],
        name=class_name,
        class_name=class_name,
        source_file=_rel(path, root),
        suggested_width=width,
        suggested_height=height,
        controls=_dedupe_controls(controls),
        confidence=0.95,
    )


def _walk(node):
    yield node
    for i in range(node.child_count):
        yield from _walk(node.child(i))


def _node_text(source: str, node) -> str:
    return source[node.start_byte : node.end_byte]


def _dedupe_controls(controls: list[DetectedControl]) -> list[DetectedControl]:
    seen: set[str] = set()
    out: list[DetectedControl] = []
    for c in controls:
        if c.cpp_variable not in seen:
            seen.add(c.cpp_variable)
            out.append(c)
    return out
