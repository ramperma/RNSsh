"""Remote tmux helpers via Paramiko."""

from __future__ import annotations

from pathlib import Path

import paramiko

from rnssh.keys import private_key_path
from rnssh.models import Host
from rnssh.ssh_cmd import shell_quote


class TmuxError(Exception):
    """Remote tmux operation failed."""


def _connect(host: Host, *, identity: Path | None = None) -> paramiko.SSHClient:
    if host.jump_host:
        # Simple jump: hostname may be user@host:port — Paramiko ProxyJump via SSHConfig is complex;
        # for v1 we require direct key auth for listing/killing when no jump, and document jump limits.
        raise TmuxError("tmux operations via jump host are not supported in v1")
    key_name = host.key_name or "default"
    key_path = identity or private_key_path(key_name)
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    connect_kwargs: dict = {
        "hostname": host.hostname,
        "port": host.port,
        "username": host.user,
        "key_filename": str(key_path),
        "allow_agent": False,
        "look_for_keys": False,
        "timeout": 20,
    }
    client.connect(**connect_kwargs)
    return client


def list_sessions(host: Host, *, identity: Path | None = None) -> list[str]:
    """Return remote tmux session names (empty list if tmux has none / not installed)."""
    client = _connect(host, identity=identity)
    try:
        _stdin, stdout, stderr = client.exec_command("tmux list-sessions -F '#{session_name}'", timeout=15)
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        code = stdout.channel.recv_exit_status()
        if code != 0:
            # No server / no sessions is common
            if "no server running" in err.lower() or "no sessions" in err.lower():
                return []
            if "command not found" in err.lower() or code == 127:
                raise TmuxError("tmux is not installed on the remote host")
            # Still try to parse any names from stdout
        names = [line.strip() for line in out.splitlines() if line.strip()]
        return names
    finally:
        client.close()


def attach_command(session: str) -> str:
    return f"tmux new-session -A -s {shell_quote(session)}"


def kill_command(session: str) -> str:
    """Build the remote shell command to kill a tmux session by name."""
    return f"tmux kill-session -t {shell_quote(session)}"


def kill_session(host: Host, session: str, *, identity: Path | None = None) -> None:
    """Kill a remote tmux session. Raises ``TmuxError`` on failure."""
    name = (session or "").strip()
    if not name:
        raise TmuxError("tmux session name is required")
    client = _connect(host, identity=identity)
    try:
        _stdin, stdout, stderr = client.exec_command(kill_command(name), timeout=15)
        err = stderr.read().decode("utf-8", errors="replace")
        code = stdout.channel.recv_exit_status()
        if code == 0:
            return
        err_l = err.lower()
        if "session not found" in err_l or "can't find session" in err_l:
            raise TmuxError(f"tmux session “{name}” not found")
        if "no server running" in err_l or "no sessions" in err_l:
            raise TmuxError(f"tmux session “{name}” not found")
        if "command not found" in err_l or code == 127:
            raise TmuxError("tmux is not installed on the remote host")
        detail = err.strip() or f"exit code {code}"
        raise TmuxError(f"failed to kill tmux session “{name}”: {detail}")
    finally:
        client.close()
