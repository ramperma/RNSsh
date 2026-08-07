"""Tests for i18n and language preference."""

from __future__ import annotations

from pathlib import Path

import pytest

from rnssh import i18n
from rnssh.models import AppConfig, Host
from rnssh.storage import load_config, save_config
import rnssh.paths as paths


@pytest.fixture(autouse=True)
def reset_language() -> None:
    i18n.set_language("en")
    yield
    i18n.set_language("en")


@pytest.fixture()
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    paths.ensure_app_dirs()
    return tmp_path / "rnssh"


def test_translate_english() -> None:
    i18n.set_language("en")
    assert i18n.t("action.add") == "Add"
    assert i18n.t("status.added", name="box") == "Added box"


def test_translate_spanish() -> None:
    i18n.set_language("es")
    assert i18n.t("action.add") == "Añadir"
    assert i18n.t("menu.language") == "Idioma"
    assert "Provisionando" in i18n.t("status.provisioning", name="srv")


def test_normalize_language() -> None:
    assert i18n.normalize_language("ES") == "es"
    assert i18n.normalize_language("en_US") == "en"
    assert i18n.normalize_language("fr") == "en"


def test_language_persisted(isolated_config: Path) -> None:
    cfg = AppConfig(language="es")
    cfg.upsert_host(Host(name="a", hostname="a.test"))
    save_config(cfg)
    loaded = load_config()
    assert loaded.language == "es"
    assert len(loaded.hosts) == 1


def test_catalogs_have_same_keys() -> None:
    en_keys = set(i18n._STRINGS["en"])
    es_keys = set(i18n._STRINGS["es"])
    assert en_keys == es_keys


def test_delete_tmux_strings() -> None:
    i18n.set_language("en")
    assert "Delete tmux session" in i18n.t("action.delete_tmux")
    assert "Close terminal window" == i18n.t("action.close_terminal")
    confirm = i18n.t("msg.delete_tmux_confirm", session="work", name="box")
    assert "work" in confirm and "box" in confirm

    i18n.set_language("es")
    assert "Eliminar sesión tmux" in i18n.t("action.delete_tmux")
    assert "Cerrar ventana del terminal" == i18n.t("action.close_terminal")
    assert "work" in i18n.t("msg.delete_tmux_confirm", session="work", name="box")
