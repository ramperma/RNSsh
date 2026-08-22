"""Microphone recording for the voice assistant (QtMultimedia, arecord fallback)."""

from __future__ import annotations

import shutil
import struct
import subprocess
import threading

from PySide6.QtCore import QObject, QTimer, Signal

try:
    from PySide6.QtMultimedia import QAudio, QAudioFormat, QAudioSource, QMediaDevices

    QT_MULTIMEDIA = True
except ImportError:  # pragma: no cover - unusual, QtMultimedia ships with PySide6
    QT_MULTIMEDIA = False

_MAX_SECONDS = 60


def build_wav(pcm: bytes, *, rate: int = 16000, channels: int = 1, bits: int = 16) -> bytes:
    """Wrap raw PCM into a canonical RIFF/WAVE container."""
    block_align = channels * bits // 8
    byte_rate = rate * block_align
    header = (
        b"RIFF"
        + struct.pack("<I", 36 + len(pcm))
        + b"WAVE"
        + b"fmt "
        + struct.pack("<IHHIIHH", 16, 1, channels, rate, byte_rate, block_align, bits)
        + b"data"
        + struct.pack("<I", len(pcm))
    )
    return header + pcm


class AudioRecorder(QObject):
    """Toggle-recording helper. Emits ``finished`` once with WAV bytes."""

    finished = Signal(bytes)
    failed = Signal(str)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._recording = False
        self._source: QAudioSource | None = None
        self._io = None
        self._buf = bytearray()
        self._rate = 16000
        self._channels = 1
        self._proc: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._max_timer = QTimer(self)
        self._max_timer.setSingleShot(True)
        self._max_timer.timeout.connect(self.stop)

    def is_recording(self) -> bool:
        return self._recording

    def start(self) -> None:
        if self._recording:
            return
        self._recording = True
        self._buf.clear()
        self._max_timer.start(_MAX_SECONDS * 1000)
        if QT_MULTIMEDIA and self._start_qt():
            return
        self._start_arecord()

    def stop(self) -> None:
        if not self._recording:
            return
        self._recording = False
        self._max_timer.stop()
        if self._source is not None:
            self._source.stop()
            self._source = None
            try:
                if self._io is not None:
                    self._buf.extend(bytes(self._io.readAll()))
            except Exception:  # noqa: BLE001 - best effort tail flush
                pass
            self._io = None
            self.finished.emit(build_wav(bytes(self._buf), rate=self._rate, channels=self._channels))
        elif self._proc is not None:
            try:
                self._proc.terminate()
            except OSError:
                pass

    def _start_qt(self) -> bool:
        device = QMediaDevices.defaultAudioInput()
        if device is None or device.isNull():
            return False
        for rate, channels in ((16000, 1), (44100, 2)):
            fmt = QAudioFormat()
            fmt.setSampleRate(rate)
            fmt.setChannelCount(channels)
            fmt.setSampleFormat(QAudioFormat.SampleFormat.Int16)
            if not device.isFormatSupported(fmt):
                continue
            source = QAudioSource(device, fmt)
            io = source.start()
            if io is None or source.error() != QAudio.Error.NoError:
                continue
            self._source = source
            self._io = io
            self._rate = rate
            self._channels = channels
            io.readyRead.connect(self._on_ready_read)
            return True
        return False

    def _on_ready_read(self) -> None:
        try:
            data = bytes(self._io.readAll())
        except Exception:  # noqa: BLE001
            data = b""
        if data:
            self._buf.extend(data)

    def _start_arecord(self) -> None:
        self._thread = threading.Thread(target=self._record_arecord, daemon=True)
        self._thread.start()

    def _record_arecord(self) -> None:
        exe = shutil.which("arecord")
        if not exe:
            if self._recording:
                self._recording = False
                self._max_timer.stop()
                self.failed.emit("Install alsa-utils (arecord) to enable microphone input")
            return
        try:
            self._proc = subprocess.Popen(  # noqa: S603 - local user command
                [exe, "-q", "-f", "S16_LE", "-r", "44100", "-c", "2",
                 "-d", str(_MAX_SECONDS), "-t", "wav", "-"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )
            out, _err = self._proc.communicate()
        except OSError as exc:
            if self._recording:
                self._recording = False
                self._max_timer.stop()
                self.failed.emit(str(exc))
            return
        finally:
            self._proc = None
        self._recording = False
        self._max_timer.stop()
        if out:
            self.finished.emit(out)
