"""Tests for theme loading."""

from __future__ import annotations

from rnssh.ui.theme import load_stylesheet, preferred_font


def test_stylesheet_loads() -> None:
    qss = load_stylesheet()
    assert "primaryButton" in qss
    assert "#0f766e" in qss


def test_preferred_font_without_app() -> None:
    font = preferred_font()
    assert font.pointSize() >= 9
    assert font.family()
