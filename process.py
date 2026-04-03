import re
import random
import vocabulary_manager
from responses import RESPONSES


class Process:
    def __init__(self):
        self.parent = None
        self.weights_amount = 128

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
        print(f"encoded[:8] = {encoded_input[:8]}")

        intent = self.detect_intent(data_array)
        response = self.get_response(intent, my_input, data_array)

        print("intent:", intent)
        print("response:", response)

        if self.parent is not None:
            self.parent.send_event("set_particles", particle_types)
            self.parent.send_event("intent", intent)
            self.parent.send_event("response_text", response)

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

    def get_response(self, intent, text, tokens):
        patterns = self.detect_patterns(text, tokens)

        response_parts = []

        if intent == "greeting":
            response_parts.append(random.choice(RESPONSES["greeting"]))

        if patterns["says_name"] and patterns["user_name"]:
            response_parts.append(f"nice to meet you, {patterns['user_name']}")

        if patterns["asks_name"]:
            response_parts.append("my name is maya")

        if intent == "status_question":
            response_parts.append(random.choice(RESPONSES["status_question"]))

        if not response_parts:
            response_parts.append(random.choice(RESPONSES["unknown"]))

        return ", ".join(response_parts)

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

    def detect_patterns(self, text, tokens):
        text_lower = text.lower()

        patterns = {
            "asks_name": False,
            "says_name": False,
            "user_name": None,
        }

        if "what's your name" in text_lower or "what is your name" in text_lower:
            patterns["asks_name"] = True

        if "your name" in text_lower:
            patterns["asks_name"] = True

        if "who are you" in text_lower:
            patterns["asks_name"] = True

        if "my name is " in text_lower:
            parts = text_lower.split("my name is ", 1)
            if len(parts) > 1:
                name_part = parts[1].strip()
                name = name_part.split(" ")[0].strip(".,!?")
                if name:
                    patterns["says_name"] = True
                    patterns["user_name"] = name

        if "i am " in text_lower:
            parts = text_lower.split("i am ", 1)
            if len(parts) > 1:
                name_part = parts[1].strip()
                name = name_part.split(" ")[0].strip(".,!?")
                if name:
                    patterns["says_name"] = True
                    patterns["user_name"] = name

        return patterns

    @staticmethod
    def tokenize(value):
        return re.findall(r"\b[\w']+\b", value.lower())