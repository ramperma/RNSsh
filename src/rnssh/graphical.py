"""Launch remote graphical applications through SSH X11 forwarding."""

from __future__ import annotations

import os
import shlex

from rnssh.keys import private_key_path
from rnssh.models import GraphicalApp, Host
from rnssh.ssh_cmd import build_ssh_argv, shell_quote


class GraphicalAppError(Exception):
    """Raised when a remote graphical command is not launchable."""


def build_graphical_ssh_argv(host: Host, app: GraphicalApp) -> list[str]:
    """Build an SSH command that displays one remote app on the local desktop."""
    command = app.command.strip()
    if not command:
        raise GraphicalAppError("The graphical application command is empty.")
    if "\n" in command or "\r" in command:
        raise GraphicalAppError("The graphical application command cannot contain newlines.")
    try:
        command_parts = shlex.split(command)
    except ValueError as exc:
        raise GraphicalAppError(f"Invalid application command: {exc}") from exc
    if not command_parts:
        raise GraphicalAppError("The graphical application command is empty.")
    if not os.environ.get("DISPLAY"):
        raise GraphicalAppError(
            "No local X11 display is available. X11 forwarding needs an X server or XWayland."
        )

    key_path = private_key_path(host.key_name or "default")
    if not key_path.is_file():
        raise GraphicalAppError(
            "No RNSsh SSH key was found for this host. Provision the host key first."
        )

    forwarding = "-Y" if app.trusted_x11 else "-X"
    argv = build_ssh_argv(
        host,
        extra_opts=[forwarding, "-o", "ExitOnForwardFailure=yes", "-o", "RequestTTY=no"],
    )
    app_command = shlex.join(command_parts)
    if app.working_directory.strip():
        app_command = f"cd {shell_quote(app.working_directory.strip())} && exec {app_command}"
    else:
        app_command = f"exec {app_command}"
    # A remote desktop user's D-Bus session can redirect single-instance GTK/Qt
    # apps to the server's existing display. Give each forwarded app its own bus.
    argv.append(
        "if command -v dbus-run-session >/dev/null 2>&1; then "
        f"exec dbus-run-session -- bash -lc {shell_quote(app_command)}; "
        f"else {app_command}; fi"
    )
    return argv
