#!/bin/bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

VENV_DIR="${VENV_DIR:-$ROOT_DIR/.venv}"
PYTHON_BIN="${PYTHON_BIN:-python3}"

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "错误: 未找到 python3，请先安装 Python 3"
  exit 1
fi

if [ ! -d "$VENV_DIR" ]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

VENV_PY="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

"$VENV_PY" -m pip install -U pip >/dev/null
"$VENV_PIP" install -r "$ROOT_DIR/requirements-cli.txt"

exec "$VENV_PY" "$ROOT_DIR/scripts/ai_proxy_cli.py" "${@:-wizard}"
