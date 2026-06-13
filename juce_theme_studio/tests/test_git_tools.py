"""Tests for scoped git helpers."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from juce_theme_studio.git_tools.git import commit


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def test_commit_with_files_excludes_unrelated_staged_changes(tmp_path: Path) -> None:
    if shutil.which("git") is None:
        pytest.skip("git not available")

    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init")
    _git(root, "config", "user.email", "test@example.com")
    _git(root, "config", "user.name", "Test User")
    theme_dir = root / ".juce_theme_studio"
    theme_dir.mkdir()
    theme_file = theme_dir / "theme_project.json"
    theme_file.write_text('{"theme": true}\n', encoding="utf-8")
    unrelated = root / "unrelated.txt"
    unrelated.write_text("keep staged for later\n", encoding="utf-8")
    _git(root, "add", "unrelated.txt")

    sha = commit(root, "theme only", [".juce_theme_studio/theme_project.json"])

    committed = _git(root, "show", "--name-only", "--pretty=format:", "HEAD").splitlines()
    status = _git(root, "status", "--short")
    assert sha
    assert committed == [".juce_theme_studio/theme_project.json"]
    assert "A  unrelated.txt" in status
