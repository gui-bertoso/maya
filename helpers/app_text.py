import json

from helpers.config import get_path


APP_TEXT_PATH = get_path("APP_TEXT_PATH", "data/app_text.json")


def load_app_text():
    with open(APP_TEXT_PATH, "r", encoding="utf-8") as file:
        return json.load(file)
