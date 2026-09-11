"""Configure graphical applications launched remotely through SSH X11."""

from __future__ import annotations

from copy import deepcopy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from rnssh.i18n import t
from rnssh.models import GraphicalApp, Host


class GraphicalAppEditor(QDialog):
    def __init__(self, parent=None, app: GraphicalApp | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("graphics.edit_title") if app else t("graphics.add_title"))
        self._result: GraphicalApp | None = None
        self.name_edit = QLineEdit()
        self.command_edit = QLineEdit()
        self.command_edit.setPlaceholderText(t("graphics.command_placeholder"))
        self.directory_edit = QLineEdit()
        self.directory_edit.setPlaceholderText("/home/user/project")
        self.trusted_check = QCheckBox(t("graphics.trusted"))

        form = QFormLayout()
        form.addRow(t("graphics.name"), self.name_edit)
        form.addRow(t("graphics.command"), self.command_edit)
        form.addRow(t("graphics.directory"), self.directory_edit)
        form.addRow("", self.trusted_check)

        help_label = QLabel(t("graphics.editor_help"))
        help_label.setWordWrap(True)
        help_label.setObjectName("settingsHelp")
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(help_label)
        layout.addLayout(form)
        layout.addWidget(buttons)

        if app:
            self.name_edit.setText(app.name)
            self.command_edit.setText(app.command)
            self.directory_edit.setText(app.working_directory)
            self.trusted_check.setChecked(app.trusted_x11)
        self.resize(520, 250)

    def result_app(self) -> GraphicalApp | None:
        return self._result

    def _accept(self) -> None:
        name = self.name_edit.text().strip()
        command = self.command_edit.text().strip()
        if not name or not command:
            QMessageBox.warning(self, t("graphics.missing_title"), t("graphics.missing_msg"))
            return
        self._result = GraphicalApp(
            name=name,
            command=command,
            working_directory=self.directory_edit.text().strip(),
            trusted_x11=self.trusted_check.isChecked(),
        )
        self.accept()


class GraphicalAppsDialog(QDialog):
    """Edit the graphical-app shortcuts stored on one host."""

    def __init__(self, host: Host, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("graphics.title", name=host.name))
        self.setMinimumSize(650, 430)
        self._apps = deepcopy(host.graphical_apps)
        self._build_ui()
        self._refresh()

    def result_apps(self) -> list[GraphicalApp]:
        return self._apps

    def _build_ui(self) -> None:
        help_label = QLabel(t("graphics.help"))
        help_label.setWordWrap(True)
        help_label.setObjectName("settingsHelp")

        self.list = QListWidget()
        self.list.itemDoubleClicked.connect(lambda _item: self._edit())
        self.list.currentRowChanged.connect(lambda _row: self._update_buttons())

        buttons = QHBoxLayout()
        self.add_button = QPushButton(t("graphics.add"))
        self.add_button.clicked.connect(self._add)
        self.common_button = QPushButton(t("graphics.add_common"))
        self.common_button.clicked.connect(self._add_common)
        self.edit_button = QPushButton(t("graphics.edit"))
        self.edit_button.clicked.connect(self._edit)
        self.remove_button = QPushButton(t("graphics.remove"))
        self.remove_button.clicked.connect(self._remove)
        buttons.addWidget(self.add_button)
        buttons.addWidget(self.common_button)
        buttons.addStretch(1)
        buttons.addWidget(self.edit_button)
        buttons.addWidget(self.remove_button)

        dialog_buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        dialog_buttons.accepted.connect(self.accept)
        dialog_buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(help_label)
        layout.addWidget(self.list, 1)
        layout.addLayout(buttons)
        layout.addWidget(dialog_buttons)

    def _refresh(self) -> None:
        self.list.clear()
        for app in self._apps:
            item = QListWidgetItem(f"{app.name}  ·  {app.command}")
            item.setData(Qt.ItemDataRole.UserRole, app)
            self.list.addItem(item)
        self._update_buttons()

    def _update_buttons(self) -> None:
        has_selection = self.list.currentRow() >= 0
        self.edit_button.setEnabled(has_selection)
        self.remove_button.setEnabled(has_selection)

    def _add(self) -> None:
        dialog = GraphicalAppEditor(self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.result_app():
            self._apps.append(dialog.result_app())  # type: ignore[arg-type]
            self._refresh()

    def _add_common(self) -> None:
        choices = [
            (t("graphics.preset_browser"), "firefox"),
            (t("graphics.preset_dolphin"), "dolphin"),
            (t("graphics.preset_thunar"), "thunar"),
            (t("graphics.preset_python"), "python3 /path/to/app.py"),
        ]
        menu = self.sender()
        popup = self._common_menu(choices)
        popup.exec(menu.mapToGlobal(menu.rect().bottomLeft()))

    def _common_menu(self, choices: list[tuple[str, str]]):
        from PySide6.QtWidgets import QMenu

        menu = QMenu(self)
        for name, command in choices:
            action = menu.addAction(name)
            action.triggered.connect(
                lambda _checked=False, n=name, c=command: self._append_app(n, c)
            )
        return menu

    def _append_app(self, name: str, command: str) -> None:
        self._apps.append(GraphicalApp(name, command))
        self._refresh()
        self.list.setCurrentRow(len(self._apps) - 1)

    def _edit(self) -> None:
        row = self.list.currentRow()
        if row < 0:
            return
        dialog = GraphicalAppEditor(self, self._apps[row])
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.result_app():
            self._apps[row] = dialog.result_app()  # type: ignore[assignment]
            self._refresh()
            self.list.setCurrentRow(row)

    def _remove(self) -> None:
        row = self.list.currentRow()
        if row >= 0:
            self._apps.pop(row)
            self._refresh()
