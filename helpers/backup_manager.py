import json
import shutil
from datetime import datetime
from pathlib import Path

from helpers.config import get_env, get_path

BACKUPS_DIR = get_path("BACKUPS_DIR", "data/backups")
MAX_BACKUPS_PER_FILE = get_env("MAX_BACKUPS_PER_FILE", 5, int)


def _ensure_backup_dir():
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)


def _backup_pattern(source_path):
    return f"{source_path.stem}-*.bak{source_path.suffix}"


def _timestamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def create_backup(file_path):
    source_path = Path(file_path)
    if not source_path.exists():
        return None

    _ensure_backup_dir()
    backup_path = BACKUPS_DIR / f"{source_path.stem}-{_timestamp()}.bak{source_path.suffix}"
    shutil.copy2(source_path, backup_path)
    prune_backups(source_path)
    return backup_path


def prune_backups(file_path):
    source_path = Path(file_path)
    backups = sorted(
        BACKUPS_DIR.glob(_backup_pattern(source_path)),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    for stale_backup in backups[MAX_BACKUPS_PER_FILE:]:
        stale_backup.unlink(missing_ok=True)


def safe_json_load(file_path, default):
    source_path = Path(file_path)
    try:
        with open(source_path, "r", encoding="utf-8") as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        if source_path.exists():
            create_backup(source_path)
        return default


def safe_json_dump(file_path, data):
    source_path = Path(file_path)
    source_path.parent.mkdir(parents=True, exist_ok=True)
    if source_path.exists():
        create_backup(source_path)
    with open(source_path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)
