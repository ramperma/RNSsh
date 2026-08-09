"""Backup and restore of connections (config + encrypted SSH keys + passwords)."""

from __future__ import annotations

import json
import os
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from rnssh.models import AppConfig
from rnssh.paths import ensure_app_dirs, keys_dir
from rnssh.storage import load_config, load_host_passwords, save_config

BACKUP_FORMAT = "rnssh-backup"
BACKUP_VERSION = 3
MANIFEST_NAME = "manifest.json"
CONFIG_NAME = "config.yaml"
KEYS_PREFIX = "keys/"
SECRETS_PREFIX = "secrets/"
PASSWORD_SUFFIX = ".password"

_ENC_MAGIC = b"RNS1"
_SALT_LEN = 16
_NONCE_LEN = 12
_KEY_LEN = 32
_PBKDF2_ITERATIONS = 600_000


class BackupError(Exception):
    """Raised when a backup cannot be created or restored."""


@dataclass(frozen=True)
class BackupInfo:
    path: Path
    created_at: str
    host_count: int
    key_count: int
    include_keys: bool
    keys_encrypted: bool = False
    include_secrets: bool = False
    secrets_encrypted: bool = False
    secret_count: int = 0
    format_version: int = BACKUP_VERSION


@dataclass(frozen=True)
class RestoreResult:
    host_count: int
    key_count: int
    include_keys: bool
    secret_count: int = 0
    include_secrets: bool = False


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def default_backup_filename(*, when: datetime | None = None) -> str:
    stamp = (when or datetime.now()).strftime("%Y%m%d-%H%M%S")
    return f"rnssh-backup-{stamp}.zip"


def _iter_key_files(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    files: list[Path] = []
    for path in sorted(directory.iterdir()):
        if path.is_file() and not path.name.startswith("."):
            files.append(path)
    return files


def _hosts_with_passwords(cfg: AppConfig) -> list[tuple[str, str]]:
    """Return ``(host_id, password)`` for hosts that have a non-empty password."""
    out: list[tuple[str, str]] = []
    for host in cfg.hosts:
        password = (host.password or "").strip()
        if not password:
            continue
        host_id = (host.id or "").strip()
        if not host_id or "/" in host_id or host_id.startswith("."):
            continue
        out.append((host_id, host.password))
    return out


def _safe_arc_basename(name: str) -> bool:
    return bool(name) and "/" not in name and "\\" not in name and not name.startswith(".")


def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=_KEY_LEN,
        salt=salt,
        iterations=_PBKDF2_ITERATIONS,
    )
    return kdf.derive(password.encode("utf-8"))


def encrypt_bytes(plaintext: bytes, password: str) -> bytes:
    """Encrypt ``plaintext`` with a password (AES-256-GCM + PBKDF2)."""
    if not password:
        raise BackupError("Password required to encrypt keys")
    salt = os.urandom(_SALT_LEN)
    nonce = os.urandom(_NONCE_LEN)
    key = _derive_key(password, salt)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
    return _ENC_MAGIC + salt + nonce + ciphertext


def encrypt_bytes_with_params(
    plaintext: bytes,
    password: str,
    *,
    salt: bytes,
    nonce: bytes,
) -> bytes:
    """Encrypt with caller-supplied salt/nonce (for golden-vector tests)."""
    if len(salt) != _SALT_LEN or len(nonce) != _NONCE_LEN:
        raise BackupError("Invalid salt or nonce length")
    if not password:
        raise BackupError("Password required to encrypt keys")
    key = _derive_key(password, salt)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, None)
    return _ENC_MAGIC + salt + nonce + ciphertext


def decrypt_bytes(blob: bytes, password: str) -> bytes:
    """Decrypt a blob produced by :func:`encrypt_bytes`."""
    if not password:
        raise BackupError("Password required to decrypt keys")
    if not blob.startswith(_ENC_MAGIC):
        raise BackupError("Invalid encrypted key data")
    min_len = len(_ENC_MAGIC) + _SALT_LEN + _NONCE_LEN + 16
    if len(blob) < min_len:
        raise BackupError("Invalid encrypted key data")
    offset = len(_ENC_MAGIC)
    salt = blob[offset : offset + _SALT_LEN]
    offset += _SALT_LEN
    nonce = blob[offset : offset + _NONCE_LEN]
    offset += _NONCE_LEN
    ciphertext = blob[offset:]
    key = _derive_key(password, salt)
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, None)
    except Exception as exc:  # noqa: BLE001 — AESGCM raises InvalidTag
        raise BackupError("Wrong password or corrupt encrypted key data") from exc


def is_encrypted_blob(data: bytes) -> bool:
    return data.startswith(_ENC_MAGIC)


