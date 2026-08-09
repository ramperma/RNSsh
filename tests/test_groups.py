"""Tests for host groups."""

from __future__ import annotations

from pathlib import Path

import pytest

from rnssh.models import UNGROUPED, AppConfig, Host
from rnssh.storage import load_config, save_config
import rnssh.paths as paths


@pytest.fixture()
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    paths.ensure_app_dirs()
    return tmp_path / "rnssh"


def test_hosts_by_group_order(isolated_config: Path) -> None:
    cfg = AppConfig(groups=["RamNet", "Clients"])
    cfg.upsert_host(Host(name="a", hostname="a.test", group="Clients"))
    cfg.upsert_host(Host(name="b", hostname="b.test", group="RamNet"))
    cfg.upsert_host(Host(name="c", hostname="c.test", group="RamNet"))
    cfg.upsert_host(Host(name="d", hostname="d.test"))  # ungrouped

    buckets = cfg.hosts_by_group()
    names = [g for g, _ in buckets]
    assert names == ["RamNet", "Clients", UNGROUPED]
    assert [h.name for h in buckets[0][1]] == ["b", "c"]
    assert [h.name for h in buckets[1][1]] == ["a"]
    assert [h.name for h in buckets[2][1]] == ["d"]


def test_empty_groups_still_listed(isolated_config: Path) -> None:
    cfg = AppConfig(groups=["Empty", "Clients"])
    cfg.upsert_host(Host(name="a", hostname="a.test", group="Clients"))
    buckets = cfg.hosts_by_group()
    names = [g for g, _ in buckets]
    assert names == ["Empty", "Clients"]
    assert buckets[0][1] == []
    assert [h.name for h in buckets[1][1]] == ["a"]


def test_set_host_group(isolated_config: Path) -> None:
    cfg = AppConfig(groups=["RamNet"])
    host = Host(name="vps", hostname="1.2.3.4")
    cfg.upsert_host(host)
    assert host.group == ""
    updated = cfg.set_host_group(host.id, "RamNet")
    assert updated is not None
    assert updated.group == "RamNet"
    cfg.set_host_group(host.id, "")
    assert host.group == ""


def test_rename_and_delete_group(isolated_config: Path) -> None:
    cfg = AppConfig()
    h = Host(name="x", hostname="x.test", group="Old")
    cfg.upsert_host(h)
    assert "Old" in cfg.groups

    cfg.rename_group("Old", "New")
    assert h.group == "New"
    assert "New" in cfg.groups
    assert "Old" not in cfg.groups

    cfg.delete_group("New")
    assert h.group == UNGROUPED
    assert "New" not in cfg.groups


def test_group_persisted(isolated_config: Path) -> None:
    cfg = AppConfig(groups=["RamNet"])
    cfg.upsert_host(Host(name="vps", hostname="1.2.3.4", group="RamNet"))
    save_config(cfg)
    loaded = load_config()
    assert loaded.groups == ["RamNet"]
    assert loaded.hosts[0].group == "RamNet"
