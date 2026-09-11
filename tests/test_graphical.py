"""Tests for remote graphical application SSH commands."""

from __future__ import annotations

from pathlib import Path

import pytest

import rnssh.paths as paths
from rnssh.graphical import GraphicalAppError, build_graphical_ssh_argv
from rnssh.keys import generate_ed25519_keypair
from rnssh.models import GraphicalApp, Host


@pytest.fixture()
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("DISPLAY", ":99")
    paths.ensure_app_dirs()
    generate_ed25519_keypair("default")
    return tmp_path / "rnssh"


def test_build_x11_command(isolated_config: Path) -> None:
    host = Host(name="box", hostname="server.example", user="alice", port=2222)
    app = GraphicalApp(
        "Python app",
        "python3 '/home/alice/my app/main.py' --debug",
        working_directory="/home/alice/project",
    )
    argv = build_graphical_ssh_argv(host, app)
    assert "-X" in argv
    assert "-Y" not in argv
    remote = argv[-1]
    assert remote.startswith("if command -v dbus-run-session >/dev/null 2>&1; then")
    assert "exec dbus-run-session -- bash -lc" in remote
    assert "cd '" in remote and "/home/alice/project" in remote
    assert "python3" in remote and "my app/main.py" in remote
    assert "else cd '/home/alice/project'" in remote
    assert argv[argv.index("-p") + 1] == "2222"


def test_trusted_x11_uses_y(isolated_config: Path) -> None:
    host = Host(name="box", hostname="server.example")
    argv = build_graphical_ssh_argv(host, GraphicalApp("Browser", "firefox", trusted_x11=True))
    assert "-Y" in argv
    assert "-X" not in argv


def test_empty_command_is_rejected(isolated_config: Path) -> None:
    host = Host(name="box", hostname="server.example")
    with pytest.raises(GraphicalAppError):
        build_graphical_ssh_argv(host, GraphicalApp("Empty", ""))
