"""Bottom panel: logs, git status, validation."""

from __future__ import annotations

from PySide6.QtWidgets import QTabWidget, QTextEdit, QVBoxLayout, QWidget

from juce_theme_studio.core.validation import ValidationReport
from juce_theme_studio.git_tools.git import GitStatus


class LogPanel(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        self._tabs = QTabWidget()

        self._log = QTextEdit()
        self._log.setReadOnly(True)
        self._tabs.addTab(self._log, "Logs")

        self._warnings = QTextEdit()
        self._warnings.setReadOnly(True)
        self._tabs.addTab(self._warnings, "Warnings")

        self._git = QTextEdit()
        self._git.setReadOnly(True)
        self._tabs.addTab(self._git, "Git")

        self._validation = QTextEdit()
        self._validation.setReadOnly(True)
        self._tabs.addTab(self._validation, "Validation")

        layout.addWidget(self._tabs)

    def append_log(self, message: str) -> None:
        self._log.append(message)

    def set_warnings(self, messages: list[str]) -> None:
        self._warnings.setPlainText("\n".join(messages) if messages else "No warnings.")

    def set_git_status(self, status: GitStatus) -> None:
        if not status.is_repo:
            self._git.setPlainText("Not a Git repository.")
            return
        lines = [f"Branch: {status.branch}"]
        if status.changed_files:
            lines.append("\nChanged:")
            lines.extend(f"  M {f}" for f in status.changed_files)
        if status.untracked_files:
            lines.append("\nUntracked:")
            lines.extend(f"  ? {f}" for f in status.untracked_files)
        if status.has_unrelated_changes:
            lines.append("\n⚠ Unrelated uncommitted changes exist in this repo.")
        self._git.setPlainText("\n".join(lines))

    def set_validation(self, report: ValidationReport) -> None:
        lines = []
        for issue in report.issues:
            prefix = "ERROR" if issue.level == "error" else "WARN"
            loc = ""
            if issue.screen_id:
                loc = f" [screen={issue.screen_id}]"
            lines.append(f"{prefix}{loc}: {issue.message}")
        self._validation.setPlainText("\n".join(lines) if lines else "No validation issues.")
