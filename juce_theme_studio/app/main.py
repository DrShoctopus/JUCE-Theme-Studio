"""JUCE Theme Studio application entry point."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from juce_theme_studio.core.logging_config import setup_logging
from juce_theme_studio.gui.main_window import MainWindow


def main() -> int:
    setup_logging()
    app = QApplication(sys.argv)
    app.setApplicationName("JUCE Theme Studio")
    app.setOrganizationName("JUCE Theme Studio")

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
