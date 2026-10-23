#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
# XWayland supports Maya's floating overlay positioning and keyboard listener.
export QT_QPA_PLATFORM=xcb
unset QT_PLUGIN_PATH QT_QPA_PLATFORM_PLUGIN_PATH QT_STYLE_OVERRIDE QML2_IMPORT_PATH QML_IMPORT_PATH
if [[ -z "${XAUTHORITY:-}" ]]; then
    session_auth="$(systemctl --user show-environment 2>/dev/null | sed -n 's/^XAUTHORITY=//p' || true)"
    if [[ -n "$session_auth" ]]; then export XAUTHORITY="$session_auth"; fi
fi
if [[ -z "${XAUTHORITY:-}" && -f "$HOME/.Xauthority" ]]; then
    export XAUTHORITY="$HOME/.Xauthority"
fi
if [[ -n "${XAUTHORITY:-}" && -f "$XAUTHORITY" && -n "${XDG_RUNTIME_DIR:-}" ]]; then
    export XAUTHORITY="$(.venv/bin/python scripts/prepare_linux_session.py)"
fi
mkdir -p logs
exec .venv/bin/python -u app.py --show "$@" >> logs/session.log 2>&1
