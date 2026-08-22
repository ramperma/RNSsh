"""Main window for the SSH connection manager."""

from __future__ import annotations

import uuid
from pathlib import Path

from PySide6.QtCore import QPoint, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QActionGroup, QBrush, QColor, QCloseEvent, QFont, QIcon, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSizePolicy,
    QStackedWidget,
    QStatusBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

_ASSETS = Path(__file__).resolve().parent / "assets"
_LOGO_PATH = _ASSETS / "logo.png"
_ICON_PATH = _ASSETS / "app_icon.png"

from rnssh.ai import GEMINI, load_ai_config
from rnssh.audio import AudioRecorder
from rnssh.i18n import (
    LANGUAGE_LABELS,
    available_languages,
    get_language,
    set_language,
    t,
)
from rnssh.models import UNGROUPED, AppConfig, Host
from rnssh.provision import ProvisionError, provision_host
from rnssh.ssh_cmd import build_plain_ssh_argv, build_tmux_ssh_argv
from rnssh.storage import load_config, save_config
from rnssh.terminal import (
    LaunchResult,
    TerminalError,
    cleanup_launch_files,
    close_process,
    launch_failed,
    launch_finished,
    launch_in_terminal,
    process_alive,
    read_launch_status,
)
from rnssh.tmux import TmuxError, kill_session, list_sessions
from rnssh.ui.ai_query_dialog import AIQueryDialog
from rnssh.ui.ai_settings_dialog import AISettingsDialog
from rnssh.ui.backup_dialog import BackupDialog
from rnssh.ui.groups_dialog import GroupsDialog
from rnssh.ui.host_dialog import HostDialog
from rnssh.ui.provision_dialog import ProvisionDialog
from rnssh.ui.status_overlay import StatusOverlay
from rnssh.voice import VoiceCommandWorker, VoiceTriggerListener


class ProvisionWorker(QThread):
    finished_ok = Signal(object, object)  # Host, ProvisionResult
    failed = Signal(str)

    def __init__(self, host: Host, password: str, parent=None) -> None:
        super().__init__(parent)
        self._host = host
        self._password = password

    def run(self) -> None:
        try:
            result = provision_host(self._host, self._password)
            self.finished_ok.emit(self._host, result)
        except ProvisionError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))
        finally:
            self._password = ""


class ListSessionsWorker(QThread):
    finished_ok = Signal(list)
    failed = Signal(str)

    def __init__(self, host: Host, parent=None) -> None:
        super().__init__(parent)
        self._host = host

    def run(self) -> None:
        try:
            sessions = list_sessions(self._host)
            self.finished_ok.emit(sessions)
        except TmuxError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class KillSessionWorker(QThread):
    finished_ok = Signal(str)
    failed = Signal(str)

    def __init__(self, host: Host, session: str, parent=None) -> None:
        super().__init__(parent)
        self._host = host
        self._session = session

    def run(self) -> None:
        try:
            kill_session(self._host, self._session)
            self.finished_ok.emit(self._session)
        except TmuxError as exc:
            self.failed.emit(str(exc))
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


