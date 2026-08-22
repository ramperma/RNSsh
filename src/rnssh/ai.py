"""AI providers (Gemini / DeepSeek) and their persisted configuration."""

from __future__ import annotations

import base64
import json
import os
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

import yaml

from rnssh.paths import ensure_app_dirs, secrets_dir

GEMINI = "gemini"
DEEPSEEK = "deepseek"

DEFAULT_MODEL = {
    GEMINI: "gemini-2.5-flash",
    DEEPSEEK: "deepseek-v4-flash",
}

MODEL_CHOICES = {
    GEMINI: ["gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-2.5-pro"],
    DEEPSEEK: ["deepseek-v4-flash", "deepseek-v4-pro"],
}

_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
_DEEPSEEK_URL = "https://api.deepseek.com/chat/completions"
_DEEPSEEK_MODELS_URL = "https://api.deepseek.com/models"

_COMMAND_PROMPT = (
    "You are an Ubuntu shell expert. Return ONLY the exact Ubuntu bash command(s) "
    "needed for this request. No explanation, no markdown, no prompt symbols. "
    "Do not invent files, hosts, passwords, or destructive steps unless explicitly requested.\n"
    "Request: {request}"
)

_TRANSCRIBE_PROMPT = (
    "Transcribe the spoken request exactly, in the language spoken, as plain text. "
    "Output only the transcription, no explanation."
)


class AIError(Exception):
    """AI provider request or response failed."""


_KEYRING_SERVICE = "rnssh"


def _keyring_backend():
    """Return the OS keyring module if usable, else None."""
    try:
        import keyring  # type: ignore[import-not-found]

        keyring.get_keyring()
        return keyring
    except Exception:
        return None


def _read_keyring_key(provider: str) -> str | None:
    backend = _keyring_backend()
    if backend is None:
        return None
    try:
        value = backend.get_password(_KEYRING_SERVICE, provider)
        return value or None
    except Exception:
        return None


def _write_keyring_key(provider: str, key: str) -> bool:
    """Store/delete a key in the OS keyring; False when unavailable."""
    backend = _keyring_backend()
    if backend is None:
        return False
    try:
        if key:
            backend.set_password(_KEYRING_SERVICE, provider, key)
        else:
            backend.delete_password(_KEYRING_SERVICE, provider)
        return True
    except Exception:
        return False


def ai_storage_mode() -> str:
    """Return ``"keyring"`` when the OS keyring is usable, else ``"file"``."""
    return "keyring" if _keyring_backend() is not None else "file"


def _cfg_path() -> Path:
    return secrets_dir() / "ai-config.yaml"


def default_ai_config() -> dict:
    return {
        GEMINI: {"api_key": "", "model": DEFAULT_MODEL[GEMINI]},
        DEEPSEEK: {"api_key": "", "model": DEFAULT_MODEL[DEEPSEEK]},
        "default_provider": GEMINI,
    }


def load_ai_config() -> dict:
    """Return the persisted AI config merged with defaults.

    API keys come from the OS keyring when available; otherwise they are
    read from the secrets file (0600). Models and the default provider are
    always stored in the file.
    """
    cfg = default_ai_config()
    path = _cfg_path()
    if not path.is_file():
        for provider in (GEMINI, DEEPSEEK):
            keyring_key = _read_keyring_key(provider)
            if keyring_key:
                cfg[provider]["api_key"] = keyring_key
        return cfg
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return cfg
    for provider in (GEMINI, DEEPSEEK):
        entry = data.get(provider) or {}
        keyring_key = _read_keyring_key(provider)
        if keyring_key is not None:
            cfg[provider]["api_key"] = keyring_key
        else:
            cfg[provider]["api_key"] = str(entry.get("api_key") or "").strip()
        model = str(entry.get("model") or "").strip()
        cfg[provider]["model"] = model or DEFAULT_MODEL[provider]
    default = str(data.get("default_provider") or "")
    if default in (GEMINI, DEEPSEEK):
        cfg["default_provider"] = default
    return cfg


def save_ai_config(cfg: dict) -> None:
    """Persist models + default provider to the secrets file (0600).

    API keys go to the OS keyring; when the keyring is unavailable they are
    kept inside the secrets file instead (plaintext, 0600) so nothing is lost.
    """
    ensure_app_dirs()
    payload: dict = {}
    for provider in (GEMINI, DEEPSEEK):
        key = str((cfg.get(provider) or {}).get("api_key") or "").strip()
        model = str((cfg.get(provider) or {}).get("model") or "").strip()
        entry: dict = {"model": model or DEFAULT_MODEL[provider]}
        if not _write_keyring_key(provider, key):
            entry["api_key"] = key
        payload[provider] = entry
    default = str(cfg.get("default_provider") or "")
    payload["default_provider"] = default if default in (GEMINI, DEEPSEEK) else GEMINI
    path = _cfg_path()
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
    try:
        tmp.chmod(0o600)
    except OSError:
        pass
    os.replace(tmp, path)


