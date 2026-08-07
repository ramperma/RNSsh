"""Tests for config storage."""

from __future__ import annotations

from pathlib import Path

import pytest

from rnssh.models import AppConfig, Host
from rnssh.paths import config_file
import rnssh.paths as paths
from rnssh.storage import load_config, save_config


@pytest.fixture()
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    paths.ensure_app_dirs()
    return tmp_path / "rnssh"


def test_roundtrip(isolated_config: Path) -> None:
    cfg = AppConfig()
    host = Host(name="prod", hostname="example.com", user="deploy", port=2222)
    cfg.upsert_host(host)
    save_config(cfg)
    assert config_file().exists()

    loaded = load_config()
    assert len(loaded.hosts) == 1
    h = loaded.hosts[0]
    assert h.name == "prod"
    assert h.hostname == "example.com"
    assert h.user == "deploy"
    assert h.port == 2222
    assert h.id == host.id


def test_upsert_and_remove(isolated_config: Path) -> None:
    cfg = AppConfig()
    h = Host(name="a", hostname="a.test")
    cfg.upsert_host(h)
    h.name = "b"
    cfg.upsert_host(h)
    assert len(cfg.hosts) == 1
    assert cfg.hosts[0].name == "b"
    assert cfg.remove_host(h.id)
    assert cfg.hosts == []
