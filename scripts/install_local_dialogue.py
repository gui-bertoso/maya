#!/usr/bin/env python3
"""Install pinned official llama.cpp Vulkan binaries + Qwen weights locally.

No system packages, sudo, telemetry, or automatic model downloads at app startup.
Run explicitly after reviewing the download (~5 GB).
"""
import hashlib
import json
import os
from pathlib import Path
import sys
import tarfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
RELEASE = 'b11748'
REVISION = '7c41481f57cb95916b40956ab2f0b139b296d974'
ASSET = f'llama-{RELEASE}-bin-ubuntu-vulkan-x64.tar.gz'
BINARY_SHA = '0c0e4eb9d3984374afee11ee9b1aa5720cf0d68d5533f49883a9d0e9c085463f'
MODEL_SHA = 'd98cdcbd03e17ce47681435b5150e34c1417f50b5c0019dd560e4882c5745785'
MODEL_NAME = 'Qwen3-8B-Q4_K_M.gguf'


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def download(url, target, expected):
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.is_file() and digest(target) == expected:
        print(f'verified: {target.name}', flush=True)
        return
    partial = target.with_suffix(target.suffix + '.part')
    offset = partial.stat().st_size if partial.exists() else 0
    request = urllib.request.Request(url, headers={'Range': f'bytes={offset}-'} if offset else {})
    with urllib.request.urlopen(request, timeout=60) as response:
        resume = response.status == 206 and offset > 0
        if not resume:
            offset = 0
        total = offset + int(response.headers.get('Content-Length', '0'))
        last = time.monotonic()
        with partial.open('ab' if resume else 'wb') as stream:
            while chunk := response.read(4 * 1024 * 1024):
                stream.write(chunk)
                offset += len(chunk)
                if time.monotonic() - last > 15:
                    print(f'{target.name}: {offset / 1e9:.2f}/{total / 1e9:.2f} GB', flush=True)
                    last = time.monotonic()
    if digest(partial) != expected:
        raise ValueError(f'Checksum mismatch: {partial.name}. Remove the partial file before retrying.')
    partial.replace(target)
    print(f'downloaded and verified: {target.name}', flush=True)


def main():
    if not sys.platform.startswith('linux') or os.uname().machine != 'x86_64':
        raise SystemExit('This pinned installer currently targets Linux x86_64 with Vulkan.')
    runtime = ROOT / '.runtime' / 'local-dialogue'
    model = ROOT / 'models' / 'dialogue' / MODEL_NAME
    runtime.mkdir(parents=True, exist_ok=True)
    archive = runtime / ASSET
    download(f'https://github.com/ggml-org/llama.cpp/releases/download/{RELEASE}/{ASSET}', archive, BINARY_SHA)
    extracted = runtime / RELEASE
    if not extracted.exists():
        staging = runtime / (RELEASE + '.extracting')
        staging.mkdir(exist_ok=True)
        with tarfile.open(archive) as bundle:
            bundle.extractall(staging, filter='data')
        staging.replace(extracted)
    candidates = list(extracted.rglob('llama-server'))
    if len(candidates) != 1:
        raise RuntimeError('Expected exactly one llama-server in the pinned release')
    download(f'https://huggingface.co/Qwen/Qwen3-8B-GGUF/resolve/{REVISION}/{MODEL_NAME}', model, MODEL_SHA)
    manifest = dict(schema=1, release=RELEASE, binary=str(candidates[0].relative_to(ROOT)),
                    model=str(model.relative_to(ROOT)), model_revision=REVISION,
                    binary_sha256=BINARY_SHA, model_sha256=MODEL_SHA,
                    model_license='Apache-2.0', backend='Vulkan', context_size=8192)
    temporary = runtime / 'install.json.tmp'
    temporary.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    temporary.replace(runtime / 'install.json')
    print('Local dialogue installed. Enable LOCAL_DIALOGUE_ENABLED only after the smoke test.', flush=True)


if __name__ == '__main__':
    main()
