import os
import random
import encryptor
import settings


def read_data():
    if os.path.exists(settings.ENCRYPT_KEY_PATH):
        file = open(settings.ENCRYPT_KEY_PATH, "r")
        key = file.read()
        file.close()

        encryptor.key = str(key)
        print(encryptor.key)
    else:
        encryption_key = random.randint(0, 99999999999999999999999999999999999999999999999999999)

        new_file = open(settings.ENCRYPT_KEY_PATH, "w+")
        new_file.write(str(encryption_key))
        new_file.close()


def pack_data():
    pass