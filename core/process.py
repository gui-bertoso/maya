import re
import random
import vocabulary_manager
from memory import Memory
from helpers.config import get_env

class Assistant:
    def __init__(self):
        self.memory = Memory()

    def process_input(self, text):
        text_lower = text.lower().strip()

        self.memory.add_message("user", text)

        patterns = self.detect_patterns(text_lower)
        self.apply_memory_updates(patterns, text)
        response = self.generate_response(text, patterns)

        self.memory.add_message("assistant", response)
        return response

class Process:
    def __init__(self):
        self.parent = None
        self.weights_amount = 128
        self.memory = None

        self.DEBUG_MODE = get_env("DEBUG_MODE", "false").lower() == "true"
        self.UI_MODE = get_env("UI_MODE", "maya")
        self.LANGUAGE = get_env("LANGUAGE", "en")

    def generate_response(self, text, patterns):
        user_name = self.memory.get_user_name() if self.memory else None

        if patterns["asks_name"]:
            return "i'm maya, your virtual assistant."

        if patterns["asks_memory"]:
            if user_name:
                return f"yes, your name is {user_name}."
            return "i don't know your name yet."

        if patterns["says_name"]:
            return f"nice to meet you, {patterns['user_name']}."

        if patterns["greets"]:
            if user_name:
                return f"hey, {user_name}. good to see you again."
            return "hey there."

        return "i'm still learning, but i'm here with you."

    def apply_memory_updates(self, patterns, original_text):
        if not self.memory:
            return

        if patterns["says_name"]:
            self.memory.set_user_name(patterns["user_name"])

        self.memory.set_last_topic("conversation")

    def handle_input(self, my_input):
        my_input = my_input.strip()

        if not my_input:
            return

        if self.parent is not None:
            self.parent.send_event("input_text", my_input)

        if my_input == "print":
            print(vocabulary_manager.get_text())
            return

        data_array = self.tokenize(my_input)
        particle_types = []

        for data in data_array:
            if vocabulary_manager.has_word(data):
                particle_types.append("vocab")
            else:
                particle_types.append("input")
                vocabulary_manager.write_text(data, self.generate_weights())

        encoded_input = self.encode_text(my_input)

        if self.DEBUG_MODE:
            print(f"encoded[:8] = {encoded_input[:8]}")

        intent = self.detect_intent(data_array)
        patterns = self.detect_patterns(my_input.lower())

        if self.memory:
            self.memory.add_message("user", my_input)

        self.apply_memory_updates(patterns, my_input)

        response = self.generate_response(my_input, patterns)

        if self.memory:
            self.memory.add_message("assistant", response)

        if self.DEBUG_MODE:
            print("intent:", intent)
            print("response:", response)

        if self.parent is not None:
            self.parent.send_event("set_particles", particle_types)
            self.parent.send_event("intent", intent)
            self.parent.send_event("response_text", response)

        return response

    def detect_intent(self, tokens):
        if any(t in tokens for t in ["oi", "ola", "hello", "hey", "hi"]):
            return "greeting"

        if any(t in tokens for t in ["bye", "goodbye", "cya", "later"]):
            return "farewell"

        if "how" in tokens and "you" in tokens:
            return "status_question"

        if "como" in tokens and "voce" in tokens:
            return "status_question"

        return "unknown"

    def generate_weights(self):
        return [random.uniform(-1, 1) for _ in range(self.weights_amount)]

    def encode_text(self, text):
        tokens = self.tokenize(text)

        result = [0.0] * self.weights_amount
        count = 0

        for token in tokens:
            vector = vocabulary_manager.get_word_vector(token)

            if vector is None:
                continue

            for i in range(self.weights_amount):
                result[i] += vector[i]

            count += 1

        if count > 0:
            for i in range(self.weights_amount):
                result[i] /= count

        return result

    def detect_patterns(self, text_lower):
        patterns = {
            "asks_name": False,
            "says_name": False,
            "user_name": None,
            "asks_memory": False,
            "greets": False
        }

        if "who are you" in text_lower or "your name" in text_lower:
            patterns["asks_name"] = True

        if "my name is " in text_lower:
            parts = text_lower.split("my name is ", 1)
            if len(parts) > 1:
                name = parts[1].split(" ")[0].strip(".,!?")
                if name:
                    patterns["says_name"] = True
                    patterns["user_name"] = name

        if "i am " in text_lower:
            parts = text_lower.split("i am ", 1)
            if len(parts) > 1:
                name = parts[1].split(" ")[0].strip(".,!?")
                if name:
                    patterns["says_name"] = True
                    patterns["user_name"] = name

        if any(word in text_lower for word in ["hello", "hi", "hey"]):
            patterns["greets"] = True

        if "do you remember me" in text_lower or "remember my name" in text_lower:
            patterns["asks_memory"] = True

        return patterns

    @staticmethod
    def tokenize(value):
        return re.findall(r"\b[\w']+\b", value.lower())