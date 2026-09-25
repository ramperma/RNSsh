"""Main window for the SSH connection manager."""

from __future__ import annotations

import uuid
from pathlib import Path

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QThread, QTimer, Signal
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QBrush,
    QColor,
    QCloseEvent,
    QFont,
    QIcon,
    QKeySequence,
    QPainter,
    QPixmap,
    QShowEvent,
)
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QStatusBar,
    QSystemTrayIcon,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

_ASSETS = Path(__file__).resolve().parent / "assets"
_LOGO_PATH = _ASSETS / "logo.png"
_LOGO_MONO_PATH = _ASSETS / "logo_mono.png"
_ICON_PATH = _ASSETS / "app_icon.png"
_HEADER_LOGO_COLOR = QColor("#f8fafc")


def _header_logo_pixmap(height: int) -> QPixmap | None:
    """Return a light logo that stays visible on the dark header."""
    source = _LOGO_MONO_PATH if _LOGO_MONO_PATH.is_file() else _LOGO_PATH
    if not source.is_file():
        return None
    pix = QPixmap(str(source))
    if pix.isNull():
        return None
    scaled = pix.scaledToHeight(height, Qt.TransformationMode.SmoothTransformation)
    tinted = QPixmap(scaled.size())
    tinted.fill(Qt.GlobalColor.transparent)
    painter = QPainter(tinted)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    painter.drawPixmap(0, 0, scaled)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
    painter.fillRect(tinted.rect(), _HEADER_LOGO_COLOR)
    painter.end()
    return tinted


def initial_window_position(available: QRect, size: QSize) -> QPoint:
    """Center the window when it fits; otherwise keep its size at the screen origin."""
    if size.width() <= available.width() and size.height() <= available.height():
        return QPoint(
            available.x() + (available.width() - size.width()) // 2,
            available.y() + (available.height() - size.height()) // 2,
        )
    return QPoint(available.x(), available.y())

