"""Build OpenSSH client argv for a host."""

from __future__ import annotations

from pathlib import Path

from rnssh.keys import private_key_path
from rnssh.models import Host


def build_ssh_argv(
    host: Host,
    *,
    remote_command: str | None = None,
    identity: Path | None = None,
    extra_opts: list[str] | None = None,
) -> list[str]:
    """Return argv for the system ``ssh`` client."""
    key_name = host.key_name or "default"
    key_path = identity or private_key_path(key_name)

    argv: list[str] = [
        "ssh",
        "-i",
        str(key_path),
        "-p",
        str(host.port),
        "-o",
        "IdentitiesOnly=yes",
        "-o",
        "StrictHostKeyChecking=accept-new",
    ]
    if host.agent_forwarding:
        argv.append("-A")
    if host.jump_host:
        argv.extend(["-J", host.jump_host])
    if extra_opts:
        argv.extend(extra_opts)

    target = f"{host.user}@{host.hostname}"
    argv.append(target)

    if remote_command:
        argv.extend(["-t", remote_command])

    return argv


def build_plain_ssh_argv(host: Host, *, identity: Path | None = None) -> list[str]:
    return build_ssh_argv(host, identity=identity)


def build_tmux_ssh_argv(
    host: Host,
    *,
    session: str | None = None,
    identity: Path | None = None,
) -> list[str]:
    session_name = session or host.tmux_session or "rnssh"
    # Attach if exists, otherwise create — keeps work persistent across disconnects.
    remote = f"tmux new-session -A -s {shell_quote(session_name)}"
    return build_ssh_argv(host, remote_command=remote, identity=identity)


def shell_quote(value: str) -> str:
    """Minimal single-quote escaping for remote shell tokens."""
    return "'" + value.replace("'", "'\"'\"'") + "'"
