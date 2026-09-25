"""Tests for theme loading."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from rnssh.ui.main_window import _header_logo_pixmap
from rnssh.ui.theme import load_stylesheet, preferred_font


def test_stylesheet_loads() -> None:
    qss = load_stylesheet()
    assert "primaryButton" in qss
    assert "actionBar" in qss
    assert "hostsCard" in qss
    assert "#0f766e" in qss


def test_preferred_font_without_app() -> None:
    font = preferred_font()
    assert font.pointSize() >= 9
    assert font.family()


def test_header_logo_is_visible_on_dark_header() -> None:
    if QApplication.instance() is None:
        QApplication(["rnssh-tests"])
    pix = _header_logo_pixmap(40)
    assert pix is not None
    assert not pix.isNull()
    assert pix.height() == 40
    image = pix.toImage()
    opaque = None
    for y in range(0, image.height(), 2):
        for x in range(0, image.width(), 2):
            sample = image.pixelColor(x, y)
            if sample.alpha() > 200:
                opaque = sample
                break
        if opaque is not None:
            break
    assert opaque is not None
    assert opaque.lightness() > 180
