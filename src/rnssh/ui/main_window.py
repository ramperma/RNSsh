"""Main window for the SSH connection manager."""

from __future__ import annotations

from PySide6.QtCore import QPoint, Qt, QThread, Signal
from PySide6.QtGui import QAction, QActionGroup, QColor, QKeySequence
from PySide6.QtWidgets import (
    QFrame,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSizePolicy,
    QStackedWidget,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from rnssh.i18n import (
    LANGUAGE_LABELS,
    available_languages,
    get_language,
    set_language,
    t,
)
from rnssh.models import AppConfig, Host
from rnssh.provision import ProvisionError, provision_host
from rnssh.ssh_cmd import build_plain_ssh_argv, build_tmux_ssh_argv
from rnssh.storage import load_config, save_config
from rnssh.terminal import TerminalError, close_process, launch_in_terminal
from rnssh.tmux import TmuxError, kill_session, list_sessions
from rnssh.ui.host_dialog import HostDialog
from rnssh.ui.provision_dialog import ProvisionDialog


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

        self._config: AppConfig = load_config()
        set_language(self._config.language)
        self._launched: dict[str, int] = {}
        self._worker: QThread | None = None

        self._actions: dict[str, QAction] = {}
        self._lang_actions: dict[str, QAction] = {}

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

        self._lang_menu = QMenu(self)
        menubar.addMenu(self._lang_menu)

        host_specs = [
            ("add", self.add_host, QKeySequence.StandardKey.New),
            ("edit", self.edit_host, None),
            ("delete", self.delete_host, QKeySequence.StandardKey.Delete),
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
            ("provision", self.provision_selected, None),
            ("list_sessions", self.list_tmux_sessions, None),
            ("delete_tmux", self.delete_tmux_session, None),
            ("close_terminal", self.close_selected_terminal, None),
        ]
        for key, slot, shortcut in conn_specs:
            act = QAction(self)
            act.triggered.connect(slot)
            if shortcut:
                act.setShortcut(shortcut)
            self._connection_menu.addAction(act)
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
        header_layout = QVBoxLayout(header)
        header_layout.setContentsMargins(24, 18, 24, 16)
        header_layout.setSpacing(4)
        self._brand = QLabel()
        self._brand.setObjectName("brandTitle")
        self._subtitle = QLabel()
        self._subtitle.setObjectName("brandSubtitle")
        self._subtitle.setWordWrap(True)
        header_layout.addWidget(self._brand)
        header_layout.addWidget(self._subtitle)
        root.addWidget(header)

        self.table = QTableWidget(0, 5)
        self.table.setObjectName("hostsTable")
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.horizontalHeader().setDefaultAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        self.table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_host_context_menu)
        self.table.doubleClicked.connect(lambda: self.connect_selected(tmux=True))
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._empty_hint = QLabel()
        self._empty_hint.setObjectName("emptyHint")
        self._empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_hint.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._empty_hint.customContextMenuRequested.connect(self._show_empty_context_menu)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._empty_hint)
        self._stack.addWidget(self.table)
        root.addWidget(self._stack, 1)

        self.setCentralWidget(central)

    def _build_statusbar(self) -> None:
        sb = QStatusBar()
        self.setStatusBar(sb)
        self._status = QLabel()
        sb.addWidget(self._status, 1)

    def _select_row_at(self, pos: QPoint) -> bool:
        index = self.table.indexAt(pos)
        if not index.isValid():
            self.table.clearSelection()
            return False
        self.table.selectRow(index.row())
        self.table.setCurrentIndex(index)
        return True

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
            menu.addAction(self._actions["delete"])
            menu.addSeparator()
            menu.addAction(self._actions["refresh"])
        else:
            menu.addAction(self._actions["add"])
            menu.addAction(self._actions["refresh"])
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _show_empty_context_menu(self, pos: QPoint) -> None:
        menu = QMenu(self)
        menu.addAction(self._actions["add"])
        menu.addAction(self._actions["refresh"])
        menu.exec(self._empty_hint.mapToGlobal(pos))

    def _retranslate_ui(self) -> None:
        self.setWindowTitle(t("app.title"))
        self._brand.setText(t("app.brand"))
        self._subtitle.setText(t("app.subtitle"))
        self._host_menu.setTitle(t("menu.host"))
        self._connection_menu.setTitle(t("menu.connection"))
        self._lang_menu.setTitle(t("menu.language"))
        self._empty_hint.setText(t("empty.hint"))

        action_keys = {
            "add": "action.add",
            "edit": "action.edit",
            "delete": "action.delete",
            "provision": "action.provision",
            "connect_tmux": "action.connect_tmux",
            "connect_plain": "action.connect_plain",
            "list_sessions": "action.list_sessions",
            "delete_tmux": "action.delete_tmux",
            "close_terminal": "action.close_terminal",
            "refresh": "action.refresh",
        }
        for key, msg_key in action_keys.items():
            self._actions[key].setText(t(msg_key))

        self.table.setHorizontalHeaderLabels(
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
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return None
        row = rows[0].row()
        item = self.table.item(row, self.COL_NAME)
        if item is None:
            return None
        host_id = item.data(Qt.ItemDataRole.UserRole)
        return self._config.get_host(host_id)

    def _reload_table(self, *, preserve_config: bool = False) -> None:
        if not preserve_config:
            self._config = load_config()
            set_language(self._config.language)
        selected_id = None
        selected = self._selected_host()
        if selected:
            selected_id = selected.id

        self.table.setRowCount(0)
        for host in self._config.hosts:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setRowHeight(row, 48)

            name_item = QTableWidgetItem(host.name)
            name_item.setData(Qt.ItemDataRole.UserRole, host.id)
            self.table.setItem(row, self.COL_NAME, name_item)
            self.table.setItem(row, self.COL_TARGET, QTableWidgetItem(host.target))

            key_status = t("key.provisioned") if host.provisioned else t("key.not_provisioned")
            if host.key_name:
                key_status = f"{key_status} ({host.key_name})"
            key_item = QTableWidgetItem(key_status)
            if host.provisioned:
                key_item.setForeground(QColor("#0f766e"))
            else:
                key_item.setForeground(QColor("#b45309"))
            self.table.setItem(row, self.COL_KEY, key_item)

            self.table.setItem(row, self.COL_TMUX, QTableWidgetItem(host.tmux_session))
            self.table.setItem(
                row,
                self.COL_LAST,
                QTableWidgetItem(host.last_connected or "—"),
            )
            if selected_id and host.id == selected_id:
                self.table.selectRow(row)

        if self._config.hosts:
            self._stack.setCurrentWidget(self.table)
            self.table.resizeColumnsToContents()
            self.table.setColumnWidth(self.COL_NAME, max(160, self.table.columnWidth(self.COL_NAME)))
            self.table.setColumnWidth(self.COL_TARGET, max(200, self.table.columnWidth(self.COL_TARGET)))
        else:
            self._stack.setCurrentWidget(self._empty_hint)

        self.set_status(t("status.hosts_count", count=len(self._config.hosts)))

    def _persist(self) -> None:
        save_config(self._config)

    def add_host(self) -> None:
        dlg = HostDialog(self)
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
        dlg = HostDialog(self, host=host)
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
            result = launch_in_terminal(argv)
        except TerminalError as exc:
            QMessageBox.critical(self, t("dialog.terminal_error"), str(exc))
            self.set_status(str(exc))
            return
        host.mark_connected()
        self._config.upsert_host(host)
        self._persist()
        self._launched[host.id] = result.pid
        mode = t("mode.tmux") if tmux else t("mode.plain")
        self._reload_table(preserve_config=True)
        self.set_status(t("status.launched", mode=mode, name=host.name, pid=result.pid))

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
        pid = self._launched.get(host.id)
        if not pid:
            QMessageBox.information(
                self,
                t("dialog.no_tracked"),
                t("msg.no_tracked"),
            )
            return
        close_process(pid)
        del self._launched[host.id]
        self.set_status(t("status.terminated", pid=pid, name=host.name))
