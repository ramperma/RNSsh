"""Settings tab: backup and restore of connections."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from rnssh.backup import (
    BackupError,
    create_backup,
    default_backup_filename,
    read_backup_info,
    restore_backup,
)
from rnssh.i18n import t
from rnssh.models import AppConfig
from rnssh.paths import config_dir, config_file, keys_dir
from rnssh.ui.backup_password_dialog import BackupPasswordDialog


class SettingsPage(QWidget):
    """Configuration page with backup / restore controls."""

    restored = Signal()
    status_message = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._config: AppConfig | None = None
        self._build_ui()

    def set_config(self, config: AppConfig) -> None:
        self._config = config
        self._refresh_summary()

    def retranslate(self) -> None:
        self._section_title.setText(t("settings.backup_title"))
        self._section_help.setText(t("settings.backup_help"))
        self._include_keys.setText(t("settings.include_keys"))
        self._backup_btn.setText(t("settings.backup_export"))
        self._restore_btn.setText(t("settings.backup_restore"))
        self._paths_title.setText(t("settings.paths_title"))
        self._refresh_summary()

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        card = QFrame()
        card.setObjectName("settingsCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(20, 18, 20, 18)
        card_layout.setSpacing(12)

        self._section_title = QLabel()
        self._section_title.setObjectName("settingsSectionTitle")
        self._section_help = QLabel()
        self._section_help.setObjectName("settingsHelp")
        self._section_help.setWordWrap(True)

        self._summary = QLabel()
        self._summary.setObjectName("settingsSummary")
        self._summary.setWordWrap(True)

        self._include_keys = QCheckBox()
        self._include_keys.setChecked(True)
        self._include_keys.setObjectName("settingsCheck")

        buttons = QHBoxLayout()
        buttons.setSpacing(10)
        self._backup_btn = QPushButton()
        self._backup_btn.setObjectName("primaryButton")
        self._backup_btn.clicked.connect(self._export_backup)
        self._restore_btn = QPushButton()
        self._restore_btn.clicked.connect(self._import_backup)
        buttons.addWidget(self._backup_btn)
        buttons.addWidget(self._restore_btn)
        buttons.addStretch(1)

        card_layout.addWidget(self._section_title)
        card_layout.addWidget(self._section_help)
        card_layout.addWidget(self._summary)
        card_layout.addWidget(self._include_keys)
        card_layout.addLayout(buttons)

        paths_card = QFrame()
        paths_card.setObjectName("settingsCard")
        paths_layout = QVBoxLayout(paths_card)
        paths_layout.setContentsMargins(20, 18, 20, 18)
        paths_layout.setSpacing(8)
        self._paths_title = QLabel()
        self._paths_title.setObjectName("settingsSectionTitle")
        self._paths_body = QLabel()
        self._paths_body.setObjectName("settingsPaths")
        self._paths_body.setWordWrap(True)
        self._paths_body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        paths_layout.addWidget(self._paths_title)
        paths_layout.addWidget(self._paths_body)

        root.addWidget(card)
        root.addWidget(paths_card)
        root.addStretch(1)

    def _refresh_summary(self) -> None:
        hosts = len(self._config.hosts) if self._config else 0
        keys = 0
        keys_path = keys_dir()
        if keys_path.is_dir():
            keys = sum(
                1 for p in keys_path.iterdir() if p.is_file() and not p.name.startswith(".")
            )
        self._summary.setText(t("settings.summary", hosts=hosts, keys=keys))
        self._paths_body.setText(
            t(
                "settings.paths_body",
                config=str(config_file()),
                keys=str(keys_dir()),
                data=str(config_dir()),
            )
        )

    def _ask_password(self, *, confirm: bool) -> str | None:
        dlg = BackupPasswordDialog(
            self,
            confirm=confirm,
            title=t("settings.password_title"),
            prompt=(
                t("settings.password_prompt_create")
                if confirm
                else t("settings.password_prompt_restore")
            ),
        )
        if dlg.exec() != BackupPasswordDialog.DialogCode.Accepted:
            return None
        return dlg.password()

    def _export_backup(self) -> None:
        suggested = str(Path.home() / default_backup_filename())
        path, _ = QFileDialog.getSaveFileName(
            self,
            t("settings.backup_export_title"),
            suggested,
            t("settings.backup_filter"),
        )
        if not path:
            return

        include_sensitive = self._include_keys.isChecked()
        password: str | None = None
        has_key_files = False
        keys_path = keys_dir()
        if keys_path.is_dir():
            has_key_files = any(
                p.is_file() and not p.name.startswith(".") for p in keys_path.iterdir()
            )
        has_secrets = bool(
            self._config
            and any((h.password or "").strip() for h in self._config.hosts)
        )
        if include_sensitive and (has_key_files or has_secrets):
            password = self._ask_password(confirm=True)
            if password is None:
                return

        try:
            info = create_backup(
                Path(path),
                include_keys=include_sensitive,
                include_secrets=include_sensitive,
                password=password,
                config=self._config,
            )
        except BackupError as exc:
            QMessageBox.critical(self, t("settings.backup_failed"), str(exc))
            self.status_message.emit(t("settings.backup_failed_status", message=str(exc)))
            return

        QMessageBox.information(
            self,
            t("settings.backup_done_title"),
            t(
                "settings.backup_done",
                path=str(info.path),
                hosts=info.host_count,
                keys=info.key_count,
                secrets=info.secret_count,
            ),
        )
        self.status_message.emit(
            t("settings.backup_done_status", path=str(info.path), hosts=info.host_count)
        )

    def _import_backup(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            t("settings.backup_restore_title"),
            str(Path.home()),
            t("settings.backup_filter"),
        )
        if not path:
            return
        try:
            info = read_backup_info(Path(path))
        except BackupError as exc:
            QMessageBox.critical(self, t("settings.restore_failed"), str(exc))
            return

        encrypted_note = (
            t("settings.restore_encrypted_note")
            if (info.keys_encrypted or info.secrets_encrypted)
            else ""
        )
        detail = t(
            "settings.restore_confirm",
            path=str(info.path),
            hosts=info.host_count,
            keys=info.key_count,
            secrets=info.secret_count,
            created=info.created_at,
            encrypted_note=encrypted_note,
        )
        reply = QMessageBox.question(
            self,
            t("settings.restore_confirm_title"),
            detail,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        restore_sensitive = self._include_keys.isChecked()
        password: str | None = None
        needs_password = restore_sensitive and (
            info.keys_encrypted or info.secrets_encrypted
        )
        if needs_password:
            password = self._ask_password(confirm=False)
            if password is None:
                return

        try:
            result = restore_backup(
                Path(path),
                restore_keys=restore_sensitive,
                restore_secrets=restore_sensitive,
                password=password,
            )
        except BackupError as exc:
            QMessageBox.critical(self, t("settings.restore_failed"), str(exc))
            self.status_message.emit(t("settings.restore_failed_status", message=str(exc)))
            return

        QMessageBox.information(
            self,
            t("settings.restore_done_title"),
            t(
                "settings.restore_done",
                hosts=result.host_count,
                keys=result.key_count,
                secrets=result.secret_count,
            ),
        )
        self.status_message.emit(
            t(
                "settings.restore_done_status",
                hosts=result.host_count,
                keys=result.key_count,
                secrets=result.secret_count,
            )
        )
        self.restored.emit()
