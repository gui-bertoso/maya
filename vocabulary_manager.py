import json
import vocabulary


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
    with open("vocabulary.json", "w", encoding="utf-8") as file:
        json.dump(vocabulary.dictionary, file, ensure_ascii=False, indent=2)


def load_vocabulary():
    try:
        with open("vocabulary.json", "r", encoding="utf-8") as file:
            loaded_vocabulary = json.load(file)
        vocabulary.dictionary = loaded_vocabulary
    except FileNotFoundError:
        vocabulary.dictionary = {}