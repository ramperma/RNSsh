"""Tests for Ed25519 key generation."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

import rnssh.keys as keymod
import rnssh.paths as paths


@pytest.fixture()
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    paths.ensure_app_dirs()
    return tmp_path / "rnssh"


def test_generate_ed25519_keypair(isolated_config: Path) -> None:
    priv = keymod.generate_ed25519_keypair("devbox", comment="test@rnssh")
    assert priv.exists()
    assert keymod.public_key_path("devbox").exists()
    mode = priv.stat().st_mode & 0o777
    assert mode == 0o600
    pub = keymod.read_public_key("devbox")
    assert pub.startswith("ssh-ed25519 ")
    assert "test@rnssh" in pub


def test_reject_invalid_name(isolated_config: Path) -> None:
    with pytest.raises(keymod.SSHKeyError):
        keymod.generate_ed25519_keypair("../evil")


def test_ensure_keypair_idempotent(isolated_config: Path) -> None:
    p1 = keymod.ensure_keypair("shared")
    p2 = keymod.ensure_keypair("shared")
    assert p1 == p2


def test_refuse_world_readable(isolated_config: Path) -> None:
    priv = keymod.generate_ed25519_keypair("loose")
    os.chmod(priv, 0o644)
    with pytest.raises(keymod.SSHKeyError):
        keymod.ensure_keypair("loose")
