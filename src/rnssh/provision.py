"""Password bootstrap: install public key on remote host and verify key auth."""

from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from pathlib import Path

import paramiko

from rnssh import keys as keymod
from rnssh.models import Host


class ProvisionError(Exception):
    """Key provisioning failed."""


@dataclass
class HostKeyInfo:
    key_type: str
    fingerprint_sha256: str


@dataclass
class ProvisionResult:
    host_key: HostKeyInfo
    key_name: str
    already_present: bool


def _fingerprint_sha256(key: paramiko.PKey) -> str:
    digest = hashlib.sha256(key.asbytes()).digest()
    # OpenSSH-style fingerprint without trailing '=' padding noise
    b64 = base64.b64encode(digest).decode("ascii").rstrip("=")
    return f"SHA256:{b64}"


def get_remote_host_key(host: Host, password: str, *, timeout: float = 20) -> HostKeyInfo:
    """Connect with password and return the server host key fingerprint."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=host.hostname,
            port=host.port,
            username=host.user,
            password=password,
            allow_agent=False,
            look_for_keys=False,
            timeout=timeout,
        )
        transport = client.get_transport()
        if transport is None:
            raise ProvisionError("No SSH transport after connect")
        remote_key = transport.get_remote_server_key()
        return HostKeyInfo(
            key_type=remote_key.get_name(),
            fingerprint_sha256=_fingerprint_sha256(remote_key),
        )
    except paramiko.AuthenticationException as exc:
        raise ProvisionError("Authentication failed — check username/password") from exc
    except Exception as exc:  # noqa: BLE001 — surface as provision error
        raise ProvisionError(str(exc)) from exc
    finally:
        client.close()


def provision_host(
    host: Host,
    password: str,
    *,
    key_name: str | None = None,
    accept_host_key: bool = True,
    timeout: float = 20,
) -> ProvisionResult:
    """Generate (if needed) a key pair, install the public key, verify key login.

    Password is used only in memory for this call.
    """
    if host.jump_host:
        raise ProvisionError("Automatic key provisioning via jump host is not supported in v1")

    name = key_name or host.key_name or host.name.replace(" ", "-").lower()
    # Sanitize for key filename
    safe = "".join(c if c.isalnum() or c in "._-" else "-" for c in name).strip("-") or "default"
    priv_path = keymod.ensure_keypair(safe, comment=f"rnssh@{host.hostname}")
    pubkey = keymod.read_public_key(safe)

    client = paramiko.SSHClient()
    policy = paramiko.AutoAddPolicy() if accept_host_key else paramiko.RejectPolicy()
    client.set_missing_host_key_policy(policy)

    host_key_info: HostKeyInfo | None = None
    try:
        client.connect(
            hostname=host.hostname,
            port=host.port,
            username=host.user,
            password=password,
            allow_agent=False,
            look_for_keys=False,
            timeout=timeout,
        )
        transport = client.get_transport()
        if transport is None:
            raise ProvisionError("No SSH transport after connect")
        remote_key = transport.get_remote_server_key()
        host_key_info = HostKeyInfo(
            key_type=remote_key.get_name(),
            fingerprint_sha256=_fingerprint_sha256(remote_key),
        )

        already = _pubkey_present(client, pubkey)
        if not already:
            _install_pubkey(client, pubkey)
    except paramiko.AuthenticationException as exc:
        raise ProvisionError("Authentication failed — check username/password") from exc
    except ProvisionError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ProvisionError(str(exc)) from exc
    finally:
        client.close()

    # Verify key-based login works
    _verify_key_auth(host, priv_path, timeout=timeout)

    return ProvisionResult(
        host_key=host_key_info,  # type: ignore[arg-type]
        key_name=safe,
        already_present=already,
    )


def _pubkey_present(client: paramiko.SSHClient, pubkey: str) -> bool:
    key_body = pubkey.split()[1] if len(pubkey.split()) >= 2 else pubkey
    cmd = "mkdir -p ~/.ssh && chmod 700 ~/.ssh && touch ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && cat ~/.ssh/authorized_keys"
    _stdin, stdout, _stderr = client.exec_command(cmd, timeout=30)
    content = stdout.read().decode("utf-8", errors="replace")
    return key_body in content


def _install_pubkey(client: paramiko.SSHClient, pubkey: str) -> None:
    # Append via a quoted heredoc-safe approach using printf
    line = pubkey.strip() + "\n"
    # Use base64 to avoid shell escaping issues
    b64 = base64.b64encode(line.encode("utf-8")).decode("ascii")
    script = (
        "mkdir -p ~/.ssh && chmod 700 ~/.ssh && "
        "touch ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys && "
        f"echo {b64} | base64 -d >> ~/.ssh/authorized_keys"
    )
    _stdin, stdout, stderr = client.exec_command(script, timeout=30)
    code = stdout.channel.recv_exit_status()
    if code != 0:
        err = stderr.read().decode("utf-8", errors="replace")
        raise ProvisionError(f"Failed to install public key: {err or f'exit {code}'}")


def _verify_key_auth(host: Host, priv_path: Path, *, timeout: float = 20) -> None:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        client.connect(
            hostname=host.hostname,
            port=host.port,
            username=host.user,
            key_filename=str(priv_path),
            allow_agent=False,
            look_for_keys=False,
            timeout=timeout,
        )
        _stdin, stdout, _stderr = client.exec_command("echo rnssh-ok", timeout=15)
        out = stdout.read().decode("utf-8", errors="replace").strip()
        if "rnssh-ok" not in out:
            raise ProvisionError("Key installed but verification command failed")
    except paramiko.AuthenticationException as exc:
        raise ProvisionError(
            "Public key was written but key-based login still fails "
            "(check PermitRootLogin / AuthorizedKeysFile)"
        ) from exc
    except ProvisionError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise ProvisionError(f"Key verification failed: {exc}") from exc
    finally:
        client.close()
