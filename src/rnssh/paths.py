"""Application config and key directory paths."""

from __future__ import annotations

import os
from pathlib import Path


APP_NAME = "rnssh"


def config_dir() -> Path:
    """Return ``~/.config/rnssh`` (or ``$XDG_CONFIG_HOME/rnssh``)."""
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        base = Path(xdg)
    else:
        base = Path.home() / ".config"
    return base / APP_NAME


def config_file() -> Path:
    return config_dir() / "config.yaml"


def keys_dir() -> Path:
    return config_dir() / "keys"


def secrets_dir() -> Path:
    """Directory for per-host login passwords (never written to config.yaml)."""
    return config_dir() / "secrets"


def ensure_app_dirs() -> None:
    """Create config, keys, and secrets directories with restrictive permissions."""
    cfg = config_dir()
    keys = keys_dir()
    secrets = secrets_dir()
    cfg.mkdir(mode=0o700, parents=True, exist_ok=True)
    keys.mkdir(mode=0o700, parents=True, exist_ok=True)
    secrets.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        os.chmod(cfg, 0o700)
        os.chmod(keys, 0o700)
        os.chmod(secrets, 0o700)
    except OSError:
        pass
