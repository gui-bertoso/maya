#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TARGET_DIR = PROJECT_ROOT / "models" / "piper"
BASE_URL = "https://huggingface.co/rhasspy/piper-voices/resolve/main"
MODELS = {
    "pt": {
        "onnx": "pt/pt_BR/cadu/medium/pt_BR-cadu-medium.onnx",
        "json": "pt/pt_BR/cadu/medium/pt_BR-cadu-medium.onnx.json",
    },
    "en": {
        "onnx": "en/en_US/lessac/high/en_US-lessac-high.onnx",
        "json": "en/en_US/lessac/high/en_US-lessac-high.onnx.json",
    },
}


def download(url: str, destination: Path, force: bool) -> None:
    if destination.exists() and not force:
        print(f"skipping {destination.name}: file already exists")
        return

    destination.parent.mkdir(parents=True, exist_ok=True)
    print(f"downloading {destination.name}...")
    with urllib.request.urlopen(url) as response, destination.open("wb") as output:
        total = response.headers.get("Content-Length")
        remaining = int(total) if total and total.isdigit() else None

        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)
            if remaining is not None:
                remaining -= len(chunk)
                downloaded = int(total) - max(remaining, 0)
                print(f"  {destination.name}: {downloaded // (1024 * 1024)} MB", end="\r", flush=True)

    print(f"downloaded {destination}")


def iter_selected_models(selection: str):
    if selection == "all":
        keys = ("pt", "en")
    else:
        keys = (selection,)

    for key in keys:
        for relative_path in MODELS[key].values():
            yield BASE_URL + "/" + relative_path, TARGET_DIR / Path(relative_path).name


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download Piper voice models used by Maya.")
    parser.add_argument(
        "--model",
        choices=("pt", "en", "all"),
        default="all",
        help="Which voice model to download.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Redownload files even if they already exist locally.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        for url, destination in iter_selected_models(args.model):
            download(url, destination, args.force)
    except Exception as error:
        print(f"failed to download Piper models: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
