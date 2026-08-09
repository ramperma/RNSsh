"""Tests for SSH argv builders and terminal wrapping."""

from __future__ import annotations

from pathlib import Path

import pytest

import rnssh.paths as paths
from rnssh import keys as keymod
from rnssh.models import Host
from rnssh.ssh_cmd import build_plain_ssh_argv, build_tmux_ssh_argv, shell_quote
from rnssh.terminal import build_terminal_argv


@pytest.fixture()
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    paths.ensure_app_dirs()
    keymod.generate_ed25519_keypair("default")
    return tmp_path / "rnssh"


def test_shell_quote() -> None:
    assert shell_quote("rnssh") == "'rnssh'"
    assert "\"'\"" in shell_quote("a'b")


def test_plain_ssh_argv(isolated_config: Path) -> None:
    host = Host(
        name="box",
        hostname="10.0.0.1",
        user="alice",
        port=2222,
        key_name="default",
        agent_forwarding=True,
        jump_host="jump.example",
    )
    argv = build_plain_ssh_argv(host)
    assert argv[0] == "ssh"
    assert "-i" in argv
    assert "-p" in argv
    assert argv[argv.index("-p") + 1] == "2222"
    assert "-A" in argv
    assert "-J" in argv
    assert argv[argv.index("-J") + 1] == "jump.example"
    assert argv[-1] == "alice@10.0.0.1"


def test_tmux_ssh_argv(isolated_config: Path) -> None:
    host = Host(name="box", hostname="h", user="u", key_name="default", tmux_session="work")
    argv = build_tmux_ssh_argv(host)
    assert "-t" in argv
    remote = argv[argv.index("-t") + 1]
    assert "tmux new-session -A -s" in remote
    assert "'work'" in remote


def test_terminal_gnome() -> None:
    argv = build_terminal_argv(["ssh", "user@host"], terminal="/usr/bin/gnome-terminal")
    assert argv[:3] == ["/usr/bin/gnome-terminal", "--wait", "--"]
    assert argv[3:] == ["ssh", "user@host"]


def test_terminal_xterm() -> None:
    argv = build_terminal_argv(["ssh", "user@host"], terminal="/usr/bin/xterm")
    assert argv[0] == "/usr/bin/xterm"
    assert argv[1] == "-e"
    assert argv[2:] == ["ssh", "user@host"]


def test_wrap_keep_open_on_failure(tmp_path: Path) -> None:
    from rnssh.terminal import wrap_keep_open_on_failure

    status = tmp_path / "status"
    done = tmp_path / "done"
    failed = tmp_path / "failed"
    wrapped = wrap_keep_open_on_failure(
        ["ssh", "-p", "22", "u@h"],
        status_file=status,
        done_file=done,
        failed_file=failed,
    )
    assert wrapped[0] == "bash"
    assert wrapped[1] == "-lc"
    script = wrapped[2]
    assert "ssh -p 22 u@h" in script
    assert "Press Enter to close" in script
    assert "failed_file=" in script
    assert "done_file=" in script
    assert "trap finish EXIT" in script
    assert str(status) in script
    assert str(done) in script
    assert str(failed) in script


def test_launch_finished_marker(tmp_path: Path) -> None:
    from rnssh.terminal import launch_failed, launch_finished

    done = tmp_path / "done"
    failed = tmp_path / "failed"
    assert launch_finished(None) is False
    assert launch_finished(done) is False
    assert launch_failed(failed) is False
    done.write_text("1\n", encoding="utf-8")
    assert launch_finished(done) is True
    failed.write_text("1\n", encoding="utf-8")
    assert launch_failed(failed) is True
