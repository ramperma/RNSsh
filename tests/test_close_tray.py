"""Close-to-tray behavior and the simpler host toolbar."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QRect, QSize
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QApplication

from rnssh.i18n import set_language, t
from rnssh.models import AppConfig, Host
from rnssh.storage import save_config
from rnssh.ui.main_window import MainWindow, initial_window_position
import rnssh.paths as paths


@pytest.fixture(scope="module")
def qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication(["rnssh-tests"])
    return app


@pytest.fixture()
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    paths.ensure_app_dirs()
    cfg = AppConfig()
    cfg.upsert_host(Host(name="vps", hostname="1.2.3.4", group="Lab"))
    save_config(cfg)
    return tmp_path


def test_close_minimize_hides_window(
    qapp: QApplication, isolated_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = MainWindow()
    window.show()
    qapp.processEvents()
    monkeypatch.setattr(window, "_can_use_tray", lambda: True)
    monkeypatch.setattr(window, "_ask_close_choice", lambda: "minimize")
    quits: list[bool] = []
    monkeypatch.setattr(QApplication, "quit", lambda self: quits.append(True))

    event = QCloseEvent()
    window.closeEvent(event)

    assert not event.isAccepted()
    assert not window.isVisible()
    assert not window._closing
    assert quits == []
    window._quitting = True
    window.close()


def test_close_quit_shuts_down(
    qapp: QApplication, isolated_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = MainWindow()
    monkeypatch.setattr(window, "_can_use_tray", lambda: True)
    monkeypatch.setattr(window, "_ask_close_choice", lambda: "quit")
    quits: list[bool] = []
    monkeypatch.setattr(QApplication, "quit", lambda self: quits.append(True))

    event = QCloseEvent()
    window.closeEvent(event)

    assert event.isAccepted()
    assert window._closing
    assert quits == [True]


def test_close_cancel_keeps_window(
    qapp: QApplication, isolated_config: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    window = MainWindow()
    window.show()
    monkeypatch.setattr(window, "_can_use_tray", lambda: True)
    monkeypatch.setattr(window, "_ask_close_choice", lambda: "cancel")

    event = QCloseEvent()
    window.closeEvent(event)

    assert not event.isAccepted()
    assert window.isVisible()
    assert not window._closing
    window._quitting = True
    window.deleteLater()


def test_close_buttons_fit_their_labels(qapp: QApplication, isolated_config: Path) -> None:
    window = MainWindow()
    try:
        for language in ("en", "es"):
            set_language(language)
            box = window._ask_close_box()
            minimize = next(b for b in box.buttons() if b.text() == t("tray.minimize"))
            needed = minimize.fontMetrics().horizontalAdvance(minimize.text())
            assert minimize.minimumWidth() >= needed + 32
            box.close()
    finally:
        set_language("en")
        window._quitting = True
        window.close()


def test_search_filters_hosts(qapp: QApplication, isolated_config: Path) -> None:
    window = MainWindow()
    try:
        assert window.table.topLevelItemCount() >= 1
        window._search.setText("missing-host")
        qapp.processEvents()
        assert window._stack.currentWidget() is window._filter_empty
        window._search.setText("vps")
        qapp.processEvents()
        assert window._stack.currentWidget() is window.table
    finally:
        window._quitting = True
        window.close()


def test_window_is_centered_when_it_fits() -> None:
    pos = initial_window_position(QRect(0, 0, 1920, 1080), QSize(920, 560))
    assert pos == QPoint((1920 - 920) // 2, (1080 - 560) // 2)


def test_window_stays_current_size_when_it_does_not_fit() -> None:
    pos = initial_window_position(QRect(100, 40, 800, 500), QSize(920, 560))
    assert pos == QPoint(100, 40)


def test_window_show_keeps_default_size(qapp: QApplication, isolated_config: Path) -> None:
    window = MainWindow()
    try:
        window.show()
        qapp.processEvents()
        assert window.size().width() == 920
        assert window.size().height() == 560
        assert window._placed_on_screen
    finally:
        window._quitting = True
        window.close()
