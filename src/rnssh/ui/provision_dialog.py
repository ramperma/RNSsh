"""Password prompt for key provisioning."""

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
from rnssh.models import Host


class ProvisionDialog(QDialog):
    def __init__(self, host: Host, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("provision.title", name=host.name))
        self._password = ""

        target = f"{host.user}@{host.hostname}:{host.port}"
        info = QLabel(t("provision.info", target=target))
        info.setWordWrap(True)

        self.password_edit = QLineEdit()
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)

        form = QFormLayout()
        form.addRow(t("provision.password"), self.password_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(info)
        layout.addLayout(form)
        layout.addWidget(buttons)
        self.resize(420, 160)

    def password(self) -> str:
        return self._password

    def _on_accept(self) -> None:
        pwd = self.password_edit.text()
        if not pwd:
            QMessageBox.warning(
                self,
                t("provision.password_required"),
                t("provision.password_msg"),
            )
            return
        self._password = pwd
        self.accept()
