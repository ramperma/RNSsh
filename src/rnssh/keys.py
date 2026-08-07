"""Ed25519 SSH key generation and loading."""

from __future__ import annotations

import os
import re
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from rnssh.paths import ensure_app_dirs, keys_dir

_SAFE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


class SSHKeyError(Exception):
    """Raised when a key cannot be created or loaded safely."""


def _validate_name(name: str) -> str:
    if not name or not _SAFE_NAME.match(name):
        raise SSHKeyError(
            f"Invalid key name {name!r}: use letters, digits, '.', '_' or '-'"
        )
    return name


def private_key_path(name: str) -> Path:
    return keys_dir() / _validate_name(name)


def public_key_path(name: str) -> Path:
    return keys_dir() / f"{_validate_name(name)}.pub"


def key_exists(name: str) -> bool:
    return private_key_path(name).is_file() and public_key_path(name).is_file()


def generate_ed25519_keypair(name: str, *, comment: str | None = None) -> Path:
    """Generate an OpenSSH Ed25519 key pair under the keys directory.

    Returns the path to the private key.
    """
    ensure_app_dirs()
    name = _validate_name(name)
    priv_path = private_key_path(name)
    pub_path = public_key_path(name)
    if priv_path.exists() or pub_path.exists():
        raise SSHKeyError(f"Key already exists: {name}")

    private_key = Ed25519PrivateKey.generate()
    comment = comment or f"rnssh-{name}"

    private_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.OpenSSH,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.OpenSSH,
        format=serialization.PublicFormat.OpenSSH,
    )
    public_line = public_bytes.decode("utf-8") + f" {comment}\n"

    priv_path.write_bytes(private_bytes)
    pub_path.write_text(public_line, encoding="utf-8")
    try:
        os.chmod(priv_path, 0o600)
        os.chmod(pub_path, 0o644)
    except OSError:
        pass

    if not _is_private_key_safe(priv_path):
        priv_path.unlink(missing_ok=True)
        pub_path.unlink(missing_ok=True)
        raise SSHKeyError(f"Refusing world-readable private key at {priv_path}")

    return priv_path


def ensure_keypair(name: str, *, comment: str | None = None) -> Path:
    """Return existing private key path or generate a new pair."""
    if key_exists(name):
        path = private_key_path(name)
        if not _is_private_key_safe(path):
            raise SSHKeyError(f"Private key permissions too open: {path}")
        return path
    return generate_ed25519_keypair(name, comment=comment)


def read_public_key(name: str) -> str:
    path = public_key_path(name)
    if not path.is_file():
        raise SSHKeyError(f"Public key not found: {name}")
    return path.read_text(encoding="utf-8").strip()


def _is_private_key_safe(path: Path) -> bool:
    try:
        mode = path.stat().st_mode & 0o777
    except OSError:
        return False
    # Refuse group/other read/write/execute
    return (mode & 0o077) == 0
