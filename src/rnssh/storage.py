"""Load and save application configuration."""

from __future__ import annotations

from pathlib import Path

import yaml

from rnssh.models import AppConfig
from rnssh.paths import config_file, ensure_app_dirs


def load_config(path: Path | None = None) -> AppConfig:
    ensure_app_dirs()
    cfg_path = path or config_file()
    if not cfg_path.exists():
        return AppConfig()
    with cfg_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return AppConfig.from_dict(data)


def save_config(config: AppConfig, path: Path | None = None) -> None:
    ensure_app_dirs()
    cfg_path = path or config_file()
    cfg_path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    with cfg_path.open("w", encoding="utf-8") as fh:
        yaml.safe_dump(
            config.to_dict(),
            fh,
            default_flow_style=False,
            sort_keys=False,
            allow_unicode=True,
        )
    try:
        cfg_path.chmod(0o600)
    except OSError:
        pass
