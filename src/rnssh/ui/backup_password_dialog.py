"""Dialog to set or enter a backup password."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

from rnssh.i18n import t


class BackupPasswordDialog(QDialog):
    """Ask for a password; optionally require confirmation (create backup)."""

    def __init__(
        self,
        parent=None,
        *,
        confirm: bool = False,
        title: str | None = None,
        prompt: str | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title or t("settings.password_title"))
        self._confirm = confirm
        self._password = ""

        self._info = QLabel(prompt or t("settings.password_prompt"))
        self._info.setWordWrap(True)

        self._password_edit = QLineEdit()
        self._password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._confirm_edit = QLineEdit()
        self._confirm_edit.setEchoMode(QLineEdit.EchoMode.Password)

        form = QFormLayout()
        form.addRow(t("settings.password"), self._password_edit)
        if confirm:
            form.addRow(t("settings.password_confirm"), self._confirm_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addWidget(self._info)
        root.addLayout(form)
        root.addWidget(buttons)

        self._password_edit.setFocus()

    def password(self) -> str:
        return self._password

    def _on_accept(self) -> None:
        pwd = self._password_edit.text()
        if not pwd:
            QMessageBox.warning(
                self,
                t("settings.password_required_title"),
                t("settings.password_required"),
            )
            return
        if self._confirm and pwd != self._confirm_edit.text():
            QMessageBox.warning(
                self,
                t("settings.password_mismatch_title"),
                t("settings.password_mismatch"),
            )
            return
        if self._confirm and len(pwd) < 8:
            QMessageBox.warning(
                self,
                t("settings.password_weak_title"),
                t("settings.password_weak"),
            )
            return
        self._password = pwd
        self.accept()