def create_backup(
    dest: Path,
    *,
    include_keys: bool = True,
    include_secrets: bool = True,
    password: str | None = None,
    config: AppConfig | None = None,
) -> BackupInfo:
    """Write a ZIP backup of the current config (and optionally encrypted keys/secrets)."""
    ensure_app_dirs()
    cfg = config if config is not None else load_config()
    if config is not None:
        # Ensure passwords from secrets/ are attached even if the UI config is stale.
        load_host_passwords(cfg)
    dest = Path(dest)
    if dest.suffix.lower() != ".zip":
        dest = dest.with_suffix(".zip")
    dest.parent.mkdir(parents=True, exist_ok=True)

    key_files = _iter_key_files(keys_dir()) if include_keys else []
    password_entries = _hosts_with_passwords(cfg) if include_secrets else []
    keys_encrypted = bool(include_keys and key_files)
    secrets_encrypted = bool(include_secrets and password_entries)
    needs_password = keys_encrypted or secrets_encrypted
    if needs_password and not password:
        raise BackupError("Password required when including SSH keys or login passwords")

    use_crypto = bool(password) and needs_password
    manifest = {
        "format": BACKUP_FORMAT,
        "version": BACKUP_VERSION,
        "created_at": _utc_now_iso(),
        "include_keys": include_keys,
        "keys_encrypted": bool(use_crypto and keys_encrypted),
        "include_secrets": include_secrets,
        "secrets_encrypted": bool(use_crypto and secrets_encrypted),
        "kdf": "pbkdf2-sha256" if use_crypto else None,
        "kdf_iterations": _PBKDF2_ITERATIONS if use_crypto else None,
        "cipher": "aes-256-gcm" if use_crypto else None,
        "host_count": len(cfg.hosts),
        "key_count": len(key_files),
        "secret_count": len(password_entries),
    }

    try:
        with zipfile.ZipFile(dest, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(
                MANIFEST_NAME,
                json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
            )
            zf.writestr(
                CONFIG_NAME,
                yaml.safe_dump(
                    cfg.to_dict(),
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True,
                ),
            )
            for key_path in key_files:
                arcname = f"{KEYS_PREFIX}{key_path.name}"
                raw = key_path.read_bytes()
                payload = (
                    encrypt_bytes(raw, password or "")
                    if use_crypto and keys_encrypted
                    else raw
                )
                zf.writestr(arcname, payload)
            for host_id, host_password in password_entries:
                arcname = f"{SECRETS_PREFIX}{host_id}{PASSWORD_SUFFIX}"
                raw = host_password.encode("utf-8")
                payload = (
                    encrypt_bytes(raw, password or "")
                    if use_crypto and secrets_encrypted
                    else raw
                )
                zf.writestr(arcname, payload)
    except OSError as exc:
        raise BackupError(f"Could not write backup: {exc}") from exc

    try:
        dest.chmod(0o600)
    except OSError:
        pass

    return BackupInfo(
        path=dest,
        created_at=manifest["created_at"],
        host_count=len(cfg.hosts),
        key_count=len(key_files),
        include_keys=include_keys,
        keys_encrypted=bool(manifest["keys_encrypted"]),
        include_secrets=include_secrets,
        secrets_encrypted=bool(manifest["secrets_encrypted"]),
        secret_count=len(password_entries),
        format_version=BACKUP_VERSION,
    )


def read_backup_info(source: Path) -> BackupInfo:
    """Inspect a backup ZIP without restoring it."""
    source = Path(source)
    if not source.is_file():
        raise BackupError(f"Backup not found: {source}")
    try:
        with zipfile.ZipFile(source, "r") as zf:
            names = set(zf.namelist())
            if CONFIG_NAME not in names:
                raise BackupError("Invalid backup: missing config.yaml")
            created_at = ""
            include_keys = any(n.startswith(KEYS_PREFIX) for n in names)
            include_secrets = any(n.startswith(SECRETS_PREFIX) for n in names)
            host_count = 0
            key_count = sum(
                1 for n in names if n.startswith(KEYS_PREFIX) and not n.endswith("/")
            )
            secret_count = sum(
                1
                for n in names
                if n.startswith(SECRETS_PREFIX)
                and not n.endswith("/")
                and n.endswith(PASSWORD_SUFFIX)
            )
            version = BACKUP_VERSION
            keys_encrypted = False
            secrets_encrypted = False
            if MANIFEST_NAME in names:
                try:
                    manifest = json.loads(zf.read(MANIFEST_NAME).decode("utf-8"))
                except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                    raise BackupError("Invalid backup: corrupt manifest") from exc
                if manifest.get("format") != BACKUP_FORMAT:
                    raise BackupError("Invalid backup: unknown format")
                version = int(manifest.get("version", BACKUP_VERSION))
                created_at = str(manifest.get("created_at", ""))
                include_keys = bool(manifest.get("include_keys", include_keys))
                key_count = int(manifest.get("key_count", key_count))
                host_count = int(manifest.get("host_count", 0))
                keys_encrypted = bool(manifest.get("keys_encrypted", False))
                include_secrets = bool(manifest.get("include_secrets", include_secrets))
                secrets_encrypted = bool(manifest.get("secrets_encrypted", False))
                secret_count = int(manifest.get("secret_count", secret_count))
                if not keys_encrypted and include_keys and key_count:
                    for name in names:
                        if name.startswith(KEYS_PREFIX) and not name.endswith("/"):
                            if is_encrypted_blob(zf.read(name)):
                                keys_encrypted = True
                                break
                if not secrets_encrypted and include_secrets and secret_count:
                    for name in names:
                        if name.startswith(SECRETS_PREFIX) and name.endswith(
                            PASSWORD_SUFFIX
                        ):
                            if is_encrypted_blob(zf.read(name)):
                                secrets_encrypted = True
                                break
            else:
                raw = yaml.safe_load(zf.read(CONFIG_NAME))
                cfg = AppConfig.from_dict(raw)
                host_count = len(cfg.hosts)
                # Detect encryption by scanning blobs when no manifest.
                for name in names:
                    if name.startswith(KEYS_PREFIX) and not name.endswith("/"):
                        if is_encrypted_blob(zf.read(name)):
                            keys_encrypted = True
                    if name.startswith(SECRETS_PREFIX) and name.endswith(PASSWORD_SUFFIX):
                        if is_encrypted_blob(zf.read(name)):
                            secrets_encrypted = True
    except zipfile.BadZipFile as exc:
        raise BackupError("Invalid backup: not a ZIP file") from exc

    return BackupInfo(
        path=source,
        created_at=created_at or "unknown",
        host_count=host_count,
        key_count=key_count,
        include_keys=include_keys,
        keys_encrypted=keys_encrypted,
        include_secrets=include_secrets,
        secrets_encrypted=secrets_encrypted,
        secret_count=secret_count,
        format_version=version,
    )


def restore_backup(
    source: Path,
    *,
    restore_keys: bool = True,
    restore_secrets: bool = True,
    password: str | None = None,
) -> RestoreResult:
    """Replace the current config (and optionally keys/secrets) from a backup ZIP."""
    source = Path(source)
    info = read_backup_info(source)
    ensure_app_dirs()

    needs_password = (restore_keys and info.keys_encrypted) or (
        restore_secrets and info.secrets_encrypted
    )
    if needs_password and not password:
        raise BackupError(
            "Password required to decrypt SSH keys or login passwords in this backup"
        )

    try:
        with zipfile.ZipFile(source, "r") as zf:
            raw = yaml.safe_load(zf.read(CONFIG_NAME))
            cfg = AppConfig.from_dict(raw)

            restored_secrets = 0
            if restore_secrets and info.include_secrets:
                for name in zf.namelist():
                    if not name.startswith(SECRETS_PREFIX) or name.endswith("/"):
                        continue
                    if not name.endswith(PASSWORD_SUFFIX):
                        continue
                    rel = name[len(SECRETS_PREFIX) :]
                    if not _safe_arc_basename(rel):
                        continue
                    host_id = rel[: -len(PASSWORD_SUFFIX)]
                    if not _safe_arc_basename(host_id):
                        continue
                    blob = zf.read(name)
                    if is_encrypted_blob(blob):
                        data = decrypt_bytes(blob, password or "")
                    else:
                        data = blob
                    secret_text = data.decode("utf-8")
                    for host in cfg.hosts:
                        if host.id == host_id:
                            host.password = secret_text
                            restored_secrets += 1
                            break

            # Persist config + passwords together so secrets are not wiped.
            save_config(cfg)

            restored_keys = 0
            if restore_keys and info.include_keys:
                keys = keys_dir()
                keys.mkdir(mode=0o700, parents=True, exist_ok=True)
                for name in zf.namelist():
                    if not name.startswith(KEYS_PREFIX) or name.endswith("/"):
                        continue
                    rel = name[len(KEYS_PREFIX) :]
                    if not _safe_arc_basename(rel):
                        continue
                    blob = zf.read(name)
                    if is_encrypted_blob(blob):
                        data = decrypt_bytes(blob, password or "")
                    else:
                        data = blob
                    target = keys / rel
                    target.write_bytes(data)
                    try:
                        if rel.endswith(".pub"):
                            target.chmod(0o644)
                        else:
                            target.chmod(0o600)
                    except OSError:
                        pass
                    restored_keys += 1
    except BackupError:
        raise
    except (OSError, zipfile.BadZipFile, yaml.YAMLError, UnicodeDecodeError) as exc:
        raise BackupError(f"Could not restore backup: {exc}") from exc

    return RestoreResult(
        host_count=len(cfg.hosts),
        key_count=restored_keys,
        include_keys=restore_keys and info.include_keys,
        secret_count=restored_secrets,
        include_secrets=restore_secrets and info.include_secrets,
    )
