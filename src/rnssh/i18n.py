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
        "app.subtitle": "Right-click a connection for actions · Settings tab for backup & restore",
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
        "action.manage_groups": "Manage groups…",
        "menu.host": "Host",
        "menu.connection": "Connection",
        "menu.language": "Language",
        "tab.hosts": "Hosts",
        "tab.settings": "Settings",
        "settings.backup_title": "Backup & restore",
        "settings.backup_help": (
            "Export your host list (and optionally SSH keys and login passwords) to a ZIP file, "
            "or restore them from a previous backup. Keys and passwords are encrypted "
            "with a password (AES-256-GCM). Restoring replaces the current connections."
        ),
        "settings.summary": "Current data: {hosts} host(s), {keys} key file(s).",
        "settings.include_keys": (
            "Include / restore SSH keys and login passwords (encrypted with password)"
        ),
        "settings.backup_export": "Create backup…",
        "settings.backup_restore": "Restore backup…",
        "settings.backup_export_title": "Save backup",
        "settings.backup_restore_title": "Open backup",
        "settings.backup_filter": "RNSsh backup (*.zip)",
        "settings.backup_failed": "Backup failed",
        "settings.backup_failed_status": "Backup failed: {message}",
        "settings.backup_done_title": "Backup created",
        "settings.backup_done": (
            "Backup saved to:\n{path}\n\n"
            "Hosts: {hosts}\nKey files: {keys}\nLogin passwords: {secrets}\n\n"
            "SSH keys and login passwords (if included) are password-encrypted. "
            "Remember the password — it cannot be recovered."
        ),
        "settings.backup_done_status": "Backup saved ({hosts} host(s)): {path}",
        "settings.restore_confirm_title": "Restore backup?",
        "settings.restore_confirm": (
            "Restore from:\n{path}\n\n"
            "Created: {created}\nHosts in backup: {hosts}\nKey files: {keys}\n"
            "Login passwords: {secrets}\n"
            "{encrypted_note}\n"
            "This will replace your current connections."
        ),
        "settings.restore_encrypted_note": (
            "Keys and/or login passwords in this backup are encrypted — "
            "you will be asked for the password."
        ),
        "settings.restore_failed": "Restore failed",
        "settings.restore_failed_status": "Restore failed: {message}",
        "settings.restore_done_title": "Backup restored",
        "settings.restore_done": (
            "Restored {hosts} host(s), {keys} key file(s), "
            "and {secrets} login password(s).\n"
            "The hosts list has been reloaded."
        ),
        "settings.restore_done_status": (
            "Restored {hosts} host(s), {keys} key file(s), {secrets} password(s)"
        ),
        "settings.password_title": "Backup password",
        "settings.password_prompt": "Enter the backup password.",
        "settings.password_prompt_create": (
            "Choose a password to encrypt SSH keys and login passwords in this backup.\n"
            "You will need the same password to restore them."
        ),
        "settings.password_prompt_restore": (
            "Enter the password used when this backup was created."
        ),
        "settings.password": "Password",
        "settings.password_confirm": "Confirm password",
        "settings.password_required_title": "Password required",
        "settings.password_required": "Enter a password.",
        "settings.password_mismatch_title": "Passwords do not match",
        "settings.password_mismatch": "The two passwords must be the same.",
        "settings.password_weak_title": "Password too short",
        "settings.password_weak": "Use at least 8 characters.",
        "settings.paths_title": "Data locations",
        "settings.paths_body": (
            "Config file:\n{config}\n\n"
            "SSH keys:\n{keys}\n\n"
            "App data directory:\n{data}"
        ),
        "group.hosts": "HOSTS",
        "group.session": "SESSION",
        "group.header": "{name} ({count})",
        "group.ungrouped": "Ungrouped ({count})",
        "groups.title": "Connection groups",
        "groups.help": (
            "Create groups here, then assign hosts with “Assign hosts…”, "
            "or use right-click → Move to group, or set the group when editing a host."
        ),
        "groups.add": "Add group",
        "groups.rename": "Rename",
        "groups.delete": "Delete",
        "groups.assign": "Assign hosts…",
        "groups.assign_title": "Assign hosts to “{name}”",
        "groups.assign_help": (
            "Check the connections that should belong to “{name}”. "
            "Unchecked hosts currently in this group will become ungrouped."
        ),
        "groups.assign_no_hosts": "There are no connections to assign yet. Add a host first.",
        "groups.name_prompt": "Group name:",
        "groups.item": "{name} — {count} host(s)",
        "groups.exists": "Group “{name}” already exists.",
        "groups.select_first": "Select a group first.",
        "groups.delete_confirm": (
            "Delete group “{name}”?\n"
            "{count} host(s) will move to Ungrouped."
        ),
        "status.groups_updated": "Groups updated",
        "action.move_to_group": "Move to group",
        "action.ungroup": "Ungrouped",
        "status.moved_group": "Moved “{name}” to {group}",
        "status.ungrouped": "Removed “{name}” from its group",
        "host.group": "Group",
        "host.group_placeholder": "optional — type a new group name",
        "dialog.connection_failed": "Connection failed",
        "msg.connection_failed": (
            "Connection to “{name}” failed (exit code {code}).\n\n"
            "The terminal stayed open so you could see the SSH error.\n"
            "Check host, port, key, and network, then try again."
        ),
        "status.connection_failed": "Connection to {name} failed (exit {code})",
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
        "app.subtitle": "Clic derecho en una conexión para acciones · pestaña Configuración para copia y restauración",
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
        "action.manage_groups": "Gestionar grupos…",
        "menu.host": "Host",
        "menu.connection": "Conexión",
        "menu.language": "Idioma",
        "tab.hosts": "Hosts",
        "tab.settings": "Configuración",
        "settings.backup_title": "Copia de seguridad y recuperación",
        "settings.backup_help": (
            "Exporte la lista de hosts (y opcionalmente las claves SSH y contraseñas de acceso) "
            "a un ZIP, o restáurelos desde una copia anterior. Claves y contraseñas se cifran "
            "con una contraseña (AES-256-GCM). La restauración sustituye las conexiones actuales."
        ),
        "settings.summary": "Datos actuales: {hosts} host(s), {keys} archivo(s) de clave.",
        "settings.include_keys": (
            "Incluir / restaurar claves SSH y contraseñas de acceso (cifradas con contraseña)"
        ),
        "settings.backup_export": "Crear copia…",
        "settings.backup_restore": "Restaurar copia…",
        "settings.backup_export_title": "Guardar copia de seguridad",
        "settings.backup_restore_title": "Abrir copia de seguridad",
        "settings.backup_filter": "Copia RNSsh (*.zip)",
        "settings.backup_failed": "Falló la copia",
        "settings.backup_failed_status": "Falló la copia: {message}",
        "settings.backup_done_title": "Copia creada",
        "settings.backup_done": (
            "Copia guardada en:\n{path}\n\n"
            "Hosts: {hosts}\nArchivos de clave: {keys}\nContraseñas de acceso: {secrets}\n\n"
            "Las claves SSH y contraseñas (si se incluyen) van cifradas con contraseña. "
            "Recuerde la contraseña: no se puede recuperar."
        ),
        "settings.backup_done_status": "Copia guardada ({hosts} host(s)): {path}",
        "settings.restore_confirm_title": "¿Restaurar copia?",
        "settings.restore_confirm": (
            "Restaurar desde:\n{path}\n\n"
            "Creada: {created}\nHosts en la copia: {hosts}\nArchivos de clave: {keys}\n"
            "Contraseñas de acceso: {secrets}\n"
            "{encrypted_note}\n"
            "Esto sustituirá sus conexiones actuales."
        ),
        "settings.restore_encrypted_note": (
            "Las claves y/o contraseñas de esta copia están cifradas: "
            "se pedirá la contraseña."
        ),
        "settings.restore_failed": "Falló la restauración",
        "settings.restore_failed_status": "Falló la restauración: {message}",
        "settings.restore_done_title": "Copia restaurada",
        "settings.restore_done": (
            "Se restauraron {hosts} host(s), {keys} archivo(s) de clave "
            "y {secrets} contraseña(s) de acceso.\n"
            "La lista de hosts se ha recargado."
        ),
        "settings.restore_done_status": (
            "Restaurados {hosts} host(s), {keys} archivo(s) de clave, {secrets} contraseña(s)"
        ),
        "settings.password_title": "Contraseña de la copia",
        "settings.password_prompt": "Introduzca la contraseña de la copia.",
        "settings.password_prompt_create": (
            "Elija una contraseña para cifrar las claves SSH y contraseñas de acceso "
            "de esta copia.\n"
            "Necesitará la misma contraseña para restaurarlas."
        ),
        "settings.password_prompt_restore": (
            "Introduzca la contraseña usada al crear esta copia."
        ),
        "settings.password": "Contraseña",
        "settings.password_confirm": "Confirmar contraseña",
        "settings.password_required_title": "Contraseña requerida",
        "settings.password_required": "Introduzca una contraseña.",
        "settings.password_mismatch_title": "Las contraseñas no coinciden",
        "settings.password_mismatch": "Las dos contraseñas deben ser iguales.",
        "settings.password_weak_title": "Contraseña demasiado corta",
        "settings.password_weak": "Use al menos 8 caracteres.",
        "settings.paths_title": "Ubicaciones de datos",
        "settings.paths_body": (
            "Archivo de configuración:\n{config}\n\n"
            "Claves SSH:\n{keys}\n\n"
            "Directorio de datos:\n{data}"
        ),
        "group.hosts": "HOSTS",
        "group.session": "SESIÓN",
        "group.header": "{name} ({count})",
        "group.ungrouped": "Sin grupo ({count})",
        "groups.title": "Grupos de conexiones",
        "groups.help": (
            "Cree grupos aquí y asígneles hosts con «Asignar hosts…», "
            "o use clic derecho → Mover a grupo, o el campo Grupo al editar un host."
        ),
        "groups.add": "Añadir grupo",
        "groups.rename": "Renombrar",
        "groups.delete": "Eliminar",
        "groups.assign": "Asignar hosts…",
        "groups.assign_title": "Asignar hosts a “{name}”",
        "groups.assign_help": (
            "Marque las conexiones que deben pertenecer a “{name}”. "
            "Las desmarcadas que estaban en este grupo pasarán a Sin grupo."
        ),
        "groups.assign_no_hosts": "Aún no hay conexiones. Añada un host primero.",
        "groups.name_prompt": "Nombre del grupo:",
        "groups.item": "{name} — {count} host(s)",
        "groups.exists": "El grupo “{name}” ya existe.",
        "groups.select_first": "Seleccione un grupo primero.",
        "groups.delete_confirm": (
            "¿Eliminar el grupo “{name}”?\n"
            "{count} host(s) pasarán a Sin grupo."
        ),
        "status.groups_updated": "Grupos actualizados",
        "action.move_to_group": "Mover a grupo",
        "action.ungroup": "Sin grupo",
        "status.moved_group": "«{name}» movido a {group}",
        "status.ungrouped": "«{name}» quitado del grupo",
        "host.group": "Grupo",
        "host.group_placeholder": "opcional — escriba un nombre de grupo nuevo",
        "dialog.connection_failed": "Conexión fallida",
        "msg.connection_failed": (
            "La conexión a “{name}” falló (código de salida {code}).\n\n"
            "El terminal permaneció abierto para que pudiera ver el error de SSH.\n"
            "Revise host, puerto, clave y red, e inténtelo de nuevo."
        ),
        "status.connection_failed": "Conexión a {name} falló (salida {code})",
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
