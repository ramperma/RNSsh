"""Dialog to configure the AI provider, API key, and model."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QToolButton,
    QVBoxLayout,
)

from rnssh.ai import GEMINI, MODEL_CHOICES, ai_storage_mode, list_models, load_ai_config, save_ai_config
from rnssh.i18n import t

_PROVIDER_LABELS = {GEMINI: "Gemini", "deepseek": "DeepSeek"}


class ModelsWorker(QThread):
    """Fetch the live model list for a provider without blocking the UI."""

    finished_ok = Signal(list)
    failed = Signal(str)

    def __init__(self, provider: str, parent=None) -> None:
        super().__init__(parent)
        self._provider = provider

    def run(self) -> None:
        try:
            models = list_models(self._provider)
            if not models:
                raise ValueError("no models returned")
            self.finished_ok.emit(models)
        except Exception as exc:  # noqa: BLE001 - surface any failure to the dialog
            self.failed.emit(str(exc))


class AISettingsDialog(QDialog):
    """Edit per-provider API keys/models and pick the default provider."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._cfg = load_ai_config()
        self._models_worker: ModelsWorker | None = None
        self._load_serial = 0
        self.setWindowTitle(t("ai_settings.title"))
        self.setMinimumWidth(460)

        self._provider = QComboBox()
        for code, label in _PROVIDER_LABELS.items():
            self._provider.addItem(label, code)
        self._provider.currentIndexChanged.connect(self._on_provider_changed)

        self._key_edit = QLineEdit()
        self._key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._key_edit.setPlaceholderText(t("ai_settings.api_key_placeholder"))
        self._key_edit.editingFinished.connect(self._load_models)

        self._show_key = QCheckBox(t("ai_settings.show_key"))
        self._show_key.toggled.connect(
            lambda checked: self._key_edit.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
        )

        key_row = QHBoxLayout()
        key_row.addWidget(self._key_edit, 1)
        key_row.addWidget(self._show_key)

        self._model = QComboBox()
        self._model.setEditable(True)
        self._model.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)

        self._refresh_btn = QToolButton()
        self._refresh_btn.setText("⟳")
        self._refresh_btn.setToolTip(t("ai_settings.models_refresh"))
        self._refresh_btn.clicked.connect(self._load_models)

        model_row = QHBoxLayout()
        model_row.addWidget(self._model, 1)
        model_row.addWidget(self._refresh_btn)

        self._models_status = QLabel()
        self._models_status.setWordWrap(True)

        self._default = QCheckBox(t("ai_settings.default_provider"))

        self._storage_note = QLabel()
        self._storage_note.setWordWrap(True)
        self._storage_note.setObjectName("settingsHelp")
        self._refresh_storage_note()

        form = QFormLayout()
        form.addRow(t("ai_settings.provider"), self._provider)
        form.addRow(t("ai_settings.api_key"), key_row)
        form.addRow(t("ai_settings.model"), model_row)
        form.addRow("", self._models_status)
        form.addRow("", self._default)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_save)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addWidget(QLabel(t("ai_settings.help")))
        root.addWidget(self._storage_note)
        root.addLayout(form)
        root.addWidget(buttons)

        self._provider.setCurrentIndex(0)
        self._on_provider_changed()

    def _current_provider(self) -> str:
        return str(self._provider.currentData())

    def _on_provider_changed(self) -> None:
        provider = self._current_provider()
        entry = self._cfg.get(provider) or {}
        self._key_edit.setText(str(entry.get("api_key") or ""))
        self._populate_models(MODEL_CHOICES.get(provider, []))
        model = str(entry.get("model") or "")
        index = self._model.findText(model)
        if index >= 0:
            self._model.setCurrentIndex(index)
        else:
            self._model.setEditText(model)
        self._default.setChecked(self._cfg.get("default_provider") == provider)
        self._load_models()

    def _populate_models(self, models: list[str]) -> None:
        current = self._model.currentText().strip()
        self._model.clear()
        for model in models:
            self._model.addItem(model)
        index = self._model.findText(current)
        if index >= 0:
            self._model.setCurrentIndex(index)
        elif current:
            self._model.setEditText(current)

    def _load_models(self) -> None:
        provider = self._current_provider()
        key = self._key_edit.text().strip()
        if not key:
            self._populate_models(MODEL_CHOICES.get(provider, []))
            self._models_status.setText(t("ai_settings.models_need_key"))
            return
        self._load_serial += 1
        serial = self._load_serial
        self._models_status.setText(t("ai_settings.models_loading"))
        self._refresh_btn.setEnabled(False)
        self._models_worker = ModelsWorker(provider, self)
        self._models_worker.finished_ok.connect(
            lambda models, s=serial: self._on_models_loaded(models, s)
        )
        self._models_worker.failed.connect(
            lambda _msg, s=serial: self._on_models_failed(s)
        )
        self._models_worker.start()

    def _on_models_loaded(self, models: list, serial: int) -> None:
        if serial != self._load_serial:
            return
        self._refresh_btn.setEnabled(True)
        current = self._model.currentText().strip()
        self._populate_models(models)
        if current and current not in models:
            self._model.setCurrentIndex(0)
            self._models_status.setText(t("ai_settings.models_stale", model=current))
        else:
            self._models_status.setText(t("ai_settings.models_loaded", count=len(models)))

    def _on_models_failed(self, serial: int) -> None:
        if serial != self._load_serial:
            return
        self._refresh_btn.setEnabled(True)
        current = self._model.currentText().strip()
        self._populate_models(MODEL_CHOICES.get(self._current_provider(), []))
        if current and current not in [self._model.itemText(i) for i in range(self._model.count())]:
            self._model.setCurrentIndex(0)
            self._models_status.setText(t("ai_settings.models_stale", model=current))
        else:
            self._models_status.setText(t("ai_settings.models_offline"))

    def _refresh_storage_note(self) -> None:
        if ai_storage_mode() == "keyring":
            self._storage_note.setText(t("ai_settings.storage_keyring"))
        else:
            self._storage_note.setText(t("ai_settings.storage_file"))

    def _persist_current(self) -> None:
        """Save whatever is typed, so closing the dialog never loses the keys."""
        provider = self._current_provider()
        model = self._model.currentText().strip()
        if not model:
            return
        self._cfg[provider] = {
            "api_key": self._key_edit.text().strip(),
            "model": model,
        }
        if self._default.isChecked():
            self._cfg["default_provider"] = provider
        save_ai_config(self._cfg)
        self._refresh_storage_note()

    def _on_save(self) -> None:
        self._persist_current()
        self._shutdown_worker()
        self.accept()

    def reject(self) -> None:
        self._persist_current()
        self._shutdown_worker()
        super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._persist_current()
        self._shutdown_worker()
        super().closeEvent(event)

    def _shutdown_worker(self) -> None:
        """Let an in-flight model fetch finish before the dialog is destroyed."""
        worker = self._models_worker
        if worker is not None and worker.isRunning():
            worker.wait(20000)
