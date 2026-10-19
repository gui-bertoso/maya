#!/usr/bin/env python3
"""Download the local Kokoro model and voice pack from its official release."""
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent / 'models' / 'kokoro'
BASE = 'https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.1/'

def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    for name in ('kokoro-v1.0.onnx', 'voices-v1.0.bin'):
        destination = ROOT / name
        if destination.exists():
            print(f'Already downloaded: {name}')
            continue
        temporary = destination.with_suffix(destination.suffix + '.partial')
        try:
            with urlopen(BASE + name, timeout=60) as response, temporary.open('wb') as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
            temporary.replace(destination)
        finally:
            temporary.unlink(missing_ok=True)
        print(f'Downloaded: {name}')

if __name__ == '__main__':
    main()
