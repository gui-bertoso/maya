import os
from dotenv import load_dotenv

load_dotenv()

def get_env(key, default=None, cast=str):
    value = os.getenv(key, default)

    if value is None:
        return None

    try:
        return cast(value)
    except Exception:
        return default