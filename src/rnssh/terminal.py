"""Discover and launch the OS native terminal with a command."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass


class TerminalError(Exception):
    """No suitable terminal emulator found or launch failed."""


@dataclass
class LaunchResult:
    argv: list[str]
    pid: int


# (binary_name, argv builder taking the inner command string)
def _env_terminal() -> str | None:
    return os.environ.get("RNSSH_TERMINAL") or None


def _which(name: str) -> str | None:
    return shutil.which(name)


def find_terminal() -> str:
    """Return path to a terminal emulator (Linux-first)."""
    env = _env_terminal()
    if env:
        path = _which(env) if os.sep not in env else (env if os.path.isfile(env) else None)
        if path:
            return path
        if os.path.isfile(env) and os.access(env, os.X_OK):
            return env
        raise TerminalError(f"RNSSH_TERMINAL={env!r} not found or not executable")

    if sys.platform.startswith("linux"):
        candidates = [
            "x-terminal-emulator",
            "gnome-terminal",
            "konsole",
            "xfce4-terminal",
            "mate-terminal",
            "tilix",
            "kitty",
            "alacritty",
            "wezterm",
            "xterm",
        ]
        for name in candidates:
            path = _which(name)
            if path:
                return path
        raise TerminalError(
            "No terminal emulator found. Install gnome-terminal, konsole, xterm, "
            "or set RNSSH_TERMINAL."
        )

    if sys.platform == "darwin":
        # Stub: Terminal.app via `open` needs a different launch path
        term = _which("osascript")
        if term:
            return "Terminal.app"
        raise TerminalError("No macOS terminal launcher available")

    if sys.platform.startswith("win"):
        wt = _which("wt.exe") or _which("wt")
        if wt:
            return wt
        return "cmd.exe"

    raise TerminalError(f"Unsupported platform: {sys.platform}")


def build_terminal_argv(command: list[str], *, terminal: str | None = None) -> list[str]:
    """Wrap ``command`` so it runs inside a new terminal window."""
    term = terminal or find_terminal()
    basename = os.path.basename(term)

    # Join for shells that take a single -e/-x string; prefer list where supported.
    cmd_str = subprocess.list2cmdline(command) if sys.platform.startswith("win") else _join_posix(command)

    if basename in {"gnome-terminal", "gnome-terminal.real"}:
        # gnome-terminal wants -- then the command argv
        return [term, "--", *command]

    if basename == "xfce4-terminal":
        return [term, "-e", cmd_str]

    if basename == "mate-terminal":
        return [term, "-e", cmd_str]

    if basename == "tilix":
        return [term, "-e", cmd_str]

    if basename == "konsole":
        return [term, "-e", *command]

    if basename == "kitty":
        return [term, *command]

    if basename == "alacritty":
        return [term, "-e", *command]

    if basename == "wezterm":
        return [term, "start", "--", *command]

    if basename == "xterm":
        return [term, "-e", *command]

    if basename == "x-terminal-emulator":
        # Debian alternative — usually supports -e
        return [term, "-e", *command]

    if term == "Terminal.app" or basename == "Terminal.app":
        # Launch via open; command runs inside login shell after open — limited stub
        script = f'tell application "Terminal" to do script {repr(cmd_str)}'
        return ["osascript", "-e", script]

    if basename in {"wt.exe", "wt"}:
        return [term, "new-tab", "--", *command]

    if basename.lower() in {"cmd.exe", "cmd"}:
        return [term, "/K", cmd_str]

    # Generic fallback
    return [term, "-e", cmd_str]


def _join_posix(argv: list[str]) -> str:
    parts: list[str] = []
    for arg in argv:
        if arg == "":
            parts.append("''")
            continue
        if all(c.isalnum() or c in "@%_+:,./=-" for c in arg):
            parts.append(arg)
        else:
            parts.append("'" + arg.replace("'", "'\"'\"'") + "'")
    return " ".join(parts)


def launch_in_terminal(command: list[str], *, terminal: str | None = None) -> LaunchResult:
    """Spawn a terminal running ``command``; return PID of the terminal process."""
    argv = build_terminal_argv(command, terminal=terminal)
    try:
        proc = subprocess.Popen(  # noqa: S603 — intentional launch of user terminal
            argv,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
    except OSError as exc:
        raise TerminalError(f"Failed to launch terminal: {exc}") from exc
    return LaunchResult(argv=argv, pid=proc.pid)


def close_process(pid: int) -> None:
    """Best-effort terminate of a previously launched terminal PID."""
    try:
        os.kill(pid, 15)
    except OSError:
        pass
