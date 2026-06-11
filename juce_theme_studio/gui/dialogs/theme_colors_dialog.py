"""Edit the theme colour palette exported to ThemeLayout.json / ThemeLookAndFeel."""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
)

from juce_theme_studio.core.manifest import DEFAULT_THEME_COLORS, ThemeManifest

# Friendly labels and display order for the known palette keys.
COLOR_FIELDS: list[tuple[str, str]] = [
    ("background", "Background"),
    ("surface", "Surface / panel"),
    ("primary", "Primary (knobs / sliders)"),
    ("text", "Text"),
    ("meter", "Meter"),
    ("meterWarning", "Meter warning"),
    ("meterClip", "Meter clip"),
]


def hex_to_qcolor(value: str) -> QColor:
    """Parse an 'aarrggbb' (or 'rrggbb') hex string into a QColor."""
    h = value.strip().lstrip("#")
    if len(h) == 6:
        h = "ff" + h
    if len(h) != 8:
        return QColor(0, 0, 0)
    a = int(h[0:2], 16)
    r = int(h[2:4], 16)
    g = int(h[4:6], 16)
    b = int(h[6:8], 16)
    return QColor(r, g, b, a)


def qcolor_to_hex(color: QColor) -> str:
    """Serialise a QColor to JUCE's 'aarrggbb' hex form."""
    return f"{color.alpha():02x}{color.red():02x}{color.green():02x}{color.blue():02x}"


class ThemeColorsDialog(QDialog):
    def __init__(self, manifest: ThemeManifest, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Theme Colors")
        self._manifest = manifest
        # Work on a copy until the user accepts.
        self._values: dict[str, str] = dict(manifest.theme_colors)
        self._swatches: dict[str, QPushButton] = {}

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Colours are exported to ThemeLayout.json and applied by\n"
                                "the generated ThemeLookAndFeel."))
        form = QFormLayout()

        keys = [k for k, _ in COLOR_FIELDS]
        keys += [k for k in self._values if k not in keys]  # any custom keys
        labels = dict(COLOR_FIELDS)

        for key in keys:
            swatch = QPushButton()
            swatch.setFixedWidth(120)
            swatch.clicked.connect(lambda _checked=False, k=key: self._pick(k))
            self._swatches[key] = swatch
            self._update_swatch(key)
            form.addRow(labels.get(key, key), swatch)

        layout.addLayout(form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.RestoreDefaults
            | QDialogButtonBox.StandardButton.Ok
            | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        buttons.button(QDialogButtonBox.StandardButton.RestoreDefaults).clicked.connect(
            self._restore_defaults
        )
        layout.addWidget(buttons)

    def _update_swatch(self, key: str) -> None:
        value = self._values.get(key, "ff000000")
        color = hex_to_qcolor(value)
        # Readable label colour against the swatch.
        fg = "#000000" if color.lightnessF() > 0.5 else "#ffffff"
        self._swatches[key].setText(f"#{value}")
        self._swatches[key].setStyleSheet(
            f"background-color: rgba({color.red()},{color.green()},"
            f"{color.blue()},{color.alpha() / 255:.3f}); color: {fg};"
        )

    def _pick(self, key: str) -> None:
        initial = hex_to_qcolor(self._values.get(key, "ff000000"))
        color = QColorDialog.getColor(
            initial,
            self,
            "Select colour",
            QColorDialog.ColorDialogOption.ShowAlphaChannel,
        )
        if color.isValid():
            self._values[key] = qcolor_to_hex(color)
            self._update_swatch(key)

    def _restore_defaults(self) -> None:
        for key in self._swatches:
            if key in DEFAULT_THEME_COLORS:
                self._values[key] = DEFAULT_THEME_COLORS[key]
                self._update_swatch(key)

    def apply(self) -> None:
        self._manifest.theme_colors = dict(self._values)

    def changed(self) -> bool:
        return self._values != self._manifest.theme_colors

    def result_colors(self) -> dict[str, str]:
        return dict(self._values)
