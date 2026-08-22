"""Tests for the tmux voice button setup and paste helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from rnssh.models import Host
from rnssh.tmux import (
    TmuxError,
    build_voice_setup_script,
    exec_voice_setup,
    paste_command,
    voice_trigger_path,
)


def test_voice_trigger_path() -> None:
    path = voice_trigger_path("abc123")
    assert path.startswith("/tmp/rnssh-voice-abc123")
    assert ".click" not in path


def test_build_voice_setup_script() -> None:
    script = build_voice_setup_script("work", "tok12")
    assert "touch '/tmp/rnssh-voice-tok12'" in script
    assert "range=right" in script
    assert "MouseDown1StatusRight" in script
    assert "bind-key -T root" in script
    assert "rnssh-voice-tok12.click" in script
    assert "printf 'v\\n' >> '/tmp/rnssh-voice-tok12'" in script
    assert "mouse on" in script
    assert "bind-key -t" not in script


def test_exec_voice_setup() -> None:
    client = MagicMock()
    stdout = MagicMock()
    stderr = MagicMock()
    stderr.read.return_value = b""
    stdout.channel.recv_exit_status.return_value = 0
    client.exec_command.return_value = (MagicMock(), stdout, stderr)

    exec_voice_setup(client, "work", "tok")

    cmd = client.exec_command.call_args[0][0]
    assert "cat > '/tmp/rnssh-voice-tok.click'" in cmd
    assert "MouseDown1StatusRight" in cmd


def test_exec_voice_setup_failure() -> None:
    client = MagicMock()
    stdout = MagicMock()
    stderr = MagicMock()
    stderr.read.return_value = b"permission denied"
    stdout.channel.recv_exit_status.return_value = 1
    client.exec_command.return_value = (MagicMock(), stdout, stderr)

    with pytest.raises(TmuxError, match="permission denied"):
        exec_voice_setup(client, "work", "tok")


def test_paste_command_no_enter() -> None:
    host = Host(name="box", hostname="h.example", user="u", key_name="default")
    client = MagicMock()
    stdout = MagicMock()
    stderr = MagicMock()
    stdout.channel.recv_exit_status.return_value = 0
    client.exec_command.return_value = (MagicMock(), stdout, stderr)

    with patch("rnssh.tmux._connect", return_value=client):
        paste_command(host, "apt update\napt upgrade", "work")

    cmd = client.exec_command.call_args[0][0]
    assert cmd == "tmux send-keys -t 'work' -l 'apt update && apt upgrade'"
    assert "C-m" not in cmd
    client.close.assert_called_once()


def test_paste_command_requires_command() -> None:
    host = Host(name="box", hostname="h.example", user="u")
    with pytest.raises(TmuxError, match="required"):
        paste_command(host, "   ")
