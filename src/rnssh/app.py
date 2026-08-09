"""QApplication entry point."""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from rnssh.i18n import set_language
from rnssh.paths import ensure_app_dirs
from rnssh.storage import load_config
from rnssh.ui.main_window import MainWindow
from rnssh.ui.theme import apply_theme

_ICON_PATH = Path(__file__).resolve().parent / "ui" / "assets" / "app_icon.png"


def main(argv: list[str] | None = None) -> int:
    ensure_app_dirs()
    config = load_config()
    set_language(config.language)
    args = argv if argv is not None else sys.argv
    app = QApplication(args)
    app.setApplicationName("RNSsh")
    app.setOrganizationName("Ramnet Informatica SLU")
    if _ICON_PATH.is_file():
        app.setWindowIcon(QIcon(str(_ICON_PATH)))
    apply_theme(app)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
