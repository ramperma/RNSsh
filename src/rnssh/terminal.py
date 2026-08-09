"""Discover and launch the OS native terminal with a command."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path


class TerminalError(Exception):
    """No suitable terminal emulator found or launch failed."""


@dataclass
class LaunchResult:
    argv: list[str]
    pid: int
    launch_id: str = ""
    host_id: str = ""
    host_name: str = ""
    status_file: Path | None = None
    done_file: Path | None = None
    failed_file: Path | None = None
    log_file: Path | None = None
    started_at: float = 0.0


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
        # --wait keeps the launcher alive until the window closes (for exit monitoring)
        return [term, "--wait", "--", *command]

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


def wrap_keep_open_on_failure(
    command: list[str],
    *,
    status_file: Path,
    done_file: Path,
    failed_file: Path,
    keep_open_seconds: int = 90,
) -> list[str]:
    """Wrap ``command`` so a quick failure stays visible and signals completion.

    - ``status_file``: exit code of the command
    - ``failed_file``: created only for quick non-zero exits (real connection failures)
    - ``done_file``: created when the wrapper fully ends (Enter or window close)

    Closing a healthy long-lived session (clicking the window X) usually yields a
    non-zero SSH exit code; those are ignored for the GUI dialog / keep-open
    prompt when the session lasted longer than ``keep_open_seconds``.
    """
    if sys.platform.startswith("win"):
        # Best-effort: cmd /K keeps the window open after the command.
        return ["cmd.exe", "/K", subprocess.list2cmdline(command)]

    cmd = _join_posix(command)
    status = _join_posix([str(status_file)])
    done = _join_posix([str(done_file)])
    failed = _join_posix([str(failed_file)])
    seconds = str(int(keep_open_seconds))
    # EXIT trap covers both "Press Enter" and closing the window (SIGHUP).
    # Do not pipe SSH: it needs a real TTY.
    script = (
        "ec=1; "
        f"status_file={status}; "
        f"done_file={done}; "
        f"failed_file={failed}; "
        'finish() { '
        '  printf "%s\\n" "$ec" > "$status_file"; '
        '  printf "1\\n" > "$done_file"; '
        "}; "
        "trap finish EXIT; "
        "set +e; "
        "start_ts=$(date +%s); "
        f"{cmd}; "
        "ec=$?; "
        "end_ts=$(date +%s); "
        "elapsed=$((end_ts - start_ts)); "
        'printf "%s\\n" "$ec" > "$status_file"; '
        f'if [ "$ec" -ne 0 ] && [ "$elapsed" -lt {seconds} ]; then '
        '  printf "1\\n" > "$failed_file"; '
        "  echo; "
        "  echo '======== RNSsh ========'; "
        '  echo "Connection failed (exit $ec)."; '
        "  echo 'Press Enter to close…'; "
        "  read -r _ || true; "
        "fi"
    )
    return ["bash", "-lc", script]


def launch_in_terminal(
    command: list[str],
    *,
    terminal: str | None = None,
    keep_open_on_failure: bool = True,
    host_id: str = "",
    host_name: str = "",
) -> LaunchResult:
    """Spawn a terminal running ``command``; return PID of the terminal process."""
    status_file: Path | None = None
    done_file: Path | None = None
    failed_file: Path | None = None
    run_cmd = command
    launch_id = uuid.uuid4().hex
    if keep_open_on_failure and not sys.platform.startswith("win"):
        tmp = Path(tempfile.mkdtemp(prefix=f"rnssh-{launch_id[:8]}-"))
        status_file = tmp / "status"
        done_file = tmp / "done"
        failed_file = tmp / "failed"
        run_cmd = wrap_keep_open_on_failure(
            command,
            status_file=status_file,
            done_file=done_file,
            failed_file=failed_file,
        )

    argv = build_terminal_argv(run_cmd, terminal=terminal)
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
    return LaunchResult(
        argv=argv,
        pid=proc.pid,
        launch_id=launch_id,
        host_id=host_id,
        host_name=host_name,
        status_file=status_file,
        done_file=done_file,
        failed_file=failed_file,
        log_file=None,
        started_at=time.time(),
    )


def launch_finished(done_file: Path | None) -> bool:
    """Return True when the wrapper has fully finished (terminal session ended)."""
    return done_file is not None and done_file.is_file()


def launch_failed(failed_file: Path | None) -> bool:
    """Return True when the wrapper marked a quick connection failure."""
    return failed_file is not None and failed_file.is_file()


def cleanup_launch_files(launch: LaunchResult) -> None:
    """Remove temporary status/done/failed files for a finished launch."""
    for path in (launch.status_file, launch.done_file, launch.failed_file, launch.log_file):
        if path is None:
            continue
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
        parent = path.parent
        try:
            if parent.is_dir() and not any(parent.iterdir()):
                parent.rmdir()
        except OSError:
            pass


def read_launch_status(status_file: Path | None) -> int | None:
    """Return exit code from a status file, or ``None`` if unavailable."""
    if status_file is None or not status_file.is_file():
        return None
    try:
        text = status_file.read_text(encoding="utf-8").strip()
        return int(text.splitlines()[0])
    except (OSError, ValueError, IndexError):
        return None


def read_launch_log(log_file: Path | None, *, max_chars: int = 4000) -> str:
    """Return captured command output (tail), or empty string."""
    if log_file is None or not log_file.is_file():
        return ""
    try:
        text = log_file.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    if len(text) > max_chars:
        return "…\n" + text[-max_chars:]
    return text


def process_alive(pid: int) -> bool:
    """Return True if ``pid`` appears to be a living process."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def close_process(pid: int) -> None:
    """Best-effort terminate of a previously launched terminal PID."""
    try:
        os.kill(pid, 15)
    except OSError:
        pass
