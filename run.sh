#!/usr/bin/env bash
# Launch RNSsh from the repository (creates .venv and installs if needed).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

PYTHON="${PYTHON:-python3}"
VENV_DIR="${ROOT}/.venv"
VENV_PY="${VENV_DIR}/bin/python"
VENV_RNSSH="${VENV_DIR}/bin/rnssh"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "error: Python 3.10+ is required (python3 not found)" >&2
  exit 1
fi

if [[ ! -x "$VENV_PY" ]]; then
  echo "Creating virtualenv in ${VENV_DIR} ..."
  "$PYTHON" -m venv "$VENV_DIR"
fi

if [[ ! -x "$VENV_RNSSH" ]]; then
  echo "Installing rnssh (editable) ..."
  "$VENV_PY" -m pip install -U pip
  "$VENV_PY" -m pip install -e "${ROOT}"
fi

# Optional: force a terminal emulator, e.g. export RNSSH_TERMINAL=kitty
exec "$VENV_RNSSH" "$@"
