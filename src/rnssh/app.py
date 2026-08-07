"""QApplication entry point."""

from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from rnssh.i18n import set_language
from rnssh.paths import ensure_app_dirs
from rnssh.storage import load_config
from rnssh.ui.main_window import MainWindow
from rnssh.ui.theme import apply_theme


def main(argv: list[str] | None = None) -> int:
    ensure_app_dirs()
    config = load_config()
    set_language(config.language)
    args = argv if argv is not None else sys.argv
    app = QApplication(args)
    app.setApplicationName("RNSsh")
    app.setOrganizationName("RNSsh")
    apply_theme(app)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
