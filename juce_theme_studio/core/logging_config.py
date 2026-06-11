"""Application logging setup."""

from __future__ import annotations

import logging
from pathlib import Path


def setup_logging(project_studio_dir: Path | None = None) -> logging.Logger:
    """Configure root logger; optionally add file handler in project studio dir."""
    logger = logging.getLogger("juce_theme_studio")
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(formatter)
    logger.addHandler(console)

    if project_studio_dir is not None:
        log_dir = project_studio_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_dir / "studio.log", encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
