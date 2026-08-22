"""Voice trigger listener and voice-to-command worker."""

from __future__ import annotations

import time

from PySide6.QtCore import QThread, Signal

from rnssh.ai import GEMINI, generate_command, transcribe_audio
from rnssh.models import Host
from rnssh.ssh_cmd import shell_quote
from rnssh.tmux import _connect, exec_voice_setup, paste_command, voice_trigger_path

_RECONNECT_DELAY = 5


class VoiceTriggerListener(QThread):
    """Watch the remote trigger file written by the tmux status-bar button."""

    triggered = Signal()
    error = Signal(str)

    def __init__(self, host: Host, session: str, token: str, parent=None) -> None:
        super().__init__(parent)
        self._host = host
        self._session = session
        self._token = token
        self._stop_flag = False
        self._client = None
        self._setup_done = False

    def stop(self) -> None:
        self._stop_flag = True
        client = self._client
        if client is not None:
            try:
                client.close()
            except Exception:  # noqa: BLE001 - best effort interrupt
                pass
        self.wait(3500)

    def run(self) -> None:
        path = voice_trigger_path(self._token)
        while not self._stop_flag:
            client = None
            try:
                client = _connect(self._host)
                self._client = client
                if not self._setup_done:
                    exec_voice_setup(client, self._session, self._token)
                    self._setup_done = True
                _stdin, stdout, _stderr = client.exec_command(f"tail -F -n 0 {shell_quote(path)}")
                for line in stdout:
                    if self._stop_flag:
                        break
                    if line.strip():
                        self.triggered.emit()
            except Exception as exc:  # noqa: BLE001 - network errors are transient
                if not self._stop_flag:
                    self.error.emit(str(exc))
            finally:
                if client is not None:
                    try:
                        client.close()
                    except Exception:  # noqa: BLE001
                        pass
                self._client = None
            if self._stop_flag:
                break
            time.sleep(_RECONNECT_DELAY)


class VoiceCommandWorker(QThread):
    """Voice pipeline: Gemini transcribes AND generates the command, then paste."""

    finished_ok = Signal(str, str)  # transcription, command
    failed = Signal(str)

    def __init__(self, host: Host, session: str, wav: bytes, parent=None) -> None:
        super().__init__(parent)
        self._host = host
        self._session = session
        self._wav = wav

    def run(self) -> None:
        try:
            transcription = transcribe_audio(self._wav)
            command = generate_command(GEMINI, transcription)
            paste_command(self._host, command, self._session)
            self.finished_ok.emit(transcription, command)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
