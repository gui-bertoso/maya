import unittest
from unittest.mock import MagicMock, patch

from helpers.single_instance import ERROR_ALREADY_EXISTS, SingleInstance


class SingleInstanceTests(unittest.TestCase):
    @patch("helpers.single_instance.sys.platform", "linux")
    def test_non_windows_does_not_block_startup(self):
        self.assertTrue(SingleInstance().acquire())

    @patch("helpers.single_instance.ctypes.get_last_error", return_value=ERROR_ALREADY_EXISTS)
    @patch("helpers.single_instance.ctypes.set_last_error")
    @patch("helpers.single_instance.ctypes.WinDLL")
    @patch("helpers.single_instance.sys.platform", "win32")
    def test_existing_windows_instance_is_rejected(self, win_dll, _set_error, _get_error):
        create_mutex = MagicMock(return_value=123)
        win_dll.return_value.CreateMutexW = create_mutex

        instance = SingleInstance()

        self.assertFalse(instance.acquire())
        self.assertEqual(instance.handle, 123)


if __name__ == "__main__":
    unittest.main()
