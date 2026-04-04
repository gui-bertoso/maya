import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

def get_env(key, default=None, cast=str):
    value = os.getenv(key, default)

    if value is None:
        return None

    try:
        return cast(value)
    except Exception:
        return default
def get_path(key, default):
    relative = get_env(key, default)
    return BASE_DIR / relative