class MainWindow(QMainWindow):
    COL_NAME = 0
    COL_TARGET = 1
    COL_KEY = 2
    COL_TMUX = 3
    COL_LAST = 4

    def __init__(self) -> None:
        super().__init__()
        self.resize(920, 560)
        self.setMinimumSize(520, 360)
        if _ICON_PATH.is_file():
            self.setWindowIcon(QIcon(str(_ICON_PATH)))

        self._config: AppConfig = load_config()
        set_language(self._config.language)
        # Unique launch_id -> LaunchResult (never overwrite by host id).
        self._launched: dict[str, LaunchResult] = {}
        self._reported_launches: set[str] = set()
        self._worker: QThread | None = None
        self._voice_worker: VoiceCommandWorker | None = None
        self._voice_listeners: dict[str, VoiceTriggerListener] = {}
        self._recorder: AudioRecorder | None = None
        self._recording_for: str | None = None
        self._closing = False
        self._voice_done_timer: QTimer | None = None
        self._overlay = StatusOverlay(self)

        self._actions: dict[str, QAction] = {}
        self._lang_actions: dict[str, QAction] = {}

        self._watch_timer = QTimer(self)
        self._watch_timer.setInterval(800)
        self._watch_timer.timeout.connect(self._poll_launches)
        self._watch_timer.start()

        self._build_menubar()
        self._build_central()
        self._build_statusbar()
        self._retranslate_ui()
        self._reload_table()

    def _build_menubar(self) -> None:
        menubar = self.menuBar()

        self._host_menu = QMenu(self)
        menubar.addMenu(self._host_menu)

        self._connection_menu = QMenu(self)
        menubar.addMenu(self._connection_menu)

        self._config_menu = QMenu(self)
        menubar.addMenu(self._config_menu)

        self._lang_menu = QMenu(self)
        menubar.addMenu(self._lang_menu)

        host_specs = [
            ("add", self.add_host, QKeySequence.StandardKey.New),
            ("edit", self.edit_host, None),
            ("delete", self.delete_host, QKeySequence.StandardKey.Delete),
            (None, None, None),
            ("manage_groups", self.manage_groups, None),
            (None, None, None),
            ("refresh", self._reload_table, QKeySequence.StandardKey.Refresh),
        ]
        for key, slot, shortcut in host_specs:
            if key is None:
                self._host_menu.addSeparator()
                continue
            act = QAction(self)
            act.triggered.connect(slot)
            if shortcut:
                act.setShortcut(shortcut)
            self._host_menu.addAction(act)
            self._actions[key] = act

        conn_specs = [
            ("connect_tmux", lambda: self.connect_selected(tmux=True), QKeySequence("Return")),
            ("connect_plain", lambda: self.connect_selected(tmux=False), None),
            (None, None, None),
            ("ai_query", self._open_ai_query, None),
            (None, None, None),
            ("provision", self.provision_selected, None),
            ("list_sessions", self.list_tmux_sessions, None),
            ("delete_tmux", self.delete_tmux_session, None),
            ("close_terminal", self.close_selected_terminal, None),
        ]
        for key, slot, shortcut in conn_specs:
            if key is None:
                self._connection_menu.addSeparator()
                continue
            act = QAction(self)
            act.triggered.connect(slot)
            if shortcut:
                act.setShortcut(shortcut)
            self._connection_menu.addAction(act)
            self._actions[key] = act

        config_specs = [
            ("backup", self._open_backup_dialog, None),
            ("ai_settings", self._open_ai_settings, None),
        ]
        for key, slot, shortcut in config_specs:
            act = QAction(self)
            act.triggered.connect(slot)
            if shortcut:
                act.setShortcut(shortcut)
            self._config_menu.addAction(act)
            self._actions[key] = act

        group = QActionGroup(self)
        group.setExclusive(True)
        for code, label in available_languages():
            act = QAction(label, self)
            act.setCheckable(True)
            act.setData(code)
            act.triggered.connect(lambda checked=False, c=code: self._change_language(c))
            group.addAction(act)
            self._lang_menu.addAction(act)
            self._lang_actions[code] = act

    def _build_central(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QFrame()
        header.setObjectName("appHeader")
        header_row = QHBoxLayout(header)
        header_row.setContentsMargins(20, 14, 24, 14)
        header_row.setSpacing(16)

        self._logo = QLabel()
        self._logo.setObjectName("brandLogo")
        self._logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        if _LOGO_PATH.is_file():
            pix = QPixmap(str(_LOGO_PATH))
            self._logo.setPixmap(
                pix.scaledToHeight(64, Qt.TransformationMode.SmoothTransformation)
            )
        self._logo.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        header_row.addWidget(self._logo, 0, Qt.AlignmentFlag.AlignVCenter)

        titles = QVBoxLayout()
        titles.setContentsMargins(0, 0, 0, 0)
        titles.setSpacing(4)
        self._brand = QLabel()
        self._brand.setObjectName("brandTitle")
        self._subtitle = QLabel()
        self._subtitle.setObjectName("brandSubtitle")
        self._subtitle.setWordWrap(True)
        titles.addStretch(1)
        titles.addWidget(self._brand)
        titles.addWidget(self._subtitle)
        titles.addStretch(1)
        header_row.addLayout(titles, 1)
        root.addWidget(header)

        hosts_page = QWidget()
        hosts_layout = QVBoxLayout(hosts_page)
        hosts_layout.setContentsMargins(0, 0, 0, 0)
        hosts_layout.setSpacing(0)

        self.table = QTreeWidget()
        self.table.setObjectName("hostsTable")
        self.table.setColumnCount(5)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setRootIsDecorated(True)
        self.table.setUniformRowHeights(True)
        self.table.setItemsExpandable(True)
        self.table.setExpandsOnDoubleClick(False)
        self.table.header().setStretchLastSection(True)
        self.table.header().setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.table.header().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_host_context_menu)
        self.table.itemDoubleClicked.connect(self._on_tree_double_click)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._empty_hint = QLabel()
        self._empty_hint.setObjectName("emptyHint")
        self._empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_hint.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._empty_hint.customContextMenuRequested.connect(self._show_empty_context_menu)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._empty_hint)
        self._stack.addWidget(self.table)
        hosts_layout.addWidget(self._stack, 1)

        root.addWidget(hosts_page, 1)

        self.setCentralWidget(central)

    def _build_statusbar(self) -> None:
        sb = QStatusBar()
        self.setStatusBar(sb)
        self._status = QLabel()
        sb.addWidget(self._status, 1)

    def _select_row_at(self, pos: QPoint) -> bool:
        item = self.table.itemAt(pos)
        if item is None:
            self.table.clearSelection()
            return False
        # Prefer the host leaf under a group header click.
        if item.parent() is None and item.childCount() > 0:
            # Clicked a group — not a host selection
            self.table.setCurrentItem(item)
            return False
        host_item = item if item.parent() is not None else item
        self.table.setCurrentItem(host_item)
        return self._host_id_from_item(host_item) is not None

    def _host_id_from_item(self, item: QTreeWidgetItem | None) -> str | None:
        if item is None:
            return None
        # Host rows store id on column 0; group rows use role "group"
        kind = item.data(0, Qt.ItemDataRole.UserRole + 1)
        if kind == "group":
            return None
        host_id = item.data(0, Qt.ItemDataRole.UserRole)
        return host_id if isinstance(host_id, str) else None

    def _on_tree_double_click(self, item: QTreeWidgetItem, _column: int) -> None:
        if self._host_id_from_item(item):
            self.connect_selected(tmux=True)

    def _show_host_context_menu(self, pos: QPoint) -> None:
        has_row = self._select_row_at(pos)
        menu = QMenu(self)
        if has_row:
            menu.addAction(self._actions["connect_tmux"])
            menu.addAction(self._actions["connect_plain"])
            menu.addSeparator()
            menu.addAction(self._actions["provision"])
            menu.addAction(self._actions["list_sessions"])
            menu.addAction(self._actions["delete_tmux"])
            menu.addAction(self._actions["close_terminal"])
            menu.addSeparator()
            menu.addAction(self._actions["edit"])
            menu.addMenu(self._build_move_to_group_menu())
            menu.addAction(self._actions["delete"])
            menu.addSeparator()
            menu.addAction(self._actions["refresh"])
        else:
            menu.addAction(self._actions["add"])
            menu.addAction(self._actions["manage_groups"])
            menu.addAction(self._actions["refresh"])
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _build_move_to_group_menu(self) -> QMenu:
        submenu = QMenu(t("action.move_to_group"), self)
        ungroup = submenu.addAction(t("action.ungroup"))
        ungroup.triggered.connect(lambda: self._move_selected_to_group(""))
        groups = self._config.known_groups()
        if groups:
            submenu.addSeparator()
        for name in groups:
            act = submenu.addAction(name)
            act.triggered.connect(
                lambda _checked=False, g=name: self._move_selected_to_group(g)
            )
        return submenu

    def _move_selected_to_group(self, group: str) -> None:
        host = self._selected_host()
        if host is None:
            return
        updated = self._config.set_host_group(host.id, group)
        if updated is None:
            return
        self._persist()
        self._reload_table(preserve_config=True)
        if group:
            self.set_status(t("status.moved_group", name=updated.name, group=group))
        else:
            self.set_status(t("status.ungrouped", name=updated.name))

    def _show_empty_context_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)
        menu.addAction(self._actions["add"])
        menu.addAction(self._actions["manage_groups"])
        menu.addAction(self._actions["refresh"])
        menu.exec(self._empty_hint.mapToGlobal(pos))

    def _retranslate_ui(self) -> None:
        self.setWindowTitle(t("app.title"))
        self._brand.setText(t("app.brand"))
        self._subtitle.setText(t("app.subtitle"))
        self._host_menu.setTitle(t("menu.host"))
        self._connection_menu.setTitle(t("menu.connection"))
        self._config_menu.setTitle(t("menu.config"))
        self._lang_menu.setTitle(t("menu.language"))
        self._empty_hint.setText(t("empty.hint"))

        action_keys = {
            "add": "action.add",
            "edit": "action.edit",
            "delete": "action.delete",
            "manage_groups": "action.manage_groups",
            "provision": "action.provision",
            "connect_tmux": "action.connect_tmux",
            "connect_plain": "action.connect_plain",
            "list_sessions": "action.list_sessions",
            "delete_tmux": "action.delete_tmux",
            "close_terminal": "action.close_terminal",
            "refresh": "action.refresh",
            "backup": "action.backup",
            "ai_settings": "action.ai_settings",
            "ai_query": "action.ai_query",
        }
        for key, msg_key in action_keys.items():
            self._actions[key].setText(t(msg_key))

        self.table.setHeaderLabels(
            [
                t("col.name"),
                t("col.target"),
                t("col.key_status"),
                t("col.tmux"),
                t("col.last"),
            ]
        )

        current = get_language()
        for code, act in self._lang_actions.items():
            act.setChecked(code == current)

    def _change_language(self, code: str) -> None:
        set_language(code)
        self._config.language = get_language()
        self._persist()
        self._retranslate_ui()
        self._reload_table(preserve_config=True)
        label = LANGUAGE_LABELS.get(get_language(), get_language())
        self.set_status(t("lang.changed", label=label))

    def set_status(self, msg: str) -> None:
        self._status.setText(msg)

    def _selected_host(self) -> Host | None:
        item = self.table.currentItem()
        host_id = self._host_id_from_item(item)
        if not host_id:
            return None
        return self._config.get_host(host_id)

    def _reload_table(self, *, preserve_config: bool = False) -> None:
        if not preserve_config:
            self._config = load_config()
            set_language(self._config.language)
        selected_id = None
        selected = self._selected_host()
        if selected:
            selected_id = selected.id

        self.table.clear()
        self.table.setHeaderLabels(
            [
                t("col.name"),
                t("col.target"),
                t("col.key_status"),
                t("col.tmux"),
                t("col.last"),
            ]
        )

        select_item: QTreeWidgetItem | None = None
        group_font = QFont(self.table.font())
        group_font.setBold(True)
        group_brush = QBrush(QColor("#e8eef4"))

        for group_name, hosts in self._config.hosts_by_group():
            if group_name == UNGROUPED:
                label = t("group.ungrouped", count=len(hosts))
            else:
                label = t("group.header", name=group_name, count=len(hosts))

            group_item = QTreeWidgetItem([label, "", "", "", ""])
            group_item.setData(0, Qt.ItemDataRole.UserRole + 1, "group")
            group_item.setData(0, Qt.ItemDataRole.UserRole, group_name)
            group_item.setFlags(
                Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
            )
            for col in range(5):
                group_item.setFont(col, group_font)
                group_item.setBackground(col, group_brush)
            self.table.addTopLevelItem(group_item)

            for host in hosts:
                key_status = t("key.provisioned") if host.provisioned else t("key.not_provisioned")
                if host.key_name:
                    key_status = f"{key_status} ({host.key_name})"
                child = QTreeWidgetItem(
                    [
                        host.name,
                        host.target,
                        key_status,
                        host.tmux_session,
                        host.last_connected or "—",
                    ]
                )
                child.setData(0, Qt.ItemDataRole.UserRole, host.id)
                child.setData(0, Qt.ItemDataRole.UserRole + 1, "host")
                if host.provisioned:
                    child.setForeground(self.COL_KEY, QColor("#0f766e"))
                else:
                    child.setForeground(self.COL_KEY, QColor("#b45309"))
                group_item.addChild(child)
                if selected_id and host.id == selected_id:
                    select_item = child

            group_item.setExpanded(True)

        if self._config.hosts:
            self._stack.setCurrentWidget(self.table)
            self.table.resizeColumnToContents(self.COL_NAME)
            self.table.resizeColumnToContents(self.COL_TARGET)
            self.table.setColumnWidth(
                self.COL_NAME, max(160, self.table.columnWidth(self.COL_NAME))
            )
            self.table.setColumnWidth(
                self.COL_TARGET, max(200, self.table.columnWidth(self.COL_TARGET))
            )
            if select_item is not None:
                self.table.setCurrentItem(select_item)
        else:
            self._stack.setCurrentWidget(self._empty_hint)

        self.set_status(t("status.hosts_count", count=len(self._config.hosts)))

    def _on_backup_restored(self) -> None:
        self._reload_table()

    def _persist(self) -> None:
        save_config(self._config)

    def _open_backup_dialog(self) -> None:
        dlg = BackupDialog(self)
        dlg.set_config(self._config)
        dlg.restored.connect(self._on_backup_restored)
        dlg.status_message.connect(self.set_status)
        dlg.exec()

    def manage_groups(self) -> None:
        dlg = GroupsDialog(self._config, self)
        dlg.exec()
        if dlg.changed():
            self._persist()
            self._reload_table(preserve_config=True)
            self.set_status(t("status.groups_updated"))

    def add_host(self) -> None:
        dlg = HostDialog(self, groups=self._config.known_groups())
        if dlg.exec() != HostDialog.DialogCode.Accepted:
            return
        host = dlg.result_host()
        if host is None:
            return
        self._config.upsert_host(host)
        self._persist()
        self._reload_table(preserve_config=True)
        self.set_status(t("status.added", name=host.name))

    def edit_host(self) -> None:
        host = self._selected_host()
        if host is None:
            QMessageBox.information(self, t("dialog.no_selection"), t("msg.select_edit"))
            return
        dlg = HostDialog(self, host=host, groups=self._config.known_groups())
        if dlg.exec() != HostDialog.DialogCode.Accepted:
            return
        updated = dlg.result_host()
        if updated is None:
            return
        self._config.upsert_host(updated)
        self._persist()
        self._reload_table(preserve_config=True)
        self.set_status(t("status.updated", name=updated.name))

    def delete_host(self) -> None:
        host = self._selected_host()
        if host is None:
            QMessageBox.information(self, t("dialog.no_selection"), t("msg.select_delete"))
            return
        reply = QMessageBox.question(
            self,
            t("dialog.delete_host"),
            t("msg.delete_confirm", name=host.name),
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._config.remove_host(host.id)
        self._persist()
        self._reload_table(preserve_config=True)
        self.set_status(t("status.deleted", name=host.name))

    def provision_selected(self) -> None:
        host = self._selected_host()
        if host is None:
            QMessageBox.information(self, t("dialog.no_selection"), t("msg.select_provision"))
            return
        if host.jump_host:
            QMessageBox.warning(
                self,
                t("dialog.jump_host"),
                t("msg.jump_unsupported"),
            )
            return
        dlg = ProvisionDialog(host, self)
        if dlg.exec() != ProvisionDialog.DialogCode.Accepted:
            return
        password = dlg.password()
        self.set_status(t("status.provisioning", name=host.name))
        self._worker = ProvisionWorker(host, password, self)
        self._worker.finished_ok.connect(self._on_provision_ok)
        self._worker.failed.connect(self._on_provision_fail)
        self._worker.start()

    def _on_provision_ok(self, host: Host, result) -> None:
        host.key_name = result.key_name
        host.provisioned = True
        self._config.upsert_host(host)
        self._persist()
        self._reload_table(preserve_config=True)
        state = t("key.state.already") if result.already_present else t("key.state.installed")
        fp = result.host_key.fingerprint_sha256
        QMessageBox.information(
            self,
            t("dialog.provisioned"),
            t(
                "msg.provision_ok",
                key_name=result.key_name,
                state=state,
                key_type=result.host_key.key_type,
                fingerprint=fp,
            ),
        )
        self.set_status(t("status.provisioned", name=host.name))

    def _on_provision_fail(self, message: str) -> None:
        QMessageBox.critical(self, t("dialog.provision_failed"), message)
        self.set_status(t("status.provision_failed", message=message))

    def connect_selected(self, *, tmux: bool = True, session: str | None = None) -> None:
        host = self._selected_host()
        if host is None:
            QMessageBox.information(self, t("dialog.no_selection"), t("msg.select_connect"))
            return
        if not host.provisioned and not host.key_name:
            reply = QMessageBox.question(
                self,
                t("dialog.not_provisioned"),
                t("msg.connect_anyway"),
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        if tmux:
            argv = build_tmux_ssh_argv(host, session=session)
        else:
            argv = build_plain_ssh_argv(host)
        try:
            result = launch_in_terminal(
                argv,
                host_id=host.id,
                host_name=host.name,
            )
        except TerminalError as exc:
            QMessageBox.critical(self, t("dialog.terminal_error"), str(exc))
            self.set_status(str(exc))
            return
        host.mark_connected()
        self._config.upsert_host(host)
        self._persist()
        self._launched[result.launch_id] = result
        if tmux:
            resolved_session = session or host.tmux_session or "rnssh"
            self._start_voice_listener(host, resolved_session, result.launch_id)
        mode = t("mode.tmux") if tmux else t("mode.plain")
        self._reload_table(preserve_config=True)
        self.set_status(t("status.launched", mode=mode, name=host.name, pid=result.pid))

    def _start_voice_listener(self, host: Host, session: str, launch_id: str) -> None:
        token = uuid.uuid4().hex[:12]
        listener = VoiceTriggerListener(host, session, token, self)
        listener.triggered.connect(lambda lid=launch_id: self._on_voice_trigger(lid))
        listener.error.connect(
            lambda msg: self.set_status(t("status.ai_listener_error", message=msg))
        )
        self._voice_listeners[launch_id] = listener
        listener.start()
        self.set_status(t("status.ai_voice_active", name=host.name))

    def _open_ai_settings(self) -> None:
        dlg = AISettingsDialog(self)
        if dlg.exec() == AISettingsDialog.DialogCode.Accepted:
            self.set_status(t("status.ai_saved"))

    def _open_ai_query(self) -> None:
        dlg = AIQueryDialog(self._selected_host(), self)
        dlg.status_message.connect(self.set_status)
        dlg.exec()

    def _on_voice_trigger(self, launch_id: str) -> None:
        if self._recorder is not None and self._recorder.is_recording():
            self._recorder.stop()
            return
        cfg = load_ai_config()
        if not (cfg.get(GEMINI) or {}).get("api_key"):
            self._overlay.hide_state()
            QMessageBox.information(self, t("dialog.ai_voice"), t("msg.ai_need_gemini_key"))
            return
        if self._recorder is None:
            self._recorder = AudioRecorder(self)
            self._recorder.finished.connect(self._on_voice_audio)
            self._recorder.failed.connect(self._on_voice_failed)
        self._recording_for = launch_id
        self._recorder.start()
        self._overlay.show_state(t("overlay.listening"), "🎤")
        self.set_status(t("status.ai_listening"))

    def _on_voice_audio(self, wav: bytes) -> None:
        launch_id = self._recording_for
        self._recording_for = None
        if self._closing:
            return
        if not wav or len(wav) < 200:
            self._overlay.hide_state()
            self.set_status(t("msg.ai_no_audio"))
            return
        launch = self._launched.get(launch_id)
        if launch is None:
            self._overlay.hide_state()
            return
        host = self._config.get_host(launch.host_id)
        if host is None:
            self._overlay.hide_state()
            return
        listener = self._voice_listeners.get(launch_id)
        session = listener._session if listener is not None else None
        self._overlay.show_state(t("overlay.processing"), "🤖")
        self.set_status(t("status.ai_processing"))
        self._voice_worker = VoiceCommandWorker(host, session or host.tmux_session, wav, self)
        self._voice_worker.finished_ok.connect(
            lambda text, cmd, hid=host.id: self._on_voice_done(hid, text, cmd)
        )
        self._voice_worker.failed.connect(self._on_voice_failed)
        self._voice_worker.start()

    def _on_voice_done(self, host_id: str, transcription: str, command: str) -> None:
        host = self._config.get_host(host_id)
        name = host.name if host else host_id
        self.set_status(t("status.ai_pasted", name=name))
        preview = command if len(command) <= 70 else command[:67] + "…"
        self._overlay.show_state(t("overlay.pasted", name=name, command=preview), "⌨️")
        if self._voice_done_timer is not None:
            self._voice_done_timer.stop()
        self._voice_done_timer = QTimer(self)
        self._voice_done_timer.setSingleShot(True)
        self._voice_done_timer.timeout.connect(self._overlay.hide_state)
        self._voice_done_timer.start(4000)

    def _on_voice_failed(self, message: str) -> None:
        self._overlay.hide_state()
        self.set_status(message)
        QMessageBox.critical(self, t("dialog.ai_error"), message)

    def closeEvent(self, event: QCloseEvent) -> None:
        self._closing = True
        self._overlay.hide_state()
        if self._voice_done_timer is not None:
            self._voice_done_timer.stop()
        for listener in list(self._voice_listeners.values()):
            listener.stop()
        self._voice_listeners.clear()
        if self._recorder is not None and self._recorder.is_recording():
            self._recorder.stop()
        super().closeEvent(event)

    def _latest_launch_for_host(self, host_id: str) -> LaunchResult | None:
        matches = [launch for launch in self._launched.values() if launch.host_id == host_id]
        if not matches:
            return None
        return max(matches, key=lambda item: item.started_at)

    def _poll_launches(self) -> None:
        """Detect finished terminal sessions via done-file (not terminal PID)."""
        to_report: list[tuple[str, str, int]] = []
        finished_ids: list[str] = []

        for launch_id, launch in list(self._launched.items()):
            if launch.done_file is not None:
                if not launch_finished(launch.done_file):
                    continue
            else:
                if process_alive(launch.pid):
                    continue

            finished_ids.append(launch_id)
            # Only notify for marked quick connection failures — not for closing
            # a healthy session (which often exits non-zero on window close).
            if (
                launch_id not in self._reported_launches
                and launch_failed(launch.failed_file)
            ):
                code = read_launch_status(launch.status_file) or 1
                name = launch.host_name or launch.host_id or launch_id
                self._reported_launches.add(launch_id)
                to_report.append((launch_id, name, code))

        for launch_id in finished_ids:
            launch = self._launched.pop(launch_id, None)
            listener = self._voice_listeners.pop(launch_id, None)
            if listener is not None:
                listener.stop()
            if launch is not None:
                cleanup_launch_files(launch)

        for _launch_id, name, code in to_report:
            QTimer.singleShot(
                0,
                lambda n=name, c=code: self._show_connection_failed(n, c),
            )

    def _show_connection_failed(self, name: str, code: int) -> None:
        QMessageBox.warning(
            self,
            t("dialog.connection_failed"),
            t("msg.connection_failed", name=name, code=code),
        )
        self.set_status(t("status.connection_failed", name=name, code=code))

    def list_tmux_sessions(self) -> None:
        host = self._selected_host()
        if host is None:
            QMessageBox.information(self, t("dialog.no_selection"), t("msg.select_first"))
            return
        if not host.provisioned:
            QMessageBox.warning(
                self,
                t("dialog.not_provisioned"),
                t("msg.provision_before_list"),
            )
            return
        self.set_status(t("status.listing_sessions", name=host.name))
        self._worker = ListSessionsWorker(host, self)
        self._worker.finished_ok.connect(lambda sessions: self._on_sessions(host, sessions))
        self._worker.failed.connect(self._on_sessions_fail)
        self._worker.start()

    def _on_sessions(self, host: Host, sessions: list) -> None:
        if not sessions:
            QMessageBox.information(
                self,
                t("dialog.tmux_sessions"),
                t("msg.no_tmux_sessions", name=host.name, session=host.tmux_session),
            )
            self.set_status(t("status.no_sessions"))
            return
        choice, ok = QInputDialog.getItem(
            self,
            t("dialog.tmux_sessions"),
            t("msg.attach_session", name=host.name),
            sessions,
            0,
            False,
        )
        if ok and choice:
            self.connect_selected(tmux=True, session=choice)

    def _on_sessions_fail(self, message: str) -> None:
        QMessageBox.critical(self, t("dialog.list_sessions_failed"), message)
        self.set_status(message)

    def delete_tmux_session(self) -> None:
        host = self._selected_host()
        if host is None:
            QMessageBox.information(self, t("dialog.no_selection"), t("msg.select_first"))
            return
        if not host.provisioned:
            QMessageBox.warning(
                self,
                t("dialog.not_provisioned"),
                t("msg.provision_before_delete"),
            )
            return
        self.set_status(t("status.listing_sessions", name=host.name))
        self._worker = ListSessionsWorker(host, self)
        self._worker.finished_ok.connect(lambda sessions: self._on_sessions_for_delete(host, sessions))
        self._worker.failed.connect(self._on_sessions_fail)
        self._worker.start()

    def _on_sessions_for_delete(self, host: Host, sessions: list) -> None:
        default = host.tmux_session or "rnssh"
        if not sessions:
            reply = QMessageBox.question(
                self,
                t("dialog.delete_tmux"),
                t("msg.no_sessions_kill_default", name=host.name, session=default),
            )
            if reply != QMessageBox.StandardButton.Yes:
                self.set_status(t("status.no_sessions"))
                return
            self._confirm_and_kill_session(host, default, already_confirmed=True)
            return

        choices = list(sessions)
        current = choices.index(default) if default in choices else 0
        choice, ok = QInputDialog.getItem(
            self,
            t("dialog.delete_tmux"),
            t("msg.kill_session_pick", name=host.name),
            choices,
            current,
            False,
        )
        if ok and choice:
            self._confirm_and_kill_session(host, choice)

    def _confirm_and_kill_session(
        self,
        host: Host,
        session: str,
        *,
        already_confirmed: bool = False,
    ) -> None:
        if not already_confirmed:
            reply = QMessageBox.question(
                self,
                t("dialog.delete_tmux"),
                t("msg.delete_tmux_confirm", session=session, name=host.name),
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        self.set_status(t("status.deleting_session", session=session, name=host.name))
        self._worker = KillSessionWorker(host, session, self)
        self._worker.finished_ok.connect(
            lambda killed: self._on_kill_session_ok(host, killed)
        )
        self._worker.failed.connect(self._on_kill_session_fail)
        self._worker.start()

    def _on_kill_session_ok(self, host: Host, session: str) -> None:
        self.set_status(t("status.deleted_session", session=session, name=host.name))
        QMessageBox.information(
            self,
            t("dialog.delete_tmux"),
            t("status.deleted_session", session=session, name=host.name),
        )

    def _on_kill_session_fail(self, message: str) -> None:
        QMessageBox.critical(self, t("dialog.delete_tmux_failed"), message)
        self.set_status(message)

    def close_selected_terminal(self) -> None:
        host = self._selected_host()
        if host is None:
            QMessageBox.information(self, t("dialog.no_selection"), t("msg.select_host"))
            return
        launch = self._latest_launch_for_host(host.id)
        if not launch:
            QMessageBox.information(
                self,
                t("dialog.no_tracked"),
                t("msg.no_tracked"),
            )
            return
        close_process(launch.pid)
        self._launched.pop(launch.launch_id, None)
        cleanup_launch_files(launch)
        self.set_status(t("status.terminated", pid=launch.pid, name=host.name))
