"""Use matching Linux eSpeak library/data rather than wheel build-machine paths."""
import ctypes.util
from pathlib import Path
import sys


def kokoro_espeak_config():
    if not sys.platform.startswith('linux'):
        return None
    from kokoro_onnx.config import EspeakConfig
    library = ctypes.util.find_library('espeak-ng')
    for folder in ('/usr/share/espeak-ng-data', '/usr/local/share/espeak-ng-data',
                   '/usr/lib/espeak-ng-data', '/usr/lib64/espeak-ng-data'):
        if library and (Path(folder) / 'phontab').is_file():
            return EspeakConfig(lib_path=library, data_path=folder)
    raise RuntimeError('instale espeak-ng e seus arquivos de voz pelo gerenciador de pacotes do Linux.')
