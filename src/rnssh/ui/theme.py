"""Application visual theme (Qt Style Sheets).

PySide6 is a desktop toolkit — styling uses QSS (CSS-like), not Tailwind.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

_STYLE_PATH = Path(__file__).with_name("style.qss")

# Fallback if the QSS file is missing from the install.
_FALLBACK_QSS = """
QWidget {
    background-color: #f4f6f8;
    color: #1c2430;
    font-size: 13px;
}
"""


def load_stylesheet() -> str:
    if _STYLE_PATH.is_file():
        return _STYLE_PATH.read_text(encoding="utf-8")
    return _FALLBACK_QSS


def preferred_font() -> QFont:
    """Pick a clean UI font available on the system."""
    candidates = [
        "Inter",
        "IBM Plex Sans",
        "Source Sans 3",
        "Source Sans Pro",
        "Noto Sans",
        "Ubuntu",
        "Cantarell",
        "Segoe UI",
        "Helvetica Neue",
    ]
    available: set[str] = set()
    if QApplication.instance() is not None:
        try:
            available = set(QFontDatabase.families())
        except RuntimeError:
            available = set()
    for name in candidates:
        if not available or name in available:
            font = QFont(name, 10)
            font.setStyleHint(QFont.StyleHint.SansSerif)
            if not available:
                # No GUI yet — still request a sensible family; Qt resolves later.
                return font
            return font
    font = QFont()
    font.setPointSize(10)
    font.setStyleHint(QFont.StyleHint.SansSerif)
    return font


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    app.setFont(preferred_font())
    app.setStyleSheet(load_stylesheet())
