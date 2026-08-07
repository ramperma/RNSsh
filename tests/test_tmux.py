"""Tests for remote tmux helpers."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from rnssh.models import Host
from rnssh.tmux import TmuxError, attach_command, kill_command, kill_session


def test_attach_command() -> None:
    assert attach_command("work") == "tmux new-session -A -s 'work'"


def test_kill_command() -> None:
    assert kill_command("rnssh") == "tmux kill-session -t 'rnssh'"
    assert "\"'\"" in kill_command("a'b")


def test_kill_session_success() -> None:
    host = Host(name="box", hostname="h.example", user="u", key_name="default")
    client = MagicMock()
    stdout = MagicMock()
    stderr = MagicMock()
    stdout.read.return_value = b""
    stderr.read.return_value = b""
    stdout.channel.recv_exit_status.return_value = 0
    client.exec_command.return_value = (MagicMock(), stdout, stderr)

    with (
        patch("rnssh.tmux._connect", return_value=client),
        patch("rnssh.tmux.private_key_path"),
    ):
        kill_session(host, "work")

    client.exec_command.assert_called_once()
    cmd = client.exec_command.call_args[0][0]
    assert cmd == "tmux kill-session -t 'work'"
    client.close.assert_called_once()


def test_kill_session_not_found() -> None:
    host = Host(name="box", hostname="h.example", user="u", key_name="default")
    client = MagicMock()
    stdout = MagicMock()
    stderr = MagicMock()
    stdout.read.return_value = b""
    stderr.read.return_value = b"can't find session: missing"
    stdout.channel.recv_exit_status.return_value = 1
    client.exec_command.return_value = (MagicMock(), stdout, stderr)

    with patch("rnssh.tmux._connect", return_value=client):
        with pytest.raises(TmuxError, match="not found"):
            kill_session(host, "missing")


def test_kill_session_empty_name() -> None:
    host = Host(name="box", hostname="h.example", user="u")
    with pytest.raises(TmuxError, match="required"):
        kill_session(host, "  ")


def test_kill_session_jump_unsupported() -> None:
    host = Host(name="box", hostname="h", user="u", jump_host="jump", key_name="default")
    with pytest.raises(TmuxError, match="jump host"):
        kill_session(host, "rnssh")
