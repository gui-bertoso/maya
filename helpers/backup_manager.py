import json
import shutil
import os
import tempfile
import uuid
from datetime import datetime
from pathlib import Path

from helpers.config import get_env, get_path
from helpers.diagnostics import report_error

BACKUPS_DIR = get_path("BACKUPS_DIR", "data/backups")
MAX_BACKUPS_PER_FILE = get_env("MAX_BACKUPS_PER_FILE", 5, int)


def _ensure_backup_dir():
    BACKUPS_DIR.mkdir(parents=True, exist_ok=True)


def _backup_pattern(source_path):
    return f"{source_path.stem}-*.bak{source_path.suffix}"


def _timestamp():
    return datetime.now().strftime("%Y%m%d-%H%M%S-%f") + "-" + uuid.uuid4().hex[:8]


def create_backup(file_path):
    source_path = Path(file_path)
    if not source_path.exists():
        return None

    _ensure_backup_dir()
    backup_path = BACKUPS_DIR / f"{source_path.stem}-{_timestamp()}.bak{source_path.suffix}"
    try:
        shutil.copy2(source_path, backup_path)
        prune_backups(source_path)
    except OSError as error:
        report_error("backup_failure", error, operation="storage.backup")
        raise
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
    except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeError) as error:
        if source_path.exists():
            report_error("storage_corrupt" if isinstance(error,(ValueError,UnicodeError)) else "memory_storage",
                         error, operation="storage.json.load", context={"component":source_path.stem}, notify=False)
            create_backup(source_path)
        return default


def safe_json_dump(file_path, data):
    source_path = Path(file_path)
    source_path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.maya-json-', dir=source_path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(data, stream, indent=2, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        if source_path.exists():
            create_backup(source_path)
        os.replace(temporary, source_path)
    except Exception as error:
        report_error("memory_storage", error, operation="storage.json.save", context={"component":source_path.stem})
        raise
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
