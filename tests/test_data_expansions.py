import json
import tempfile
import unittest
from pathlib import Path

from helpers.data_expansions import DataExpansionLoader, FORMAT_NAME, FORMAT_VERSION


def myde_payload(**content):
    return {
        "format": FORMAT_NAME,
        "format_version": FORMAT_VERSION,
        **content,
    }


class DataExpansionLoaderTests(unittest.TestCase):
    def test_numbered_containers_merge_in_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "DataExpansion10.myde").write_text(json.dumps(myde_payload(commands={"thanks": ["dez"]})), encoding="utf-8")
            (root / "DataExpansion2.myde").write_text(json.dumps(myde_payload(commands={"thanks": ["dois"]})), encoding="utf-8")
            loader = DataExpansionLoader(root, refresh_interval=0)

            self.assertTrue(loader.refresh(force=True))
            self.assertEqual(loader.loaded_files, ["DataExpansion2.myde", "DataExpansion10.myde"])
            self.assertEqual(loader.command_aliases["thanks"], ["dois", "dez"])

    def test_changed_container_hot_reloads(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "DataExpansion0.myde"
            path.write_text(json.dumps(myde_payload(commands={"thanks": ["primeiro"]})), encoding="utf-8")
            loader = DataExpansionLoader(directory, refresh_interval=0)
            loader.refresh(force=True)
            path.write_text(json.dumps(myde_payload(commands={"thanks": ["segundo"]})), encoding="utf-8")

            self.assertTrue(loader.refresh())
            self.assertEqual(loader.command_aliases["thanks"], ["segundo"])

    def test_broken_container_does_not_break_other_containers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "DataExpansion0.myde").write_text("{broken", encoding="utf-8")
            (root / "DataExpansion1.myde").write_text(json.dumps(myde_payload(responses={"thanks": ["ok"]})), encoding="utf-8")
            loader = DataExpansionLoader(root, refresh_interval=0)

            loader.refresh(force=True)

            self.assertEqual(loader.responses["thanks"], ["ok"])
            self.assertEqual(len(loader.errors), 1)

    def test_legacy_json_container_is_still_supported(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "DataExpansion0.json"
            path.write_text(json.dumps({"commands": {"thanks": ["legado"]}}), encoding="utf-8")
            loader = DataExpansionLoader(directory, refresh_interval=0)

            loader.refresh(force=True)

            self.assertEqual(loader.command_aliases["thanks"], ["legado"])

    def test_invalid_myde_header_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "DataExpansion0.myde"
            path.write_text(json.dumps({"format": "qualquer-coisa", "format_version": 1}), encoding="utf-8")
            loader = DataExpansionLoader(directory, refresh_interval=0)

            loader.refresh(force=True)

            self.assertEqual(loader.loaded_files, [])
            self.assertEqual(len(loader.errors), 1)


if __name__ == "__main__":
    unittest.main()
