import zipfile


def compress_file(path):
    with zipfile.ZipFile(path[0:len(path)-4] + ".zip", "w") as compacted_file:
        compacted_file.write(path)


def unzip_file(path):
    with zipfile.ZipFile(path[0:len(path)-4] + ".zip", "r") as compacted_file:
        compacted_file.extractall()
