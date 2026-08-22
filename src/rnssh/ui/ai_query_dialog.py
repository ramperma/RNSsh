"""Dialog for text-based AI command consultations (uses the default provider)."""

from __future__ import annotations

from PySide6.QtCore import QThread, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from rnssh.ai import GEMINI, generate_command, load_ai_config
from rnssh.i18n import t
from rnssh.models import Host
from rnssh.tmux import paste_command
from rnssh.ui.status_overlay import StatusOverlay

_PROVIDER_LABELS = {GEMINI: "Gemini", "deepseek": "DeepSeek"}


class GenerateWorker(QThread):
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, request: str, parent=None) -> None:
        super().__init__(parent)
        self._request = request

    def run(self) -> None:
        try:
            provider = str(load_ai_config().get("default_provider", GEMINI))
            command = generate_command(provider, self._request)
            self.finished_ok.emit(command)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class PasteWorker(QThread):
    done = Signal()
    failed = Signal(str)

    def __init__(self, host: Host, session: str, command: str, parent=None) -> None:
        super().__init__(parent)
        self._host = host
        self._session = session
        self._command = command

    def run(self) -> None:
        try:
            paste_command(self._host, self._command, self._session)
            self.done.emit()
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class AIQueryDialog(QDialog):
    """Ask the default provider for a command; paste it into the host terminal."""

    status_message = Signal(str)

    def __init__(self, host: Host | None, parent=None) -> None:
        super().__init__(parent)
        self._host = host
        self._generate_worker: GenerateWorker | None = None
        self._paste_worker: PasteWorker | None = None
        self.setWindowTitle(t("ai_query.title"))
        self.setMinimumWidth(560)
        self._overlay = StatusOverlay(self)

        provider = str(load_ai_config().get("default_provider", GEMINI))
        provider_label = _PROVIDER_LABELS.get(provider, provider)
        self._info = QLabel(t("ai_query.info", provider=provider_label, name=host.name if host else "-"))
        self._info.setWordWrap(True)

        self._request = QPlainTextEdit()
        self._request.setPlaceholderText(t("ai_query.request"))
        self._request.setMaximumHeight(70)

        self._generate_btn = QPushButton(t("ai_query.generate"))
        self._generate_btn.setObjectName("primaryButton")
        self._generate_btn.clicked.connect(self._generate)

        request_row = QHBoxLayout()
        request_row.addWidget(self._request, 1)
        request_row.addWidget(self._generate_btn)

        self._result = QPlainTextEdit()
        self._result.setReadOnly(True)
        self._result.setPlaceholderText(t("ai_query.result_placeholder"))

        actions = QHBoxLayout()
        self._copy_btn = QPushButton(t("ai_query.copy"))
        self._copy_btn.clicked.connect(self._copy)
        self._paste_btn = QPushButton(t("ai_query.paste"))
        self._paste_btn.clicked.connect(self._paste)
        self._paste_btn.setEnabled(host is not None)
        if host is None:
            self._paste_btn.setToolTip(t("ai_query.paste_disabled"))
        actions.addWidget(self._copy_btn)
        actions.addWidget(self._paste_btn)
        actions.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addWidget(self._info)
        root.addLayout(request_row)
        root.addWidget(self._result)
        root.addLayout(actions)
        root.addWidget(buttons)

    def _current_command(self) -> str:
        return self._result.toPlainText().strip()

    def _generate(self) -> None:
        request = self._request.toPlainText().strip()
        if not request:
            QMessageBox.information(self, t("ai_query.title"), t("msg.ai_query_empty"))
            return
        self._generate_btn.setEnabled(False)
        self._overlay.show_state(t("overlay.generating"), "🤖")
        self.status_message.emit(t("status.ai_query_generating"))
        self._generate_worker = GenerateWorker(request, self)
        self._generate_worker.finished_ok.connect(self._on_generated)
        self._generate_worker.failed.connect(self._on_failed)
        self._generate_worker.start()

    def _on_generated(self, command: str) -> None:
        self._overlay.hide_state()
        self._generate_btn.setEnabled(True)
        self._result.setPlainText(command)
        self.status_message.emit(t("status.ai_query_done"))

    def _on_failed(self, message: str) -> None:
        self._overlay.hide_state()
        self._generate_btn.setEnabled(True)
        self._paste_btn.setEnabled(self._host is not None)
        QMessageBox.critical(self, t("ai_query.title"), message)
        self.status_message.emit(message)

    def _copy(self) -> None:
        command = self._current_command()
        if not command:
            return
        from PySide6.QtWidgets import QApplication

        QApplication.clipboard().setText(command)
        self.status_message.emit(t("status.ai_query_copied"))

    def _paste(self) -> None:
        command = self._current_command()
        if not command:
            QMessageBox.information(self, t("ai_query.title"), t("msg.ai_query_empty"))
            return
        host = self._host
        if host is None:
            QMessageBox.information(self, t("ai_query.title"), t("msg.ai_query_no_host"))
            return
        self._paste_btn.setEnabled(False)
        self._overlay.show_state(t("overlay.pasting"), "⌨️")
        self._paste_worker = PasteWorker(host, host.tmux_session, command, self)
        self._paste_worker.done.connect(self._on_pasted)
        self._paste_worker.failed.connect(self._on_failed)
        self._paste_worker.start()

    def _on_pasted(self) -> None:
        self._overlay.hide_state()
        self._paste_btn.setEnabled(True)
        name = self._host.name if self._host else "-"
        self.status_message.emit(t("status.ai_pasted", name=name))
        QMessageBox.information(
            self,
            t("ai_query.title"),
            t("msg.ai_query_pasted", name=name),
        )

    def reject(self) -> None:
        self._shutdown_workers()
        super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:
        self._shutdown_workers()
        super().closeEvent(event)

    def _shutdown_workers(self) -> None:
        self._overlay.hide_state()
        for worker in (self._generate_worker, self._paste_worker):
            if worker is not None and worker.isRunning():
                worker.wait(20000)
