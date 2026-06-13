"""Shared pytest fixtures."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

FIXTURE_PROJECT = Path(__file__).resolve().parent.parent / "examples" / "mock_juce_project"


@pytest.fixture
def fixture_project(tmp_path: Path) -> Path:
    """Copy mock JUCE project to a temp directory."""
    dest = tmp_path / "mock_project"
    shutil.copytree(FIXTURE_PROJECT, dest)
    return dest


@pytest.fixture(scope="module")
def qapp():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
