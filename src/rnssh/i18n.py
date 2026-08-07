"""Simple English / Spanish translations for the UI."""

from __future__ import annotations

from typing import Any

SUPPORTED_LANGUAGES = ("en", "es")
DEFAULT_LANGUAGE = "en"

LANGUAGE_LABELS = {
    "en": "English",
    "es": "Español",
}

_STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "app.title": "RNSsh — SSH Connection Manager",
        "app.brand": "RNSsh",
        "app.subtitle": "Right-click a connection for actions · menus above for Host, Connection, Language",
        "toolbar.main": "Main",
        "action.add": "Add",
        "action.edit": "Edit",
        "action.delete": "Delete",
        "action.provision": "Provision keys",
        "action.connect_tmux": "Connect (tmux)",
        "action.connect_plain": "Connect (plain SSH)",
        "action.connect_plain_short": "Connect (plain)",
        "action.list_sessions": "List tmux sessions",
        "action.list_sessions_short": "List sessions",
        "action.delete_tmux": "Delete tmux session…",
        "action.close_terminal": "Close terminal window",
        "action.refresh": "Refresh",
        "menu.host": "Host",
        "menu.connection": "Connection",
        "menu.language": "Language",
        "group.hosts": "HOSTS",
        "group.session": "SESSION",
        "empty.hint": "No hosts yet — use Host → Add, or right-click here.",
        "col.name": "Name",
        "col.target": "Target",
        "col.key_status": "Key status",
        "col.tmux": "Tmux session",
        "col.last": "Last connected",
        "status.ready": "Ready",
        "status.hosts_count": "{count} host(s)",
        "status.added": "Added {name}",
        "status.updated": "Updated {name}",
        "status.deleted": "Deleted {name}",
        "status.provisioning": "Provisioning {name}…",
        "status.provisioned": "Provisioned {name}",
        "status.provision_failed": "Provision failed: {message}",
        "status.launched": "Launched {mode} for {name} (pid {pid})",
        "status.listing_sessions": "Listing tmux sessions on {name}…",
        "status.no_sessions": "No remote tmux sessions",
        "status.deleting_session": "Deleting tmux session “{session}” on {name}…",
        "status.deleted_session": "Deleted tmux session “{session}” on {name}",
        "status.terminated": "Sent terminate to pid {pid} for {name}",
        "key.provisioned": "provisioned",
        "key.not_provisioned": "not provisioned",
        "mode.tmux": "tmux",
        "mode.plain": "plain SSH",
        "dialog.no_selection": "No selection",
        "msg.select_edit": "Select a host to edit.",
        "msg.select_delete": "Select a host to delete.",
        "msg.select_provision": "Select a host to provision.",
        "msg.select_connect": "Select a host to connect.",
        "msg.select_first": "Select a host first.",
        "msg.select_host": "Select a host.",
        "dialog.delete_host": "Delete host",
        "msg.delete_confirm": "Delete host “{name}”? Keys on disk are kept.",
        "dialog.jump_host": "Jump host",
        "msg.jump_unsupported": "Automatic key provisioning via jump host is not supported in v1.",
        "dialog.provisioned": "Provisioned",
        "msg.provision_ok": (
            "Key “{key_name}” {state}.\n"
            "Host key ({key_type}): {fingerprint}\n"
            "You can now Connect with key authentication."
        ),
        "key.state.already": "already present",
        "key.state.installed": "installed",
        "dialog.provision_failed": "Provision failed",
        "dialog.not_provisioned": "Not provisioned",
        "msg.connect_anyway": "This host has not been provisioned yet. Connect anyway?",
        "dialog.terminal_error": "Terminal error",
        "msg.provision_before_list": "Provision keys before listing sessions.",
        "msg.provision_before_delete": "Provision keys before deleting tmux sessions.",
        "dialog.tmux_sessions": "Tmux sessions",
        "msg.no_tmux_sessions": (
            "No tmux sessions on {name}.\n"
            "Connect (tmux) will create “{session}”."
        ),
        "msg.attach_session": "Attach to session on {name}:",
        "msg.kill_session_pick": "Delete which tmux session on {name}?",
        "dialog.list_sessions_failed": "List sessions failed",
        "dialog.delete_tmux": "Delete tmux session",
        "msg.delete_tmux_confirm": (
            "Permanently kill remote tmux session “{session}” on {name}?\n"
            "Running work in that session will be lost."
        ),
        "msg.no_sessions_kill_default": (
            "No remote tmux sessions listed on {name}.\n"
            "Try to kill the configured session “{session}” anyway?"
        ),
        "dialog.delete_tmux_failed": "Delete tmux session failed",
        "dialog.no_tracked": "No tracked window",
        "msg.no_tracked": (
            "No local terminal window PID tracked for this host in this app session.\n"
            "This does not remove the remote tmux session — use Delete tmux session… for that.\n"
            "Detach inside tmux with Ctrl-b d, or close the terminal window manually."
        ),
        "host.add_title": "Add host",
        "host.edit_title": "Edit host",
        "host.name": "Name",
        "host.hostname": "Hostname",
        "host.user": "User",
        "host.port": "Port",
        "host.jump": "Jump host",
        "host.tmux": "Tmux session",
        "host.key_name": "Key name",
        "host.notes": "Notes",
        "host.jump_placeholder": "optional user@host:port",
        "host.key_placeholder": "auto from host name if empty",
        "host.agent": "Enable SSH agent forwarding (-A)",
        "host.missing_title": "Missing fields",
        "host.missing_msg": "Name, hostname, and user are required.",
        "provision.title": "Provision keys — {name}",
        "provision.info": (
            "Install an SSH key on <b>{target}</b>.\n"
            "The password is used once and never stored."
        ),
        "provision.password": "Password",
        "provision.password_required": "Password required",
        "provision.password_msg": "Enter the SSH password to install the key.",
        "lang.changed": "Language set to {label}",
    },
    "es": {
        "app.title": "RNSsh — Gestor de conexiones SSH",
        "app.brand": "RNSsh",
        "app.subtitle": "Clic derecho en una conexión para acciones · menús Host, Conexión e Idioma arriba",
        "toolbar.main": "Principal",
        "action.add": "Añadir",
        "action.edit": "Editar",
        "action.delete": "Eliminar",
        "action.provision": "Provisionar claves",
        "action.connect_tmux": "Conectar (tmux)",
        "action.connect_plain": "Conectar (SSH simple)",
        "action.connect_plain_short": "Conectar (simple)",
        "action.list_sessions": "Listar sesiones tmux",
        "action.list_sessions_short": "Listar sesiones",
        "action.delete_tmux": "Eliminar sesión tmux…",
        "action.close_terminal": "Cerrar ventana del terminal",
        "action.refresh": "Actualizar",
        "menu.host": "Host",
        "menu.connection": "Conexión",
        "menu.language": "Idioma",
        "group.hosts": "HOSTS",
        "group.session": "SESIÓN",
        "empty.hint": "Aún no hay hosts — use Host → Añadir, o clic derecho aquí.",
        "col.name": "Nombre",
        "col.target": "Destino",
        "col.key_status": "Estado de clave",
        "col.tmux": "Sesión tmux",
        "col.last": "Última conexión",
        "status.ready": "Listo",
        "status.hosts_count": "{count} host(s)",
        "status.added": "Añadido {name}",
        "status.updated": "Actualizado {name}",
        "status.deleted": "Eliminado {name}",
        "status.provisioning": "Provisionando {name}…",
        "status.provisioned": "Provisionado {name}",
        "status.provision_failed": "Falló la provisión: {message}",
        "status.launched": "Lanzado {mode} para {name} (pid {pid})",
        "status.listing_sessions": "Listando sesiones tmux en {name}…",
        "status.no_sessions": "No hay sesiones tmux remotas",
        "status.deleting_session": "Eliminando sesión tmux “{session}” en {name}…",
        "status.deleted_session": "Sesión tmux “{session}” eliminada en {name}",
        "status.terminated": "Señal de cierre enviada al pid {pid} de {name}",
        "key.provisioned": "provisionada",
        "key.not_provisioned": "sin provisionar",
        "mode.tmux": "tmux",
        "mode.plain": "SSH simple",
        "dialog.no_selection": "Sin selección",
        "msg.select_edit": "Seleccione un host para editar.",
        "msg.select_delete": "Seleccione un host para eliminar.",
        "msg.select_provision": "Seleccione un host para provisionar.",
        "msg.select_connect": "Seleccione un host para conectar.",
        "msg.select_first": "Seleccione un host primero.",
        "msg.select_host": "Seleccione un host.",
        "dialog.delete_host": "Eliminar host",
        "msg.delete_confirm": "¿Eliminar el host “{name}”? Las claves en disco se conservan.",
        "dialog.jump_host": "Host salto",
        "msg.jump_unsupported": "La provisión automática de claves vía jump host no está soportada en v1.",
        "dialog.provisioned": "Provisionado",
        "msg.provision_ok": (
            "Clave “{key_name}” {state}.\n"
            "Clave de host ({key_type}): {fingerprint}\n"
            "Ya puede Conectar con autenticación por clave."
        ),
        "key.state.already": "ya presente",
        "key.state.installed": "instalada",
        "dialog.provision_failed": "Falló la provisión",
        "dialog.not_provisioned": "Sin provisionar",
        "msg.connect_anyway": "Este host aún no está provisionado. ¿Conectar de todos modos?",
        "dialog.terminal_error": "Error de terminal",
        "msg.provision_before_list": "Provisionar claves antes de listar sesiones.",
        "msg.provision_before_delete": "Provisionar claves antes de eliminar sesiones tmux.",
        "dialog.tmux_sessions": "Sesiones tmux",
        "msg.no_tmux_sessions": (
            "No hay sesiones tmux en {name}.\n"
            "Conectar (tmux) creará “{session}”."
        ),
        "msg.attach_session": "Adjuntar a sesión en {name}:",
        "msg.kill_session_pick": "¿Qué sesión tmux eliminar en {name}?",
        "dialog.list_sessions_failed": "Error al listar sesiones",
        "dialog.delete_tmux": "Eliminar sesión tmux",
        "msg.delete_tmux_confirm": (
            "¿Eliminar permanentemente la sesión tmux remota “{session}” en {name}?\n"
            "Se perderá el trabajo en curso de esa sesión."
        ),
        "msg.no_sessions_kill_default": (
            "No hay sesiones tmux remotas listadas en {name}.\n"
            "¿Intentar eliminar de todos modos la sesión configurada “{session}”?"
        ),
        "dialog.delete_tmux_failed": "Error al eliminar sesión tmux",
        "dialog.no_tracked": "Sin ventana registrada",
        "msg.no_tracked": (
            "No hay PID de ventana de terminal local registrado para este host en esta sesión de la app.\n"
            "Esto no elimina la sesión tmux remota — use Eliminar sesión tmux… para eso.\n"
            "Desconecte dentro de tmux con Ctrl-b d, o cierre la ventana del terminal manualmente."
        ),
        "host.add_title": "Añadir host",
        "host.edit_title": "Editar host",
        "host.name": "Nombre",
        "host.hostname": "Hostname",
        "host.user": "Usuario",
        "host.port": "Puerto",
        "host.jump": "Host salto",
        "host.tmux": "Sesión tmux",
        "host.key_name": "Nombre de clave",
        "host.notes": "Notas",
        "host.jump_placeholder": "opcional usuario@host:puerto",
        "host.key_placeholder": "automático desde el nombre si está vacío",
        "host.agent": "Activar reenvío del agente SSH (-A)",
        "host.missing_title": "Campos incompletos",
        "host.missing_msg": "Nombre, hostname y usuario son obligatorios.",
        "provision.title": "Provisionar claves — {name}",
        "provision.info": (
            "Instalar una clave SSH en <b>{target}</b>.\n"
            "La contraseña se usa una sola vez y nunca se guarda."
        ),
        "provision.password": "Contraseña",
        "provision.password_required": "Contraseña requerida",
        "provision.password_msg": "Introduzca la contraseña SSH para instalar la clave.",
        "lang.changed": "Idioma establecido a {label}",
    },
}

_current_language = DEFAULT_LANGUAGE


def normalize_language(code: str | None) -> str:
    if not code:
        return DEFAULT_LANGUAGE
    code = code.lower().strip()
    if code.startswith("es"):
        return "es"
    if code.startswith("en"):
        return "en"
    return DEFAULT_LANGUAGE


def get_language() -> str:
    return _current_language


def set_language(code: str) -> str:
    global _current_language
    _current_language = normalize_language(code)
    return _current_language


def t(key: str, **kwargs: Any) -> str:
    """Translate ``key`` for the current language, falling back to English."""
    lang = _current_language
    catalog = _STRINGS.get(lang) or _STRINGS[DEFAULT_LANGUAGE]
    text = catalog.get(key)
    if text is None:
        text = _STRINGS[DEFAULT_LANGUAGE].get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, ValueError):
            return text
    return text


def available_languages() -> list[tuple[str, str]]:
    """Return ``(code, label)`` pairs."""
    return [(code, LANGUAGE_LABELS[code]) for code in SUPPORTED_LANGUAGES]
