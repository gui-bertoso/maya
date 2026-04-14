import unittest

from helpers.version import APP_VERSION, get_short_revision, get_version_display


class VersionTests(unittest.TestCase):
    def test_version_display_includes_short_revision_when_available(self):
        self.assertEqual(
            get_version_display(version="1.1.0", revision="09afc4d123456789"),
            "v1.1.0 (09afc4d)",
        )

    def test_version_display_falls_back_to_version_only(self):
        self.assertEqual(get_version_display(version="1.1.0", revision=""), "v1.1.0")

    def test_short_revision_handles_empty_values(self):
        self.assertIsNone(get_short_revision(""))
        self.assertEqual(get_short_revision("abcdef1234"), "abcdef1")

    def test_app_version_uses_semver_shape(self):
        parts = APP_VERSION.split(".")
        self.assertEqual(len(parts), 3)
        self.assertTrue(all(part.isdigit() for part in parts))


if __name__ == "__main__":
    unittest.main()
