from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSettings

from ui.theme import colors


class ThemeManager:
    """
    Lightweight theme loader that swaps QSS skins at runtime and updates the shared palette.
    """

    def __init__(self, settings: QSettings | None = None):
        self.settings = settings or QSettings("OmniFlow", "TerminalUI")
        self.themes_dir = Path(__file__).parent / "themes"
        self.default_theme = "default"
        self._palettes = {
            "default": colors.DEFAULT_PALETTE,
            "bloomberg": {
                "BACKGROUND": "#0B0F14",
                "PANEL_BG": "#11161C",
                "CARD_BG": "#1A1F26",
                "ACCENT_GREEN": "#27AE60",
                "ACCENT_RED": "#C04F4F",
                "ACCENT_BLUE": "#56CCF2",
                "TEXT": "#D6DEE6",
                "MUTED": "#9BA7B4",
                "HIGHLIGHT": "#F2C94C",
                "GRID": "#1F262F",
            },
            "refinitiv": {
                "BACKGROUND": "#0E0E0E",
                "PANEL_BG": "#151515",
                "CARD_BG": "#1C1C1C",
                "ACCENT_GREEN": "#2ECC71",
                "ACCENT_RED": "#D16666",
                "ACCENT_BLUE": "#4DA3FF",
                "TEXT": "#E0E0E0",
                "MUTED": "#A0A0A0",
                "HIGHLIGHT": "#D4AF37",
                "GRID": "#242424",
            },
        }

    def available(self) -> list[str]:
        return list(self._palettes.keys())

    def apply_saved(self, widget) -> str:
        saved = str(self.settings.value("theme", self.default_theme) or self.default_theme).lower()
        return self.apply(widget, saved)

    def apply(self, widget, theme_name: str) -> str:
        theme = theme_name.lower()
        if theme not in self._palettes:
            theme = self.default_theme
        colors.apply_palette(self._palettes.get(theme, colors.DEFAULT_PALETTE))
        stylesheet = self._load_qss(theme) or self._load_qss(self.default_theme) or ""
        if widget:
            widget.setStyleSheet(stylesheet)
        self.settings.setValue("theme", theme)
        return theme

    def _load_qss(self, theme: str) -> str | None:
        path = self.themes_dir / f"{theme}.qss"
        if not path.exists():
            return None
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return None

