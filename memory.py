import json
import os


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
            "last_topic": None
        }

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
        if not preference:
            return

        preference = preference.strip().lower()

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

    def save(self, file_path="memory.json"):
        data = {
            "short_term_limit": self.short_term_limit,
            "short_term": self.short_term,
            "long_term": self.long_term,
            "state": self.state
        }

        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(data, file, indent=4, ensure_ascii=False)

    def load(self, file_path="memory.json"):
        if not os.path.exists(file_path):
            return

        with open(file_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        self.short_term_limit = data.get("short_term_limit", 10)
        self.short_term = data.get("short_term", [])
        self.long_term = data.get("long_term", {
            "user_name": None,
            "preferences": [],
            "known_facts": []
        })
        self.state = data.get("state", {
            "mood": "neutral",
            "last_topic": None
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
            "last_topic": None
        }

    def get_context(self):
        return {
            "short_term": self.short_term,
            "long_term": self.long_term,
            "state": self.state
        }