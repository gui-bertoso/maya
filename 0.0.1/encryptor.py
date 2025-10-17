import cryptocode

key = "0000000000000000"


def encrypt_file(path, layers=10):
    for layer in range(layers):
        file = open(path, "r")
        text = str(file.read())
        file.close()

        encrypted_text = cryptocode.encrypt(text, key)

        new_file = open(path, "w+")
        new_file.write(encrypted_text)
        new_file.close()


def decrypt_file(path, layers=10):
    for layer in range(layers):
        file = open(path, "r")
        text = file.read()
        file.close()

        decrypted_text = cryptocode.decrypt(text, key)

        new_file = open(path, "w+")
        new_file.write(decrypted_text)
        new_file.close()