from rnssh.ai import GEMINI, load_ai_config
from rnssh.audio import AudioRecorder
from rnssh.graphical import GraphicalAppError, build_graphical_ssh_argv
from rnssh.i18n import (
    LANGUAGE_LABELS,
    available_languages,
    get_language,
    set_language,
    t,
)
from rnssh.models import GraphicalApp, UNGROUPED, AppConfig, Host
from rnssh.provision import ProvisionError, provision_host
from rnssh.ssh_cmd import (
    build_plain_ssh_argv,
    build_shutdown_ssh_argv,
    build_tmux_ssh_argv,
)
from rnssh.storage import load_config, save_config
from rnssh.terminal import (
    LaunchResult,
    TerminalError,
    cleanup_launch_files,
    close_process,
    launch_failed,
    launch_finished,
    launch_in_terminal,
    launch_process,
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
from rnssh.ui.graphical_apps_dialog import GraphicalAppsDialog
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
        self._placed_on_screen = False
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
        self._quitting = False
        self._tray: QSystemTrayIcon | None = None
        self._tray_show_action: QAction | None = None
        self._tray_quit_action: QAction | None = None
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
        self._build_tray()
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
            ("configure_graphical_apps", self.configure_graphical_apps_selected, None),
            ("shutdown_remote", self.shutdown_selected, None),
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
        header_row.setContentsMargins(20, 10, 22, 10)
        header_row.setSpacing(14)

        self._logo = QLabel()
        self._logo.setObjectName("brandLogo")
        self._logo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pix = _header_logo_pixmap(40)
        if pix is not None:
            self._logo.setPixmap(pix)
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

        accent = QFrame()
        accent.setObjectName("brandAccent")
        accent.setFixedHeight(3)
        root.addWidget(accent)

        canvas = QWidget()
        canvas.setObjectName("contentCanvas")
        canvas_layout = QVBoxLayout(canvas)
        canvas_layout.setContentsMargins(18, 14, 18, 16)
        canvas_layout.setSpacing(10)

        bar = QFrame()
        bar.setObjectName("actionBar")
        bar_row = QHBoxLayout(bar)
        bar_row.setContentsMargins(2, 0, 2, 0)
        bar_row.setSpacing(8)

        self._search = QLineEdit()
        self._search.setObjectName("hostSearch")
        self._search.setClearButtonEnabled(True)
        self._search.textChanged.connect(lambda _text: self._reload_table(preserve_config=True))
        bar_row.addWidget(self._search, 1)

        self._connect_btn = QPushButton()
        self._connect_btn.setObjectName("primaryButton")
        self._connect_btn.clicked.connect(lambda: self.connect_selected(tmux=True))
        self._add_btn = QPushButton()
        self._add_btn.clicked.connect(self.add_host)
        self._edit_btn = QPushButton()
        self._edit_btn.clicked.connect(self.edit_host)
        bar_row.addWidget(self._connect_btn)
        bar_row.addWidget(self._add_btn)
        bar_row.addWidget(self._edit_btn)
        canvas_layout.addWidget(bar)

        hosts_card = QFrame()
        hosts_card.setObjectName("hostsCard")
        hosts_layout = QVBoxLayout(hosts_card)
        hosts_layout.setContentsMargins(1, 1, 1, 1)
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
        self.table.setFrameShape(QFrame.Shape.NoFrame)
        self.table.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_host_context_menu)
        self.table.itemDoubleClicked.connect(self._on_tree_double_click)
        self.table.itemSelectionChanged.connect(self._sync_toolbar)
        self.table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self._empty_page = QWidget()
        self._empty_page.setObjectName("hostsSurface")
        empty_outer = QVBoxLayout(self._empty_page)
        empty_outer.setContentsMargins(24, 24, 24, 24)
        empty_outer.addStretch(1)
        empty_card = QFrame()
        empty_card.setObjectName("emptyCard")
        empty_card.setMaximumWidth(440)
        empty_inner = QVBoxLayout(empty_card)
        empty_inner.setContentsMargins(28, 28, 28, 28)
        empty_inner.setSpacing(10)
        self._empty_title = QLabel()
        self._empty_title.setObjectName("emptyTitle")
        self._empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_hint = QLabel()
        self._empty_hint.setObjectName("emptyHint")
        self._empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._empty_hint.setWordWrap(True)
        self._empty_add = QPushButton()
        self._empty_add.setObjectName("primaryButton")
        self._empty_add.clicked.connect(self.add_host)
        empty_inner.addWidget(self._empty_title)
        empty_inner.addWidget(self._empty_hint)
        empty_inner.addWidget(self._empty_add, 0, Qt.AlignmentFlag.AlignCenter)
        empty_outer.addWidget(empty_card, 0, Qt.AlignmentFlag.AlignHCenter)
        empty_outer.addStretch(2)
        self._empty_page.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._empty_page.customContextMenuRequested.connect(self._show_empty_context_menu)

        self._filter_empty = QLabel()
        self._filter_empty.setObjectName("emptyHint")
        self._filter_empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._filter_empty.setWordWrap(True)

        self._stack = QStackedWidget()
        self._stack.addWidget(self._empty_page)
        self._stack.addWidget(self._filter_empty)
        self._stack.addWidget(self.table)
        hosts_layout.addWidget(self._stack, 1)
        canvas_layout.addWidget(hosts_card, 1)
        root.addWidget(canvas, 1)

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
            menu.addMenu(self._build_graphical_apps_menu())
            menu.addSeparator()
            menu.addAction(self._actions["shutdown_remote"])
            menu.addSeparator()
            menu.addAction(self._actions["provision"])
            menu.addAction(self._actions["list_sessions"])
            menu.addAction(self._actions["delete_tmux"])
            menu.addAction(self._actions["close_terminal"])
            menu.addSeparator()
            menu.addAction(self._actions["edit"])
            menu.addMenu(self._build_move_to_group_menu())
            menu.addAction(self._actions["manage_groups"])
            menu.addAction(self._actions["delete"])
            menu.addSeparator()
            menu.addAction(self._actions["refresh"])
        else:
            menu.addAction(self._actions["add"])
            menu.addAction(self._actions["manage_groups"])
            menu.addAction(self._actions["refresh"])
        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _build_graphical_apps_menu(self) -> QMenu:
        submenu = QMenu(t("action.graphical_apps"), self)
        host = self._selected_host()
        if host is not None and host.graphical_apps:
            for app in host.graphical_apps:
                action = submenu.addAction(app.name)
                action.triggered.connect(
                    lambda _checked=False, selected=app: self.launch_graphical_app(selected)
                )
            submenu.addSeparator()
        submenu.addAction(self._actions["configure_graphical_apps"])
        return submenu

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
        menu.exec(self._empty_page.mapToGlobal(pos))

    def _retranslate_ui(self) -> None:
        self.setWindowTitle(t("app.title"))
        self._brand.setText(t("app.brand"))
        self._subtitle.setText(t("app.subtitle"))
        self._host_menu.setTitle(t("menu.host"))
        self._connection_menu.setTitle(t("menu.connection"))
        self._config_menu.setTitle(t("menu.config"))
        self._lang_menu.setTitle(t("menu.language"))
        self._empty_title.setText(t("empty.title"))
        self._empty_hint.setText(t("empty.hint"))
        self._empty_add.setText(t("empty.add"))
        self._search.setPlaceholderText(t("search.placeholder"))
        self._connect_btn.setText(t("action.connect"))
        self._add_btn.setText(t("action.add"))
        self._edit_btn.setText(t("action.edit"))
        if self._tray is not None:
            self._tray.setToolTip(t("app.title"))
        if self._tray_show_action is not None:
            self._tray_show_action.setText(t("tray.show"))
        if self._tray_quit_action is not None:
            self._tray_quit_action.setText(t("tray.quit"))

        action_keys = {
            "add": "action.add",
            "edit": "action.edit",
            "delete": "action.delete",
            "manage_groups": "action.manage_groups",
            "provision": "action.provision",
            "connect_tmux": "action.connect_tmux",
            "connect_plain": "action.connect_plain",
            "configure_graphical_apps": "action.configure_graphical_apps",
            "shutdown_remote": "action.shutdown_remote",
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
        group_brush = QBrush(QColor("#f4f7fb"))
        query = self._search.text().strip().lower()
        visible = 0

        for group_name, hosts in self._config.hosts_by_group():
            hosts = [host for host in hosts if self._host_matches(host, group_name, query)]
            if not hosts:
                continue
            visible += len(hosts)
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
                group_item.setForeground(col, QColor("#1e293b"))
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

        if not self._config.hosts:
            self._stack.setCurrentWidget(self._empty_page)
        elif visible == 0:
            self._filter_empty.setText(t("filter.empty", query=self._search.text().strip()))
            self._stack.setCurrentWidget(self._filter_empty)
        else:
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

        self._sync_toolbar()
        self.set_status(t("status.hosts_count", count=len(self._config.hosts)))

    def _host_matches(self, host: Host, group_name: str, query: str) -> bool:
        if not query:
            return True
        if group_name and group_name != UNGROUPED and query in group_name.lower():
            return True
        haystack = " ".join(
            [
                host.name,
                host.hostname,
                host.user,
                host.target,
                host.notes,
                host.tmux_session,
                host.group or "",
            ]
        ).lower()
        return query in haystack

    def _sync_toolbar(self) -> None:
        has_host = self._selected_host() is not None
        self._connect_btn.setEnabled(has_host)
        self._edit_btn.setEnabled(has_host)

    def _build_tray(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        icon = self.windowIcon()
        if icon.isNull() and _ICON_PATH.is_file():
            icon = QIcon(str(_ICON_PATH))
        self._tray = QSystemTrayIcon(icon, self)
        menu = QMenu(self)
        self._tray_show_action = QAction(self)
        self._tray_quit_action = QAction(self)
        self._tray_show_action.triggered.connect(self._restore_from_tray)
        self._tray_quit_action.triggered.connect(self._quit_from_tray)
        menu.addAction(self._tray_show_action)
        menu.addSeparator()
        menu.addAction(self._tray_quit_action)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray.show()

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._restore_from_tray()

    def _restore_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def _quit_from_tray(self) -> None:
        self._quitting = True
        self.close()

    def _can_use_tray(self) -> bool:
        return self._tray is not None and QSystemTrayIcon.isSystemTrayAvailable()

    def _ask_close_box(self) -> QMessageBox:
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(t("tray.close_title"))
        box.setText(t("tray.close_prompt"))
        box.setInformativeText(t("tray.close_hint"))
        minimize = box.addButton(t("tray.minimize"), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(t("tray.quit"), QMessageBox.ButtonRole.DestructiveRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        self._fit_close_buttons(box)
        box.setDefaultButton(minimize)
        return box

    def _ask_close_choice(self) -> str:
        box = self._ask_close_box()
        minimize = next(b for b in box.buttons() if b.text() == t("tray.minimize"))
        quit_btn = next(b for b in box.buttons() if b.text() == t("tray.quit"))
        box.exec()
        clicked = box.clickedButton()
        if clicked is minimize:
            return "minimize"
        if clicked is quit_btn:
            return "quit"
        return "cancel"

    def _fit_close_buttons(self, box: QMessageBox) -> None:
        """Give each close-dialog button enough width for its full label."""
        total = 24
        for button in box.buttons():
            text_width = button.fontMetrics().horizontalAdvance(button.text())
            width = text_width + 48
            button.setMinimumWidth(width)
            total += width + 12
        box.setMinimumWidth(max(box.sizeHint().width(), total))

    def _shutdown_session(self) -> None:
        self._closing = True
        self._overlay.hide_state()
        if self._voice_done_timer is not None:
            self._voice_done_timer.stop()
        for listener in list(self._voice_listeners.values()):
            listener.stop()
        self._voice_listeners.clear()
        if self._recorder is not None and self._recorder.is_recording():
            self._recorder.stop()
        if self._tray is not None:
            self._tray.hide()

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

    def configure_graphical_apps_selected(self) -> None:
        host = self._selected_host()
        if host is None:
            QMessageBox.information(self, t("dialog.no_selection"), t("msg.select_host"))
            return
        dlg = GraphicalAppsDialog(host, self)
        if dlg.exec() != GraphicalAppsDialog.DialogCode.Accepted:
            return
        host.graphical_apps = dlg.result_apps()
        self._config.upsert_host(host)
        self._persist()
        self._reload_table(preserve_config=True)
        self.set_status(t("status.graphics_saved", name=host.name))

    def shutdown_selected(self) -> None:
        host = self._selected_host()
        if host is None:
            QMessageBox.information(self, t("dialog.no_selection"), t("msg.select_host"))
            return
        if not host.provisioned and not host.key_name:
            reply = QMessageBox.question(
                self,
                t("dialog.not_provisioned"),
                t("msg.connect_anyway"),
            )
            if reply != QMessageBox.StandardButton.Yes:
                return
        reply = QMessageBox.warning(
            self,
            t("dialog.shutdown_remote"),
            t("msg.shutdown_confirm", name=host.name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            result = launch_in_terminal(
                build_shutdown_ssh_argv(host),
                keep_open_on_failure=False,
                host_id=host.id,
                host_name=host.name,
            )
        except TerminalError as exc:
            QMessageBox.critical(self, t("dialog.terminal_error"), str(exc))
            self.set_status(str(exc))
            return
        self._launched[result.launch_id] = result
        self.set_status(t("status.shutdown_launched", name=host.name))

    def launch_graphical_app(self, app: GraphicalApp) -> None:
        host = self._selected_host()
        if host is None:
            QMessageBox.information(self, t("dialog.no_selection"), t("msg.select_host"))
            return
        try:
            argv = build_graphical_ssh_argv(host, app)
            result = launch_process(
                argv,
                host_id=host.id,
                host_name=host.name,
            )
        except (GraphicalAppError, TerminalError) as exc:
            QMessageBox.critical(self, t("dialog.graphics_error"), str(exc))
            self.set_status(str(exc))
            return
        host.mark_connected()
        self._config.upsert_host(host)
        self._persist()
        self._launched[result.launch_id] = result
        self._reload_table(preserve_config=True)
        self.set_status(t("status.graphics_launched", app=app.name, name=host.name))

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

    def showEvent(self, event: QShowEvent) -> None:
        super().showEvent(event)
        if self._placed_on_screen:
            return
        self._place_on_screen()
        self._placed_on_screen = True

    def _place_on_screen(self) -> None:
        screen = self.screen()
        if screen is None:
            app = QApplication.instance()
            screen = app.primaryScreen() if app is not None else None
        if screen is None:
            return
        available = screen.availableGeometry()
        frame = self.frameGeometry()
        size = frame.size() if frame.isValid() else self.size()
        self.move(initial_window_position(available, size))

    def closeEvent(self, event: QCloseEvent) -> None:
        if not self._quitting and self._can_use_tray():
            choice = self._ask_close_choice()
            if choice == "minimize":
                event.ignore()
                self.hide()
                if self._tray is not None:
                    self._tray.show()
                    self._tray.showMessage(
                        t("tray.minimized"),
                        t("tray.minimized_hint"),
                        QSystemTrayIcon.MessageIcon.Information,
                        4000,
                    )
                return
            if choice != "quit":
                event.ignore()
                return
            self._quitting = True
        self._quitting = True
        self._shutdown_session()
        event.accept()
        app = QApplication.instance()
        if app is not None:
            app.quit()

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
