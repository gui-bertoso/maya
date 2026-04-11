import os
import re
import unicodedata
from helpers.backup_manager import safe_json_dump, safe_json_load
from helpers.config import get_path

MEMORY_PATH = get_path("MEMORY_PATH", "data/memory.json")

class Memory:
    def __init__(self, short_term_limit=10):
        self.short_term_limit = short_term_limit

        self.short_term = []
        self.long_term = {
            "user_name": None,
            "preferences": [],
            "known_facts": []
        }
        self.state = {
            "mood": "neutral",
            "last_topic": None,
            "pending_learning": None
        }

    @staticmethod
    def _normalize_memory_text(value):
        normalized = unicodedata.normalize("NFKD", (value or "").strip().lower())
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        normalized = re.sub(r"\s+", " ", normalized)
        return normalized.strip()

    @classmethod
    def _is_valid_preference(cls, preference):
        normalized = cls._normalize_memory_text(preference)
        if not normalized:
            return False

        tokens = re.findall(r"[a-z0-9']+", normalized)
        if not tokens or len(tokens) > 8:
            return False

        blocked_tokens = {
            "i", "you", "me", "my", "your", "that", "keep", "study", "supplies",
            "pursue", "tell", "easier", "voce", "você", "eu", "que", "mim",
        }
        blocked_hits = sum(1 for token in tokens if token in blocked_tokens)
        if blocked_hits >= 2:
            return False

        if len(tokens) >= 5 and blocked_hits >= 1:
            return False

        return True

    @classmethod
    def _clean_preferences(cls, preferences):
        cleaned = []
        for preference in preferences or []:
            if not cls._is_valid_preference(preference):
                continue
            normalized = cls._normalize_memory_text(preference)
            if normalized not in cleaned:
                cleaned.append(normalized)
        return cleaned

    def add_message(self, role, content):
        if not content:
            return

        self.short_term.append({
            "role": role,
            "content": content.strip()
        })

        if len(self.short_term) > self.short_term_limit:
            self.short_term.pop(0)

    def get_recent_messages(self, amount=5):
        return self.short_term[-amount:]

    def clear_short_term(self):
        self.short_term = []

    def set_user_name(self, name):
        if not name:
            return

        clean_name = name.strip().capitalize()
        self.long_term["user_name"] = clean_name

    def get_user_name(self):
        return self.long_term["user_name"]

    def add_preference(self, preference):
        if not preference or not self._is_valid_preference(preference):
            return

        preference = self._normalize_memory_text(preference)

        if preference not in self.long_term["preferences"]:
            self.long_term["preferences"].append(preference)

    def remove_preference(self, preference):
        if not preference:
            return

        preference = preference.strip().lower()

        if preference in self.long_term["preferences"]:
            self.long_term["preferences"].remove(preference)

    def get_preferences(self):
        return self.long_term["preferences"]

    def add_known_fact(self, fact):
        if not fact:
            return

        fact = fact.strip()

        if fact not in self.long_term["known_facts"]:
            self.long_term["known_facts"].append(fact)

    def remove_known_fact(self, fact):
        if not fact:
            return

        fact = fact.strip()

        if fact in self.long_term["known_facts"]:
            self.long_term["known_facts"].remove(fact)

    def get_known_facts(self):
        return self.long_term["known_facts"]

    def set_mood(self, mood):
        if not mood:
            return

        self.state["mood"] = mood.strip().lower()

    def get_mood(self):
        return self.state["mood"]

    def set_last_topic(self, topic):
        if not topic:
            return

        self.state["last_topic"] = topic.strip().lower()

    def get_last_topic(self):
        return self.state["last_topic"]

    def set_pending_learning(self, question):
        if not question:
            self.state["pending_learning"] = None
            return

        self.state["pending_learning"] = question.strip()

    def get_pending_learning(self):
        return self.state.get("pending_learning")

    def clear_pending_learning(self):
        self.state["pending_learning"] = None

    def save(self, file_path=MEMORY_PATH):
        data = {
            "short_term_limit": self.short_term_limit,
            "short_term": self.short_term,
            "long_term": self.long_term,
            "state": self.state
        }

        safe_json_dump(file_path, data)

    def load(self, file_path=MEMORY_PATH):
        if not os.path.exists(file_path):
            return

        data = safe_json_load(file_path, {})

        self.short_term_limit = data.get("short_term_limit", 10)
        self.short_term = data.get("short_term", [])
        self.long_term = data.get("long_term", {
            "user_name": None,
            "preferences": [],
            "known_facts": []
        })
        self.long_term["preferences"] = self._clean_preferences(self.long_term.get("preferences", []))
        self.state = data.get("state", {
            "mood": "neutral",
            "last_topic": None,
            "pending_learning": None
        })

    def reset_all(self):
        self.short_term = []
        self.long_term = {
            "user_name": None,
            "preferences": [],
            "known_facts": []
        }
        self.state = {
            "mood": "neutral",
            "last_topic": None,
            "pending_learning": None
        }

    def get_context(self):
        return {
            "short_term": self.short_term,
            "long_term": self.long_term,
            "state": self.state
        }
