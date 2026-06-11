"""Theme version diff viewer."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from juce_theme_studio.core.theme_diff import (
    ThemeDiffReport,
    diff_against_backup,
    diff_manifest_files,
)


class ThemeDiffDialog(QDialog):
    def __init__(self, project_root: Path, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Theme Version Diff")
        self.setMinimumSize(720, 480)
        self._project_root = project_root

        layout = QVBoxLayout(self)
        row = QHBoxLayout()
        self._summary = QLabel("Compare theme manifests or backup exports.")
        row.addWidget(self._summary)
        compare_files_btn = QPushButton("Compare files…")
        compare_files_btn.clicked.connect(self._compare_files)
        row.addWidget(compare_files_btn)
        compare_backup_btn = QPushButton("vs latest backup")
        compare_backup_btn.clicked.connect(self._compare_backup)
        row.addWidget(compare_backup_btn)
        layout.addLayout(row)

        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(["Action", "Category", "Path", "Detail", "Change"])
        self._table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def _show_report(self, report: ThemeDiffReport) -> None:
        self._summary.setText(
            f"{report.left_label} → {report.right_label}: {report.summary()}"
        )
        self._table.setRowCount(len(report.entries))
        for row, entry in enumerate(report.entries):
            self._table.setItem(row, 0, QTableWidgetItem(entry.action))
            self._table.setItem(row, 1, QTableWidgetItem(entry.category))
            self._table.setItem(row, 2, QTableWidgetItem(entry.path))
            self._table.setItem(row, 3, QTableWidgetItem(entry.detail))
            change = entry.new_value if entry.new_value else ""
            if entry.old_value:
                if entry.new_value:
                    change = f"{entry.old_value} → {entry.new_value}"
                else:
                    change = entry.old_value
            self._table.setItem(row, 4, QTableWidgetItem(change))

    def _compare_files(self) -> None:
        a, _ = QFileDialog.getOpenFileName(
            self, "Manifest A", str(self._project_root), "JSON (*.json)",
        )
        if not a:
            return
        b, _ = QFileDialog.getOpenFileName(
            self, "Manifest B", str(self._project_root), "JSON (*.json)",
        )
        if not b:
            return
        self._show_report(diff_manifest_files(Path(a), Path(b)))

    def _compare_backup(self) -> None:
        report = diff_against_backup(self._project_root)
        if report is None:
            self._summary.setText("No backup export found to compare.")
            self._table.setRowCount(0)
            return
        self._show_report(report)
