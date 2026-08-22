"""Tests for AI config storage and response parsing."""

from __future__ import annotations

from pathlib import Path

import pytest

import rnssh.paths as paths
from rnssh.ai import (
    AIError,
    GEMINI,
    ai_storage_mode,
    generate_command,
    list_models,
    load_ai_config,
    save_ai_config,
)
from rnssh.ai import _command, _cfg_path  # noqa: PLC2701 - white-box unit test
from rnssh.audio import build_wav


class FakeKeyring:
    def __init__(self) -> None:
        self.store: dict[tuple[str, str], str] = {}

    def get_keyring(self):  # noqa: D102
        return self

    def set_password(self, service: str, user: str, password: str) -> None:
        self.store[(service, user)] = password

    def get_password(self, service: str, user: str) -> str | None:
        return self.store.get((service, user))

    def delete_password(self, service: str, user: str) -> None:
        self.store.pop((service, user), None)


@pytest.fixture()
def isolated_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    paths.ensure_app_dirs()


@pytest.fixture()
def fake_keyring(monkeypatch: pytest.MonkeyPatch) -> FakeKeyring:
    fake = FakeKeyring()
    monkeypatch.setattr("rnssh.ai._keyring_backend", lambda: fake)
    return fake


@pytest.fixture()
def no_keyring(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("rnssh.ai._keyring_backend", lambda: None)


def test_config_roundtrip(isolated_config: None, fake_keyring: FakeKeyring) -> None:
    cfg = load_ai_config()
    assert cfg[GEMINI]["model"] == "gemini-2.5-flash"
    assert cfg["deepseek"]["model"] == "deepseek-v4-flash"
    assert cfg["default_provider"] == GEMINI

    cfg[GEMINI]["api_key"] = "secret-gemini"
    cfg[GEMINI]["model"] = "gemini-2.5-pro"
    cfg["deepseek"]["api_key"] = "secret-deepseek"
    cfg["deepseek"]["model"] = "deepseek-reasoner"
    cfg["default_provider"] = "deepseek"
    save_ai_config(cfg)

    loaded = load_ai_config()
    assert loaded[GEMINI]["api_key"] == "secret-gemini"
    assert loaded[GEMINI]["model"] == "gemini-2.5-pro"
    assert loaded["deepseek"]["api_key"] == "secret-deepseek"
    assert loaded["deepseek"]["model"] == "deepseek-reasoner"
    assert loaded["default_provider"] == "deepseek"


def test_config_keeps_secrets_out_of_config_file(isolated_config: None, fake_keyring: FakeKeyring) -> None:
    save_ai_config(load_ai_config())
    assert _cfg_path().is_file()
    assert _cfg_path().parent.name == "secrets"


def test_ai_keys_survive_save_config(isolated_config: None, fake_keyring: FakeKeyring) -> None:
    """The secrets/ orphan cleanup must never delete the AI key file."""
    from rnssh.models import AppConfig
    from rnssh.storage import save_config

    cfg = load_ai_config()
    cfg[GEMINI]["api_key"] = "secret-gemini"
    cfg["deepseek"]["api_key"] = "secret-deepseek"
    save_ai_config(cfg)

    save_config(AppConfig())
    save_config(AppConfig())

    loaded = load_ai_config()
    assert loaded[GEMINI]["api_key"] == "secret-gemini"
    assert loaded["deepseek"]["api_key"] == "secret-deepseek"


def test_keys_go_to_keyring_not_file(isolated_config: None, fake_keyring: FakeKeyring) -> None:
    cfg = load_ai_config()
    cfg[GEMINI]["api_key"] = "secret-gemini"
    save_ai_config(cfg)

    assert fake_keyring.store[("rnssh", GEMINI)] == "secret-gemini"
    assert "api_key" not in _cfg_path().read_text(encoding="utf-8")
    assert load_ai_config()[GEMINI]["api_key"] == "secret-gemini"
    assert ai_storage_mode() == "keyring"


def test_keys_fallback_to_file_without_keyring(isolated_config: None, no_keyring: None) -> None:
    cfg = load_ai_config()
    cfg[GEMINI]["api_key"] = "secret-gemini"
    save_ai_config(cfg)

    assert "api_key" in _cfg_path().read_text(encoding="utf-8")
    assert load_ai_config()[GEMINI]["api_key"] == "secret-gemini"
    assert ai_storage_mode() == "file"


def test_keyring_delete_on_clear(isolated_config: None, fake_keyring: FakeKeyring) -> None:
    cfg = load_ai_config()
    cfg[GEMINI]["api_key"] = "secret-gemini"
    save_ai_config(cfg)
    assert fake_keyring.store.get(("rnssh", GEMINI)) == "secret-gemini"

    cfg[GEMINI]["api_key"] = ""
    save_ai_config(cfg)
    assert ("rnssh", GEMINI) not in fake_keyring.store
    assert load_ai_config()[GEMINI]["api_key"] == ""


def test_command_extraction() -> None:
    assert _command("Here you go:\n```bash\nsudo apt update\n```\nDone.") == "sudo apt update"
    assert _command("comando: ls -la") == "ls -la"
    assert _command("  echo hola  ") == "echo hola"


def test_command_extraction_empty() -> None:
    with pytest.raises(AIError, match="did not return"):
        _command("I am sorry, I cannot help.")


def test_generate_command_unknown_provider(isolated_config: None) -> None:
    with pytest.raises(AIError, match="Unknown provider"):
        generate_command("claude", "update")


def test_build_wav_header() -> None:
    pcm = b"\x00\x00" * 1600
    wav = build_wav(pcm, rate=16000, channels=1, bits=16)
    assert wav[:4] == b"RIFF"
    assert wav[8:12] == b"WAVE"
    assert wav[36:40] == b"data"
    assert int.from_bytes(wav[40:44], "little") == len(pcm)


def test_list_models_without_key_uses_static(isolated_config: None) -> None:
    assert list_models(GEMINI) == ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro"]


def test_list_models_falls_back_on_network_error(
    isolated_config: None, fake_keyring: FakeKeyring, monkeypatch
) -> None:
    cfg = load_ai_config()
    cfg[GEMINI]["api_key"] = "k"
    save_ai_config(cfg)

    def boom(url, headers=None, *, timeout=30):
        raise AIError("offline")

    monkeypatch.setattr("rnssh.ai._get", boom)
    assert list_models(GEMINI) == ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro"]


def test_list_models_gemini_filters_and_sorts(
    isolated_config: None, fake_keyring: FakeKeyring, monkeypatch
) -> None:
    cfg = load_ai_config()
    cfg[GEMINI]["api_key"] = "k"
    save_ai_config(cfg)

    def fake_get(url, headers=None, *, timeout=30):
        return {
            "models": [
                {"name": "models/gemini-2.5-pro", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemini-2.0-flash-preview", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemini-2.5-flash", "supportedGenerationMethods": ["generateContent", "embedContent"]},
                {"name": "models/text-embedding-004", "supportedGenerationMethods": ["embedContent"]},
                {"name": "models/gemini-2.5-flash-experimental", "supportedGenerationMethods": ["generateContent"]},
                {"name": "models/gemini-3-pro-image", "supportedGenerationMethods": ["generateContent"]},
            ]
        }

    monkeypatch.setattr("rnssh.ai._get", fake_get)
    assert list_models(GEMINI) == ["gemini-2.5-flash", "gemini-2.5-pro"]


def test_list_models_deepseek(
    isolated_config: None, fake_keyring: FakeKeyring, monkeypatch
) -> None:
    cfg = load_ai_config()
    cfg["deepseek"]["api_key"] = "k"
    save_ai_config(cfg)

    def fake_get(url, headers=None, *, timeout=30):
        assert url == "https://api.deepseek.com/models"
        assert headers == {"Authorization": "Bearer k"}
        return {"data": [{"id": "deepseek-v4-pro"}, {"id": "deepseek-v4-flash"}]}

    monkeypatch.setattr("rnssh.ai._get", fake_get)
    assert list_models("deepseek") == ["deepseek-v4-flash", "deepseek-v4-pro"]
