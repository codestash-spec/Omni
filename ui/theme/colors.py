DEFAULT_PALETTE = {
    "BACKGROUND": "#0B0E11",
    "PANEL_BG": "#111418",
    "CARD_BG": "#1A1E23",
    "ACCENT_GREEN": "#00C46B",
    "ACCENT_RED": "#FF4E4E",
    "ACCENT_BLUE": "#3A86FF",
    "TEXT": "#E6EAF0",
    "MUTED": "#9AA0A6",
    "HIGHLIGHT": "#FFB703",
    "GRID": "#2D3239",
}

# Mutable globals used across the UI. ThemeManager will update these at runtime.
BACKGROUND = DEFAULT_PALETTE["BACKGROUND"]
PANEL_BG = DEFAULT_PALETTE["PANEL_BG"]
CARD_BG = DEFAULT_PALETTE["CARD_BG"]
ACCENT_GREEN = DEFAULT_PALETTE["ACCENT_GREEN"]
ACCENT_RED = DEFAULT_PALETTE["ACCENT_RED"]
ACCENT_BLUE = DEFAULT_PALETTE["ACCENT_BLUE"]
TEXT = DEFAULT_PALETTE["TEXT"]
MUTED = DEFAULT_PALETTE["MUTED"]
HIGHLIGHT = DEFAULT_PALETTE["HIGHLIGHT"]
GRID = DEFAULT_PALETTE["GRID"]


def apply_palette(palette: dict):
    """
    Update the shared color palette in-place so existing imports pick up the new theme.
    """
    global BACKGROUND, PANEL_BG, CARD_BG, ACCENT_GREEN, ACCENT_RED, ACCENT_BLUE, TEXT, MUTED, HIGHLIGHT, GRID
    BACKGROUND = palette.get("BACKGROUND", BACKGROUND)
    PANEL_BG = palette.get("PANEL_BG", PANEL_BG)
    CARD_BG = palette.get("CARD_BG", CARD_BG)
    ACCENT_GREEN = palette.get("ACCENT_GREEN", ACCENT_GREEN)
    ACCENT_RED = palette.get("ACCENT_RED", ACCENT_RED)
    ACCENT_BLUE = palette.get("ACCENT_BLUE", ACCENT_BLUE)
    TEXT = palette.get("TEXT", TEXT)
    MUTED = palette.get("MUTED", MUTED)
    HIGHLIGHT = palette.get("HIGHLIGHT", HIGHLIGHT)
    GRID = palette.get("GRID", GRID)
