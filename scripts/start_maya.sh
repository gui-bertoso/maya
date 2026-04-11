#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/home/patolizo/Documents/GitHub/maya"

cd "$ROOT_DIR"

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "Python was not found for Maya autostart." >&2
  exit 1
fi

exec "$PYTHON_BIN" setup.py
