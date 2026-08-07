"""Data models for hosts and key references."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


@dataclass
class Host:
    """A managed SSH host entry."""

    name: str
    hostname: str
    user: str = "root"
    port: int = 22
    id: str = field(default_factory=lambda: uuid4().hex)
    jump_host: str | None = None
    tmux_session: str = "rnssh"
    notes: str = ""
    key_name: str | None = None
    provisioned: bool = False
    last_connected: str | None = None
    agent_forwarding: bool = False

    @property
    def target(self) -> str:
        return f"{self.user}@{self.hostname}:{self.port}"

    def mark_connected(self) -> None:
        self.last_connected = _utc_now_iso()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Host:
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known}
        if "port" in filtered:
            filtered["port"] = int(filtered["port"])
        return cls(**filtered)


@dataclass
class AppConfig:
    """Top-level persisted configuration."""

    hosts: list[Host] = field(default_factory=list)
    default_key_name: str = "default"
    language: str = "en"

    def to_dict(self) -> dict[str, Any]:
        return {
            "default_key_name": self.default_key_name,
            "language": self.language,
            "hosts": [h.to_dict() for h in self.hosts],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> AppConfig:
        if not data:
            return cls()
        hosts = [Host.from_dict(h) for h in data.get("hosts", [])]
        language = data.get("language", "en")
        if language not in ("en", "es"):
            language = "en"
        return cls(
            hosts=hosts,
            default_key_name=data.get("default_key_name", "default"),
            language=language,
        )

    def get_host(self, host_id: str) -> Host | None:
        for host in self.hosts:
            if host.id == host_id:
                return host
        return None

    def upsert_host(self, host: Host) -> None:
        for i, existing in enumerate(self.hosts):
            if existing.id == host.id:
                self.hosts[i] = host
                return
        self.hosts.append(host)

    def remove_host(self, host_id: str) -> bool:
        before = len(self.hosts)
        self.hosts = [h for h in self.hosts if h.id != host_id]
        return len(self.hosts) < before
