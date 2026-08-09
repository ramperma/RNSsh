"""Data models for hosts and key references."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


UNGROUPED = ""


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
    group: str = UNGROUPED
    # Android parity: attach/create named tmux session on connect.
    persistent_session: bool = True
    # In-memory / secrets-dir only — never written to config.yaml.
    password: str = field(default="", repr=False)

    @property
    def target(self) -> str:
        return f"{self.user}@{self.hostname}:{self.port}"

    def mark_connected(self) -> None:
        self.last_connected = _utc_now_iso()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data.pop("password", None)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Host:
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {k: v for k, v in data.items() if k in known}
        # Passwords belong in secrets/, never in YAML.
        filtered.pop("password", None)
        if "port" in filtered:
            filtered["port"] = int(filtered["port"])
        if "group" in filtered and filtered["group"] is None:
            filtered["group"] = UNGROUPED
        elif "group" in filtered:
            filtered["group"] = str(filtered["group"]).strip()
        if "persistent_session" in filtered:
            filtered["persistent_session"] = bool(filtered["persistent_session"])
        return cls(**filtered)


@dataclass
class AppConfig:
    """Top-level persisted configuration."""

    hosts: list[Host] = field(default_factory=list)
    groups: list[str] = field(default_factory=list)
    default_key_name: str = "default"
    language: str = "en"

    def to_dict(self) -> dict[str, Any]:
        return {
            "default_key_name": self.default_key_name,
            "language": self.language,
            "groups": list(self.groups),
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
        groups_raw = data.get("groups") or []
        groups = [str(g).strip() for g in groups_raw if str(g).strip()]
        # Ensure groups referenced by hosts appear in the list.
        seen = set(groups)
        for host in hosts:
            g = (host.group or "").strip()
            host.group = g
            if g and g not in seen:
                groups.append(g)
                seen.add(g)
        return cls(
            hosts=hosts,
            groups=groups,
            default_key_name=data.get("default_key_name", "default"),
            language=language,
        )

    def get_host(self, host_id: str) -> Host | None:
        for host in self.hosts:
            if host.id == host_id:
                return host
        return None

    def upsert_host(self, host: Host) -> None:
        host.group = (host.group or "").strip()
        if host.group:
            self.ensure_group(host.group)
        for i, existing in enumerate(self.hosts):
            if existing.id == host.id:
                self.hosts[i] = host
                return
        self.hosts.append(host)

    def remove_host(self, host_id: str) -> bool:
        before = len(self.hosts)
        self.hosts = [h for h in self.hosts if h.id != host_id]
        return len(self.hosts) < before

    def ensure_group(self, name: str) -> str:
        name = name.strip()
        if name and name not in self.groups:
            self.groups.append(name)
        return name

    def rename_group(self, old: str, new: str) -> None:
        old = old.strip()
        new = new.strip()
        if not old or old == new:
            return
        self.groups = [new if g == old else g for g in self.groups]
        # Dedupe while preserving order
        seen: set[str] = set()
        deduped: list[str] = []
        for g in self.groups:
            if g and g not in seen:
                deduped.append(g)
                seen.add(g)
        self.groups = deduped
        for host in self.hosts:
            if host.group == old:
                host.group = new

    def delete_group(self, name: str, *, reassign_to: str = UNGROUPED) -> None:
        name = name.strip()
        self.groups = [g for g in self.groups if g != name]
        for host in self.hosts:
            if host.group == name:
                host.group = reassign_to.strip()

    def known_groups(self) -> list[str]:
        """Return ordered group names (configured + used by hosts)."""
        seen: set[str] = set()
        result: list[str] = []
        for g in self.groups:
            g = g.strip()
            if g and g not in seen:
                result.append(g)
                seen.add(g)
        for host in self.hosts:
            g = (host.group or "").strip()
            if g and g not in seen:
                result.append(g)
                seen.add(g)
        return result

    def hosts_by_group(self) -> list[tuple[str, list[Host]]]:
        """Return ``(group_name, hosts)`` with configured order; ungrouped last.

        Named groups are always included (even when empty) so newly created
        groups are visible in the UI before hosts are assigned.
        """
        buckets: dict[str, list[Host]] = {g: [] for g in self.known_groups()}
        ungrouped: list[Host] = []
        for host in self.hosts:
            g = (host.group or "").strip()
            if not g:
                ungrouped.append(host)
            else:
                buckets.setdefault(g, []).append(host)
        result = [(name, hosts) for name, hosts in buckets.items()]
        if ungrouped:
            result.append((UNGROUPED, ungrouped))
        return result

    def set_host_group(self, host_id: str, group: str) -> Host | None:
        """Assign ``host_id`` to ``group`` (empty string = ungrouped)."""
        host = self.get_host(host_id)
        if host is None:
            return None
        group = (group or "").strip()
        host.group = group
        if group:
            self.ensure_group(group)
        return host
