"""Git commit dialog — explicit confirmation required."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from juce_theme_studio.git_tools.git import (
    commit,
    create_backup_branch,
    get_diff,
    get_status,
)


class GitCommitDialog(QDialog):
    def __init__(self, project_root: Path, parent=None) -> None:
        super().__init__(parent)
        self.project_root = project_root
        self.setWindowTitle("Commit Theme Changes")
        self.setMinimumSize(600, 500)

        layout = QVBoxLayout(self)
        self._status = get_status(project_root)
        branch_row = QHBoxLayout()
        branch_row.addWidget(QLabel(f"Branch: {self._status.branch or 'unknown'}"))
        backup_btn = QPushButton("Create backup branch")
        backup_btn.clicked.connect(self._create_backup_branch)
        branch_row.addWidget(backup_btn)
        layout.addLayout(branch_row)

        if self._status.has_unrelated_changes:
            warn = QLabel(
                "Warning: This repository has uncommitted changes outside .juce_theme_studio/. "
                "Only select theme files to commit."
            )
            warn.setWordWrap(True)
            warn.setStyleSheet("color: #c90;")
            layout.addWidget(warn)

        self._file_list = QListWidget()
        self._file_list.setSelectionMode(QAbstractItemView.SelectionMode.MultiSelection)
        studio_prefix = ".juce_theme_studio"
        candidates = sorted(
            set(self._status.changed_files + self._status.untracked_files)
        )
        theme_files = [f for f in candidates if f.startswith(studio_prefix)]
        for f in theme_files:
            self._file_list.addItem(f)
            self._file_list.item(self._file_list.count() - 1).setSelected(True)
        layout.addWidget(QLabel("Files to stage:"))
        layout.addWidget(self._file_list)

        self._diff = QPlainTextEdit()
        self._diff.setReadOnly(True)
        layout.addWidget(QLabel("Diff preview:"))
        layout.addWidget(self._diff)
        self._file_list.currentTextChanged.connect(self._show_diff)

        self._message = QLineEdit("Add/update JUCE theme assets and generated layout files")
        layout.addWidget(QLabel("Commit message:"))
        layout.addWidget(self._message)

        self._confirm = QCheckBox("I confirm I want to commit the selected files")
        layout.addWidget(self._confirm)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._do_commit)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if theme_files:
            self._file_list.setCurrentRow(0)

    def _create_backup_branch(self) -> None:
        try:
            name = create_backup_branch(self.project_root)
            QMessageBox.information(
                self,
                "Backup branch",
                f"Created and checked out branch: {name}\n"
                "You can commit theme changes here safely.",
            )
            self._status = get_status(self.project_root)
        except Exception as exc:
            QMessageBox.critical(self, "Branch failed", str(exc))

    def _show_diff(self, path: str) -> None:
        if path:
            diff = get_diff(self.project_root, path)
            self._diff.setPlainText(diff.diff_text or "(no diff)")

    def _do_commit(self) -> None:
        if not self._confirm.isChecked():
            QMessageBox.warning(self, "Confirm", "Please check the confirmation box to commit.")
            return
        files = [item.text() for item in self._file_list.selectedItems()]
        if not files:
            QMessageBox.warning(self, "No files", "No theme files to commit.")
            return
        msg = self._message.text().strip()
        if not msg:
            QMessageBox.warning(self, "Message", "Commit message is required.")
            return
        try:
            sha = commit(self.project_root, msg, files)
            QMessageBox.information(self, "Committed", f"Commit created: {sha}")
            self.accept()
        except Exception as exc:
            QMessageBox.critical(self, "Commit failed", str(exc))
