"""Preview managed apply operations before project files are written."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QListWidget,
    QPlainTextEdit,
    QSplitter,
    QVBoxLayout,
)

from juce_theme_studio.core.managed_apply import (
    ApplyOperation,
    ApplyOperationKind,
    ApplyPlan,
)


class ApplyPreviewDialog(QDialog):
    def __init__(self, plan: ApplyPlan, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Apply Preview")
        self.setMinimumSize(720, 520)
        self._plan = plan

        layout = QVBoxLayout(self)
        conflict_count = sum(1 for op in plan.operations if op.kind == ApplyOperationKind.CONFLICT)
        layout.addWidget(
            QLabel(
                f"{len(plan.operations)} operation(s) planned. "
                f"{conflict_count} conflict(s)."
            )
        )

        split = QSplitter()
        self._list = QListWidget()
        for operation in plan.operations:
            self._list.addItem(self._operation_label(operation))
        split.addWidget(self._list)

        self._detail = QPlainTextEdit()
        self._detail.setReadOnly(True)
        split.addWidget(self._detail)
        layout.addWidget(split)

        self._list.currentRowChanged.connect(self._show_detail)
        if plan.operations:
            self._list.setCurrentRow(0)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        apply_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        apply_button.setText("Apply")
        apply_button.setEnabled(not plan.has_conflicts)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def operation_count(self) -> int:
        return self._list.count()

    def _show_detail(self, row: int) -> None:
        if row < 0 or row >= len(self._plan.operations):
            self._detail.clear()
            return

        operation = self._plan.operations[row]
        lines = [
            f"Action: {operation.kind.value}",
            f"Target: {operation.target_rel}",
            f"Source: {operation.source_rel}",
            f"Generated checksum: {operation.source_checksum}",
        ]
        if operation.target_checksum:
            lines.append(f"Current checksum: {operation.target_checksum}")
        if operation.message:
            lines.append(f"Message: {operation.message}")
        self._detail.setPlainText("\n".join(lines))

    @staticmethod
    def _operation_label(operation: ApplyOperation) -> str:
        return f"{operation.kind.value.upper()}  {operation.target_rel}"
