from helpers import vocabulary
from helpers.backup_manager import safe_json_dump, safe_json_load
from helpers.config import get_path

VOCAB_PATH = get_path("VOCAB_PATH", "data/vocabulary.json")

def get_text():
    return f"{vocabulary.dictionary}"


def has_word(word):
    return word in vocabulary.dictionary


def get_word_vector(word):
    return vocabulary.dictionary.get(word)


def write_text(text, value):
    vocabulary.dictionary[text] = value
    save_vocabulary()


def save_vocabulary():
    safe_json_dump(VOCAB_PATH, vocabulary.dictionary)


def load_vocabulary():
    vocabulary.dictionary = safe_json_load(VOCAB_PATH, {})
