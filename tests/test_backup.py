"""Tests for backup and restore."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest
import yaml

from rnssh.backup import (
    BACKUP_VERSION,
    BackupError,
    create_backup,
    decrypt_bytes,
    default_backup_filename,
    encrypt_bytes,
    encrypt_bytes_with_params,
    is_encrypted_blob,
    read_backup_info,
    restore_backup,
)
from rnssh.models import AppConfig, Host
from rnssh.paths import config_file, keys_dir, secrets_dir
import rnssh.paths as paths
from rnssh.storage import load_config, save_config


@pytest.fixture()
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    paths.ensure_app_dirs()
    return tmp_path / "rnssh"


def _seed(isolated_config: Path, *, with_password: bool = False) -> AppConfig:
    cfg = AppConfig(language="es")
    host = Host(name="prod", hostname="example.com", user="deploy", key_name="prod")
    if with_password:
        host.password = "ssh-login-secret"
    cfg.upsert_host(host)
    save_config(cfg)
    priv = keys_dir() / "prod"
    pub = keys_dir() / "prod.pub"
    priv.write_text("PRIVATE", encoding="utf-8")
    pub.write_text("PUBLIC", encoding="utf-8")
    priv.chmod(0o600)
    return cfg


def test_default_backup_filename() -> None:
    name = default_backup_filename()
    assert name.startswith("rnssh-backup-")
    assert name.endswith(".zip")


def test_encrypt_decrypt_roundtrip() -> None:
    blob = encrypt_bytes(b"secret-key-material", "correct horse battery")
    assert is_encrypted_blob(blob)
    assert b"secret" not in blob
    assert decrypt_bytes(blob, "correct horse battery") == b"secret-key-material"
    with pytest.raises(BackupError):
        decrypt_bytes(blob, "wrong-password")


def test_rns1_golden_vector() -> None:
    """Must match SSHAndroid / shared vectors (PBKDF2 600k + AES-256-GCM)."""
    fixture_path = Path(__file__).parent / "fixtures" / "rns1_golden_vector.json"
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    password = fixture["password"]
    salt = bytes.fromhex(fixture["salt_hex"])
    nonce = bytes.fromhex(fixture["nonce_hex"])
    plaintext = fixture["plaintext"].encode("utf-8")
    expected = bytes.fromhex(fixture["ciphertext_hex"])
    blob = encrypt_bytes_with_params(plaintext, password, salt=salt, nonce=nonce)
    assert blob == expected
    assert decrypt_bytes(blob, password) == plaintext


def test_backup_and_restore_roundtrip(isolated_config: Path, tmp_path: Path) -> None:
    _seed(isolated_config)
    archive = tmp_path / "out" / "backup.zip"
    info = create_backup(archive, include_keys=True, password="test-pass-99")
    assert info.path.exists()
    assert info.host_count == 1
    assert info.key_count == 2
    assert info.include_keys is True
    assert info.keys_encrypted is True
    assert info.format_version == BACKUP_VERSION

    inspected = read_backup_info(info.path)
    assert inspected.host_count == 1
    assert inspected.key_count == 2
    assert inspected.keys_encrypted is True

    with zipfile.ZipFile(info.path, "r") as zf:
        priv_blob = zf.read("keys/prod")
        assert is_encrypted_blob(priv_blob)
        assert b"PRIVATE" not in priv_blob
        manifest = json.loads(zf.read("manifest.json"))
        assert manifest["version"] == 3
        assert manifest["format"] == "rnssh-backup"

    # Wipe current data
    save_config(AppConfig())
    for path in keys_dir().iterdir():
        path.unlink()
    assert load_config().hosts == []

    with pytest.raises(BackupError):
        restore_backup(info.path, restore_keys=True, password="wrong-password")

    result = restore_backup(info.path, restore_keys=True, password="test-pass-99")
    assert result.host_count == 1
    assert result.key_count == 2
    loaded = load_config()
    assert loaded.language == "es"
    assert loaded.hosts[0].name == "prod"
    assert loaded.hosts[0].hostname == "example.com"
    assert loaded.hosts[0].persistent_session is True
    assert (keys_dir() / "prod").read_text(encoding="utf-8") == "PRIVATE"
    assert (keys_dir() / "prod.pub").read_text(encoding="utf-8") == "PUBLIC"


def test_backup_with_login_password_roundtrip(
    isolated_config: Path, tmp_path: Path
) -> None:
    cfg = _seed(isolated_config, with_password=True)
    host_id = cfg.hosts[0].id
    assert (secrets_dir() / host_id).read_text(encoding="utf-8") == "ssh-login-secret"

    archive = tmp_path / "with-secret.zip"
    info = create_backup(
        archive,
        include_keys=True,
        include_secrets=True,
        password="test-pass-99",
    )
    assert info.secret_count == 1
    assert info.secrets_encrypted is True

    with zipfile.ZipFile(archive, "r") as zf:
        names = zf.namelist()
        assert f"secrets/{host_id}.password" in names
        blob = zf.read(f"secrets/{host_id}.password")
        assert is_encrypted_blob(blob)
        raw = yaml.safe_load(zf.read("config.yaml"))
        assert "password" not in raw["hosts"][0]

    save_config(AppConfig())
    for path in list(keys_dir().iterdir()) + list(secrets_dir().iterdir()):
        if path.is_file():
            path.unlink()

    result = restore_backup(
        archive,
        restore_keys=True,
        restore_secrets=True,
        password="test-pass-99",
    )
    assert result.secret_count == 1
    loaded = load_config()
    assert loaded.hosts[0].password == "ssh-login-secret"
    assert (secrets_dir() / host_id).read_text(encoding="utf-8") == "ssh-login-secret"


def test_password_omitted_from_config_yaml(isolated_config: Path) -> None:
    cfg = AppConfig()
    cfg.upsert_host(
        Host(name="x", hostname="h", password="should-not-appear")
    )
    save_config(cfg)
    text = config_file().read_text(encoding="utf-8")
    assert "should-not-appear" not in text
    assert "password" not in yaml.safe_load(text)["hosts"][0]


def test_backup_keys_require_password(isolated_config: Path, tmp_path: Path) -> None:
    _seed(isolated_config)
    with pytest.raises(BackupError):
        create_backup(tmp_path / "x.zip", include_keys=True, password=None)


def test_backup_secrets_require_password(isolated_config: Path, tmp_path: Path) -> None:
    _seed(isolated_config, with_password=True)
    with pytest.raises(BackupError):
        create_backup(
            tmp_path / "x.zip",
            include_keys=False,
            include_secrets=True,
            password=None,
        )


def test_backup_without_keys(isolated_config: Path, tmp_path: Path) -> None:
    _seed(isolated_config)
    archive = tmp_path / "nokeys.zip"
    info = create_backup(archive, include_keys=False, include_secrets=False)
    assert info.key_count == 0
    assert info.include_keys is False
    assert info.keys_encrypted is False

    save_config(AppConfig())
    (keys_dir() / "prod").unlink()
    (keys_dir() / "prod.pub").unlink()

    result = restore_backup(archive, restore_keys=True)
    assert result.host_count == 1
    assert result.key_count == 0
    assert not (keys_dir() / "prod").exists()


def test_v2_backup_still_restores(isolated_config: Path, tmp_path: Path) -> None:
    """Simulate a v2 archive (no secrets/, version 2 manifest)."""
    _seed(isolated_config)
    archive = tmp_path / "v2.zip"
    cfg = load_config()
    with zipfile.ZipFile(archive, "w") as zf:
        manifest = {
            "format": "rnssh-backup",
            "version": 2,
            "created_at": "2024-01-01T00:00:00+00:00",
            "include_keys": True,
            "keys_encrypted": True,
            "kdf": "pbkdf2-sha256",
            "kdf_iterations": 600_000,
            "cipher": "aes-256-gcm",
            "host_count": 1,
            "key_count": 2,
        }
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr(
            "config.yaml",
            yaml.safe_dump(cfg.to_dict(), default_flow_style=False, sort_keys=False),
        )
        zf.writestr("keys/prod", encrypt_bytes(b"PRIVATE", "v2-pass"))
        zf.writestr("keys/prod.pub", encrypt_bytes(b"PUBLIC", "v2-pass"))

    save_config(AppConfig())
    for path in keys_dir().iterdir():
        path.unlink()

    info = read_backup_info(archive)
    assert info.format_version == 2
    assert info.include_secrets is False

    result = restore_backup(archive, restore_keys=True, password="v2-pass")
    assert result.host_count == 1
    assert result.key_count == 2
    assert result.secret_count == 0
    assert (keys_dir() / "prod").read_text(encoding="utf-8") == "PRIVATE"


def test_invalid_backup_rejected(tmp_path: Path, isolated_config: Path) -> None:
    bad = tmp_path / "bad.zip"
    bad.write_bytes(b"not-a-zip")
    with pytest.raises(BackupError):
        read_backup_info(bad)

    empty = tmp_path / "empty.zip"
    with zipfile.ZipFile(empty, "w") as zf:
        zf.writestr("readme.txt", "nope")
    with pytest.raises(BackupError):
        read_backup_info(empty)


def test_backup_contains_config_yaml(isolated_config: Path, tmp_path: Path) -> None:
    _seed(isolated_config)
    archive = tmp_path / "check.zip"
    create_backup(archive, include_keys=True, password="test-pass-99")

    with zipfile.ZipFile(archive, "r") as zf:
        raw = yaml.safe_load(zf.read("config.yaml"))
    assert raw["hosts"][0]["name"] == "prod"
    assert config_file().exists()
