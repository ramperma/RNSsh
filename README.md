# RNSsh

Python + PySide6 SSH connection manager for Linux (cross-platform ready). Store hosts, auto-provision Ed25519 keys onto servers, and open your **OS terminal** attached to persistent remote **tmux** sessions.

## Features

- Add / edit / delete SSH hosts
- UI language: **English** or **Spanish** (menu **Language** / **Idioma**; saved in config)
- Clean professional Qt stylesheet (QSS) — desktop UI, not web/Tailwind
- Actions via top menus and **right-click context menu** on each host row (no cramped button bar)
- Generate Ed25519 key pairs under `~/.config/rnssh/keys/`
- One-time password bootstrap to install the public key on the server (password never stored)
- **Connect (tmux)** opens the system terminal with `tmux new-session -A -s <name>` so work survives disconnects
- **Connect (plain SSH)** for a normal login shell
- List remote tmux sessions and attach to a chosen one
- Close a tracked terminal window from the app (best-effort)

## Requirements

- Python 3.10+
- OpenSSH client (`ssh`)
- A terminal emulator (gnome-terminal, konsole, xfce4-terminal, kitty, alacritty, xterm, …)
- Remote hosts with SSH and preferably `tmux`

## Install

```bash
cd /opt/CodGit/RNSsh
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Run

```bash
rnssh
# or
python -m rnssh
```

Optional: force a terminal emulator:

```bash
export RNSSH_TERMINAL=kitty
rnssh
```

## Typical workflow

1. **Add** a host (name, hostname, user, port, default tmux session name).
2. Select it → **Provision keys** → enter the SSH password once.
3. Confirm the host key fingerprint shown after success.
4. **Connect (tmux)** — a maximizable system terminal opens inside the named session.
5. Detach with `Ctrl-b` then `d`, or close the window; processes keep running in tmux.
6. **Connect (tmux)** again to resume the same session.

## Config layout

```
~/.config/rnssh/
  config.yaml          # host list (no passwords)
  keys/                # private keys (0600) and .pub files
  secrets/             # optional per-host login passwords (0600), for Android interop
```

## Interoperability (SSHAndroid)

Backups use the shared **`rnssh-backup`** ZIP format (version **3**):

| Entry | Contents |
|-------|----------|
| `manifest.json` | `format: rnssh-backup`, version, crypto metadata |
| `config.yaml` | Host metadata only (no passwords) |
| `keys/` | OpenSSH key files, encrypted when a backup password is set |
| `secrets/<host_id>.password` | Optional SSH login passwords (UTF-8), same encryption as keys |

**Crypto (RNS1 blobs):** PBKDF2-HMAC-SHA256 (**600_000** iterations), 16-byte salt, 12-byte nonce, **AES-256-GCM**. Wire layout: `RNS1` + salt + nonce + ciphertext+tag.

SSHAndroid exports/imports this ZIP. Older Android `SSH_BACKUP_V1` `.dat` files remain importable on Android only. RNSsh still restores version **2** archives (keys only, no `secrets/`).

Golden vector for cross-implementation checks: [`tests/fixtures/rns1_golden_vector.json`](tests/fixtures/rns1_golden_vector.json).

## Tests

```bash
pytest
```

## Notes

- Jump-host key provisioning and remote session listing are limited in v1 (direct hosts only for provision/list).
- Host keys are accepted automatically during provision (`accept-new` style); verify the fingerprint in the success dialog.
- Detaching from tmux leaves work running; **Close terminal** only kills the local terminal process tracked in this app session.
- Login passwords are never written to `config.yaml`; they live under `secrets/` when present (e.g. restored from Android).
