"""About dialog for JUCE Theme Studio."""

from __future__ import annotations

import sys

from PySide6 import __version__ as pyside_version
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
)

try:
    from juce_theme_studio import __version__
except ImportError:
    __version__ = "0.2.0"


class AboutDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("About JUCE Theme Studio")
        self.setFixedWidth(420)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(32, 28, 32, 20)

        title = QLabel("JUCE Theme Studio")
        title_font = QFont()
        title_font.setPointSize(20)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)

        version_label = QLabel(f"Version {__version__}")
        version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(version_label)

        layout.addSpacing(8)

        description = QLabel(
            "Visual theme editor for JUCE audio plugin\n"
            "and application projects."
        )
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description.setWordWrap(True)
        layout.addWidget(description)

        layout.addSpacing(12)

        copyright_label = QLabel("Copyright © 2026 Shoctopus")
        copyright_font = QFont()
        copyright_font.setBold(True)
        copyright_label.setFont(copyright_font)
        copyright_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(copyright_label)

        license_label = QLabel("Released under the MIT License.")
        license_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(license_label)

        layout.addSpacing(16)

        python_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        build_info = QLabel(
            f"Python {python_ver}  ·  PySide6 {pyside_version}"
        )
        build_info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        small_font = QFont()
        small_font.setPointSize(10)
        build_info.setFont(small_font)
        build_info.setStyleSheet("color: #888;")
        layout.addWidget(build_info)

        third_party = QLabel(
            "Third-party libraries: PySide6, Pillow, GitPython"
        )
        third_party.setAlignment(Qt.AlignmentFlag.AlignCenter)
        third_party.setFont(small_font)
        third_party.setStyleSheet("color: #888;")
        layout.addWidget(third_party)

        optional_note = QLabel(
            "Optional: tree-sitter-cpp, opencv-python-headless, libclang"
        )
        optional_note.setAlignment(Qt.AlignmentFlag.AlignCenter)
        optional_note.setFont(small_font)
        optional_note.setStyleSheet("color: #666;")
        optional_note.setWordWrap(True)
        layout.addWidget(optional_note)

        layout.addSpacing(8)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)
