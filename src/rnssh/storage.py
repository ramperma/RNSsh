"""Load and save application configuration and per-host secrets."""

from __future__ import annotations

import os
from pathlib import Path

import yaml

from rnssh.models import AppConfig
from rnssh.paths import config_file, ensure_app_dirs, secrets_dir


def _safe_secret_name(host_id: str) -> str | None:
    """Return a basename-safe host id, or None if unsafe."""
    name = (host_id or "").strip()
    if not name or "/" in name or name.startswith(".") or "\\" in name:
        return None
    return name


# Non-host files that must survive the secrets/ orphan cleanup.
_PROTECTED_SECRET_FILES = {"ai-config.yaml"}


def load_host_passwords(config: AppConfig) -> None:
    """Hydrate ``Host.password`` from ``~/.config/rnssh/secrets/<id>``."""
    directory = secrets_dir()
    if not directory.is_dir():
        return
    for host in config.hosts:
        safe = _safe_secret_name(host.id)
        if not safe:
            continue
        path = directory / safe
        if not path.is_file():
            continue
        try:
            host.password = path.read_text(encoding="utf-8")
        except OSError:
            host.password = ""


def save_host_passwords(config: AppConfig) -> None:
    """Persist non-empty host passwords; remove files for cleared passwords."""
    ensure_app_dirs()
    directory = secrets_dir()
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        os.chmod(directory, 0o700)
    except OSError:
        pass

    keep: set[str] = set()
    for host in config.hosts:
        safe = _safe_secret_name(host.id)
        if not safe:
            continue
        path = directory / safe
        password = host.password or ""
        if password:
            path.write_text(password, encoding="utf-8")
            try:
                path.chmod(0o600)
            except OSError:
                pass
            keep.add(safe)
        elif path.exists():
            try:
                path.unlink()
            except OSError:
                pass

    # Drop orphan secret files for removed hosts.
    for path in directory.iterdir():
        if (
            path.is_file()
            and not path.name.startswith(".")
            and path.name not in keep
            and path.name not in _PROTECTED_SECRET_FILES
        ):
            try:
                path.unlink()
            except OSError:
                pass


def set_host_password(host_id: str, password: str) -> None:
    """Write or clear a single host password file."""
    ensure_app_dirs()
    safe = _safe_secret_name(host_id)
    if not safe:
        return
    path = secrets_dir() / safe
    if password:
        path.write_text(password, encoding="utf-8")
        try:
            path.chmod(0o600)
        except OSError:
            pass
    elif path.exists():
        try:
            path.unlink()
        except OSError:
            pass


def load_config(path: Path | None = None) -> AppConfig:
    ensure_app_dirs()
    cfg_path = path or config_file()
    if not cfg_path.exists():
        cfg = AppConfig()
    else:
        with cfg_path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        cfg = AppConfig.from_dict(data)
    load_host_passwords(cfg)
    return cfg


def _atomic_write(path: Path, data: str) -> None:
    """Write ``data`` atomically (temp file + rename) so a failure never
    truncates the real config on disk."""
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(data, encoding="utf-8")
    try:
        tmp.chmod(0o600)
    except OSError:
        pass
    os.replace(tmp, path)


def save_config(config: AppConfig, path: Path | None = None) -> None:
    ensure_app_dirs()
    cfg_path = path or config_file()
    cfg_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    _atomic_write(
        cfg_path,
        yaml.safe_dump(
            config.to_dict(),
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        ),
    )
    save_host_passwords(config)

