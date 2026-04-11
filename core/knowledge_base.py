import os
import re

from helpers.backup_manager import safe_json_dump, safe_json_load
from helpers.config import get_path

KNOWLEDGE_PATH = get_path("KNOWLEDGE_PATH", "data/learned_knowledge.json")


class KnowledgeBase:
    def __init__(self, file_path=KNOWLEDGE_PATH):
        self.file_path = file_path
        self.data = {"answers": {}}
        self.load()

    @staticmethod
    def normalize_question(text):
        normalized = text.strip().lower()
        normalized = re.sub(r"\s+", " ", normalized)
        normalized = normalized.strip(" .!?")
        return normalized

    def load(self):
        if not os.path.exists(self.file_path):
            return

        self.data = safe_json_load(self.file_path, {"answers": {}})
        self.data.setdefault("answers", {})

    def save(self):
        safe_json_dump(self.file_path, self.data)

    def get_answer(self, question):
        normalized = self.normalize_question(question)
        return self.data.get("answers", {}).get(normalized)

    def teach_answer(self, question, answer):
        normalized = self.normalize_question(question)
        if not normalized or not answer.strip():
            return

        self.data.setdefault("answers", {})[normalized] = answer.strip()
        self.save()
