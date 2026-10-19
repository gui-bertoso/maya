#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
# XWayland supports Maya's floating overlay positioning and keyboard listener.
export QT_QPA_PLATFORM=xcb
if [[ -z "${XAUTHORITY:-}" ]]; then
    session_auth="$(systemctl --user show-environment | sed -n 's/^XAUTHORITY=//p')"
    if [[ -n "$session_auth" ]]; then export XAUTHORITY="$session_auth"; fi
fi
export XAUTHORITY="$(.venv/bin/python scripts/prepare_linux_session.py)"
mkdir -p logs
exec .venv/bin/python -u app.py --show "$@" >> logs/session.log 2>&1
