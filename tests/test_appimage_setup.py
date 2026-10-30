import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from scripts import appimage_launcher as launcher


class AppImageSetupTests(unittest.TestCase):
    def bundle(self, folder):
        bundle = folder / 'mounted-appimage/usr'
        (bundle / 'python/bin').mkdir(parents=True)
        (bundle / 'python/bin/python3').write_text('runtime fixture')
        (bundle / 'setup.py').write_text('installer fixture')
        (bundle / 'bundle.json').write_text(json.dumps({'bundle_id': 'a' * 64}))
        return bundle

    def test_runtime_survives_appimage_unmount(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bundle = self.bundle(root)
            target = launcher.prepare_runtime(bundle, root / 'data')
            shutil.rmtree(root / 'mounted-appimage')
            self.assertEqual((target / 'python/bin/python3').read_text(), 'runtime fixture')
            self.assertEqual((target / 'setup.py').read_text(), 'installer fixture')
            self.assertFalse((target / 'python/bin/python3').is_symlink())

    def test_second_launch_reuses_persistent_runtime(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bundle = self.bundle(root)
            target = launcher.prepare_runtime(bundle, root / 'data')
            with patch.object(launcher.shutil, 'copytree') as copy:
                self.assertEqual(launcher.prepare_runtime(bundle, root / 'data'), target)
            copy.assert_not_called()

    def test_invalid_identity_cannot_escape_runtime_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bundle = self.bundle(root)
            (bundle / 'bundle.json').write_text(json.dumps({'bundle_id': '../../escape'}))
            with self.assertRaisesRegex(RuntimeError, 'identifier'):
                launcher.prepare_runtime(bundle, root / 'data')
            self.assertFalse((root / 'data').exists())

    def test_incomplete_persistent_runtime_is_not_used(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            bundle = self.bundle(root)
            target = launcher.prepare_runtime(bundle, root / 'data')
            (target / 'python/bin/python3').unlink()
            with self.assertRaisesRegex(RuntimeError, 'incomplete'):
                launcher.prepare_runtime(bundle, root / 'data')


if __name__ == '__main__':
    unittest.main()
