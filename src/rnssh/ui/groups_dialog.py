"""Manage connection groups and assign hosts to them."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from rnssh.i18n import t
from rnssh.models import AppConfig


class GroupsDialog(QDialog):
    def __init__(self, config: AppConfig, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("groups.title"))
        self._config = config
        self._changed = False

        self._help = QLabel(t("groups.help"))
        self._help.setWordWrap(True)

        self._list = QListWidget()
        self._list.currentItemChanged.connect(lambda *_: self._update_assign_enabled())
        self._reload()

        self._add_btn = QPushButton(t("groups.add"))
        self._rename_btn = QPushButton(t("groups.rename"))
        self._delete_btn = QPushButton(t("groups.delete"))
        self._assign_btn = QPushButton(t("groups.assign"))
        self._add_btn.clicked.connect(self._add)
        self._rename_btn.clicked.connect(self._rename)
        self._delete_btn.clicked.connect(self._delete)
        self._assign_btn.clicked.connect(self._assign_hosts)

        row = QHBoxLayout()
        row.addWidget(self._add_btn)
        row.addWidget(self._rename_btn)
        row.addWidget(self._delete_btn)
        row.addWidget(self._assign_btn)
        row.addStretch(1)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        close = buttons.button(QDialogButtonBox.StandardButton.Close)
        if close:
            close.clicked.connect(self.accept)

        root = QVBoxLayout(self)
        root.addWidget(self._help)
        root.addWidget(self._list, 1)
        root.addLayout(row)
        root.addWidget(buttons)
        self.resize(480, 400)
        self._update_assign_enabled()

    def changed(self) -> bool:
        return self._changed

    def _update_assign_enabled(self) -> None:
        self._assign_btn.setEnabled(self._selected_name() is not None and bool(self._config.hosts))

    def _reload(self) -> None:
        self._list.clear()
        for name in self._config.known_groups():
            count = sum(1 for h in self._config.hosts if (h.group or "") == name)
            self._list.addItem(t("groups.item", name=name, count=count))
            self._list.item(self._list.count() - 1).setData(Qt.ItemDataRole.UserRole, name)
        self._update_assign_enabled()

    def _selected_name(self) -> str | None:
        item = self._list.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)

    def _add(self) -> None:
        name, ok = QInputDialog.getText(self, t("groups.add"), t("groups.name_prompt"))
        if not ok:
            return
        name = name.strip()
        if not name:
            return
        if name in self._config.known_groups():
            QMessageBox.information(self, t("groups.title"), t("groups.exists", name=name))
            return
        self._config.ensure_group(name)
        self._changed = True
        self._reload()

    def _rename(self) -> None:
        old = self._selected_name()
        if not old:
            QMessageBox.information(self, t("groups.title"), t("groups.select_first"))
            return
        new, ok = QInputDialog.getText(
            self, t("groups.rename"), t("groups.name_prompt"), text=old
        )
        if not ok:
            return
        new = new.strip()
        if not new or new == old:
            return
        self._config.rename_group(old, new)
        self._changed = True
        self._reload()

    def _delete(self) -> None:
        name = self._selected_name()
        if not name:
            QMessageBox.information(self, t("groups.title"), t("groups.select_first"))
            return
        count = sum(1 for h in self._config.hosts if (h.group or "") == name)
        reply = QMessageBox.question(
            self,
            t("groups.delete"),
            t("groups.delete_confirm", name=name, count=count),
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._config.delete_group(name)
        self._changed = True
        self._reload()

    def _assign_hosts(self) -> None:
        group = self._selected_name()
        if not group:
            QMessageBox.information(self, t("groups.title"), t("groups.select_first"))
            return
        if not self._config.hosts:
            QMessageBox.information(self, t("groups.title"), t("groups.assign_no_hosts"))
            return

        dlg = _AssignHostsDialog(self._config, group, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        selected_ids = dlg.selected_host_ids()
        for host in self._config.hosts:
            if host.id in selected_ids:
                if (host.group or "") != group:
                    host.group = group
                    self._changed = True
            elif (host.group or "") == group:
                host.group = ""
                self._changed = True
        if self._changed:
            self._config.ensure_group(group)
            self._reload()


class _AssignHostsDialog(QDialog):
    """Multi-select hosts that should belong to a group."""

    def __init__(self, config: AppConfig, group: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle(t("groups.assign_title", name=group))
        self._ids: set[str] = set()

        help_lbl = QLabel(t("groups.assign_help", name=group))
        help_lbl.setWordWrap(True)

        self._list = QListWidget()
        for host in config.hosts:
            label = f"{host.name}  ({host.target})"
            if (host.group or "") and host.group != group:
                label = f"{label}  — {host.group}"
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, host.id)
            item.setFlags(
                item.flags()
                | Qt.ItemFlag.ItemIsUserCheckable
                | Qt.ItemFlag.ItemIsEnabled
            )
            checked = (host.group or "") == group
            item.setCheckState(
                Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
            )
            self._list.addItem(item)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        root = QVBoxLayout(self)
        root.addWidget(help_lbl)
        root.addWidget(self._list, 1)
        root.addWidget(buttons)
        self.resize(440, 360)

    def selected_host_ids(self) -> set[str]:
        ids: set[str] = set()
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.checkState() == Qt.CheckState.Checked:
                host_id = item.data(Qt.ItemDataRole.UserRole)
                if isinstance(host_id, str):
                    ids.add(host_id)
        return ids
