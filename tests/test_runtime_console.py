import unittest

from helpers.runtime_console import RuntimeConsole, should_enable_runtime_console


class RuntimeConsoleTests(unittest.TestCase):
    def test_console_is_enabled_only_when_debug_mode_is_true(self):
        self.assertTrue(should_enable_runtime_console(lambda key, default=None: "true"))
        self.assertFalse(should_enable_runtime_console(lambda key, default=None: "false"))
        self.assertFalse(should_enable_runtime_console(lambda key, default=None: ""))

    def test_detach_is_noop_when_console_was_never_attached(self):
        console = RuntimeConsole()
        self.assertFalse(console.detach())


if __name__ == "__main__":
    unittest.main()
