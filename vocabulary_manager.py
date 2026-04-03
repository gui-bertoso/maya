def get_text():
    return "{" + open("vocabulary_manager.txt", "r").read() + "}"

def write_text(text0, text1):
    with open("vocabulary_manager.txt", "w") as f:
        f.writelines(tex)