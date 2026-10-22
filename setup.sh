#!/usr/bin/env bash
set -euo pipefail
for candidate in python3.11 python3.12 python3; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys, tkinter, venv; assert sys.version_info[:2] >= (3, 10)' 2>/dev/null; then
        installer_python="$candidate"
        break
    fi
done
if [[ -z "${installer_python:-}" ]]; then
    printf '%s\n' 'a maya precisa de Python 3.10 ou mais novo, com tkinter e venv.' 'ubuntu/debian: sudo apt install python3 python3-venv python3-tk' 'fedora: sudo dnf install python3 python3-tkinter' >&2
    exit 1
fi
installer_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ "${1:-}" == '--local-source' ]]; then
    shift
    exec "$installer_python" "$installer_root/setup.py" --local-source "$@"
fi
installer_temp="$(mktemp -d -t maya-setup-XXXXXXXX)"
trap 'rm -rf -- "$installer_temp"' EXIT
"$installer_python" - "$installer_temp" <<'PY'
import json, os, sys
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import quote
ref = 'IA_Improvementes'
base = 'https://api.github.com/repos/gui-bertoso/maya'
def fetch(url):
    with urlopen(Request(url, headers={'User-Agent': 'Maya-Linux-Setup'}), timeout=30) as response:
        return response.read(2 * 1024 * 1024)
try:
    revision = json.loads(fetch(base + '/commits/' + quote(ref, safe='')))['sha']
    payload = fetch(f'https://raw.githubusercontent.com/gui-bertoso/maya/{revision}/setup.py')
    Path(sys.argv[1], 'setup.py').write_bytes(payload)
    try:
        Path(sys.argv[1], 'icon.png').write_bytes(fetch(f'https://raw.githubusercontent.com/gui-bertoso/maya/{revision}/icon.png'))
    except Exception:
        pass
except Exception as error:
    message = 'não foi possível baixar o instalador do github. confira a internet e se o repositório está público.\n' + str(error)
    try:
        import tkinter as tk
        from tkinter import messagebox
        root = tk.Tk(); root.withdraw()
        messagebox.showerror('maya · instalação', message, parent=root)
        root.destroy()
    except Exception:
        pass
    raise SystemExit(message)
PY
"$installer_python" "$installer_temp/setup.py" --linux-bootstrap "$@"
