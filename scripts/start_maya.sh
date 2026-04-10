#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="/home/patolizo/Documents/GitHub/maya"

cd "$ROOT_DIR"

if [ -f ".venv/bin/activate" ]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
fi

exec python app.py