def _provider_key_model(provider: str) -> tuple[str, str]:
    if provider not in (GEMINI, DEEPSEEK):
        raise AIError(f"Unknown provider: {provider}")
    cfg = load_ai_config()
    entry = cfg.get(provider) or {}
    key = str(entry.get("api_key") or "").strip()
    model = str(entry.get("model") or "").strip() or DEFAULT_MODEL[provider]
    if not key:
        raise AIError(f"Configure the {provider} API key first (Configuration → AI)")
    return key, model


def _post(url: str, payload: dict, headers: dict[str, str] | None = None) -> dict:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    try:
        with urlopen(request, timeout=45) as response:  # noqa: S310 - fixed provider URLs
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        detail = getattr(exc, "reason", str(exc))
        raise AIError(f"AI request failed: {detail}") from exc


def _get(url: str, headers: dict[str, str] | None = None, *, timeout: int = 30) -> dict:
    request = Request(
        url,
        headers={"Content-Type": "application/json", **(headers or {})},
        method="GET",
    )
    try:
        with urlopen(request, timeout=timeout) as response:  # noqa: S310 - fixed provider URLs
            return json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        detail = getattr(exc, "reason", str(exc))
        raise AIError(f"AI request failed: {detail}") from exc


def _command(text: str) -> str:
    """Strip prose and markdown fences from a provider answer."""
    fenced = re.search(r"```(?:bash|sh|shell)?\s*\n?(.*?)```", text, re.I | re.S)
    result = (fenced.group(1) if fenced else text).strip()
    result = re.sub(r"^(?:command|comando)\s*:\s*", "", result, flags=re.I)
    lines = [line.strip() for line in result.splitlines() if line.strip()]
    if not lines:
        raise AIError("The provider returned no command")
    refusal = ("cannot", "can't", "sorry", "unable", "refus", "lo siento", "no puedo", "no se puede")
    if any(token in lines[0].lower() for token in refusal):
        raise AIError("The provider did not return a command")
    return "\n".join(lines)


def list_models(provider: str) -> list[str]:
    """Return the provider's currently available models, fetched live.

    Falls back to the known static list when the provider is not configured
    yet or the network request fails, so the UI always has something usable.
    """
    cfg = load_ai_config()
    key = str((cfg.get(provider) or {}).get("api_key") or "").strip()
    if not key:
        return list(MODEL_CHOICES.get(provider, []))
    try:
        if provider == GEMINI:
            url = f"https://generativelanguage.googleapis.com/v1beta/models?pageSize=100&key={quote(key)}"
            data = _get(url, timeout=15)
            models: list[str] = []
            for item in data.get("models", []):
                name = str(item.get("name") or "")
                methods = item.get("supportedGenerationMethods") or []
                if not name.startswith("models/gemini-"):
                    continue
                if "generateContent" not in methods:
                    continue
                short = name.removeprefix("models/")
                if "preview" in short or "experimental" in short or "-image" in short:
                    continue
                models.append(short)
            return sorted(set(models))
        if provider == DEEPSEEK:
            data = _get(_DEEPSEEK_MODELS_URL, {"Authorization": f"Bearer {key}"}, timeout=15)
            ids = [str(item.get("id") or "") for item in data.get("data", [])]
            return sorted(m for m in ids if m)
    except AIError:
        pass
    return list(MODEL_CHOICES.get(provider, []))


def generate_command(provider: str, request: str) -> str:
    """Ask the selected provider for a command; returns plain shell text."""
    request = (request or "").strip()
    if not request:
        raise AIError("Describe what you want to do first")
    key, model = _provider_key_model(provider)
    prompt = _COMMAND_PROMPT.format(request=request)

    if provider == GEMINI:
        data = _post(
            _GEMINI_URL.format(model=quote(model)),
            {"contents": [{"parts": [{"text": prompt}]}]},
            {"x-goog-api-key": key},
        )
        try:
            text = data["candidates"][0]["content"]["parts"][0]["text"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIError("Gemini returned an invalid response") from exc
    elif provider == DEEPSEEK:
        data = _post(
            _DEEPSEEK_URL,
            {
                "model": model,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0,
            },
            {"Authorization": f"Bearer {key}"},
        )
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIError("DeepSeek returned an invalid response") from exc
    else:
        raise AIError(f"Unknown provider: {provider}")
    return _command(str(text))


def transcribe_audio(wav: bytes) -> str:
    """Transcribe a WAV clip with Gemini (required for voice input)."""
    if not wav:
        raise AIError("No audio was recorded")
    key, model = _provider_key_model(GEMINI)
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": _TRANSCRIBE_PROMPT},
                    {
                        "inline_data": {
                            "mime_type": "audio/wav",
                            "data": base64.b64encode(wav).decode("ascii"),
                        }
                    },
                ]
            }
        ]
    }
    data = _post(
        _GEMINI_URL.format(model=quote(model)),
        payload,
        {"x-goog-api-key": key},
    )
    try:
        text = data["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, TypeError) as exc:
        raise AIError("Gemini returned an invalid response") from exc
    return str(text).strip()
