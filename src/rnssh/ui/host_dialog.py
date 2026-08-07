"""Create / edit host dialog."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from rnssh.i18n import t
from rnssh.models import Host


class HostDialog(QDialog):
    def __init__(self, parent=None, host: Host | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("host.edit_title") if host else t("host.add_title"))
        self._host = host
        self._result: Host | None = None

        self.name_edit = QLineEdit()
        self.hostname_edit = QLineEdit()
        self.user_edit = QLineEdit("root")
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(22)
        self.jump_edit = QLineEdit()
        self.jump_edit.setPlaceholderText(t("host.jump_placeholder"))
        self.tmux_edit = QLineEdit("rnssh")
        self.key_edit = QLineEdit()
        self.key_edit.setPlaceholderText(t("host.key_placeholder"))
        self.notes_edit = QTextEdit()
        self.notes_edit.setAcceptRichText(False)
        self.notes_edit.setMaximumHeight(80)
        self.agent_check = QCheckBox(t("host.agent"))

        form = QFormLayout()
        form.addRow(t("host.name"), self.name_edit)
        form.addRow(t("host.hostname"), self.hostname_edit)
        form.addRow(t("host.user"), self.user_edit)
        form.addRow(t("host.port"), self.port_spin)
        form.addRow(t("host.jump"), self.jump_edit)
        form.addRow(t("host.tmux"), self.tmux_edit)
        form.addRow(t("host.key_name"), self.key_edit)
        form.addRow(t("host.notes"), self.notes_edit)
        form.addRow("", self.agent_check)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

        if host:
            self.name_edit.setText(host.name)
            self.hostname_edit.setText(host.hostname)
            self.user_edit.setText(host.user)
            self.port_spin.setValue(host.port)
            self.jump_edit.setText(host.jump_host or "")
            self.tmux_edit.setText(host.tmux_session)
            self.key_edit.setText(host.key_name or "")
            self.notes_edit.setPlainText(host.notes)
            self.agent_check.setChecked(host.agent_forwarding)

        self.resize(420, 360)

    def result_host(self) -> Host | None:
        return self._result

    def _on_accept(self) -> None:
        name = self.name_edit.text().strip()
        hostname = self.hostname_edit.text().strip()
        user = self.user_edit.text().strip()
        if not name or not hostname or not user:
            QMessageBox.warning(self, t("host.missing_title"), t("host.missing_msg"))
            return
        jump = self.jump_edit.text().strip() or None
        key_name = self.key_edit.text().strip() or None
        tmux = self.tmux_edit.text().strip() or "rnssh"

        if self._host:
            host = self._host
            host.name = name
            host.hostname = hostname
            host.user = user
            host.port = self.port_spin.value()
            host.jump_host = jump
            host.tmux_session = tmux
            host.key_name = key_name
            host.notes = self.notes_edit.toPlainText().strip()
            host.agent_forwarding = self.agent_check.isChecked()
        else:
            host = Host(
                name=name,
                hostname=hostname,
                user=user,
                port=self.port_spin.value(),
                jump_host=jump,
                tmux_session=tmux,
                key_name=key_name,
                notes=self.notes_edit.toPlainText().strip(),
                agent_forwarding=self.agent_check.isChecked(),
            )
        self._result = host
        self.accept()
