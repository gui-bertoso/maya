import unittest

from helpers.errors import ERRORS, classify_exception, format_error


class ErrorCatalogTests(unittest.TestCase):
    def test_codes_are_unique_and_well_formed(self):
        codes = [item.code for item in ERRORS.values()]
        self.assertEqual(len(codes), len(set(codes)))
        self.assertTrue(all(code.startswith("MAY-") and len(code) == 8 for code in codes))

    def test_config_permission_is_classified(self):
        error = PermissionError("Permission denied: C:/AppData/maya/.env")
        self.assertEqual(classify_exception(error, "startup config").code, "MAY-0101")

    def test_formatted_error_always_contains_code(self):
        self.assertIn("[MAY-0302]", format_error("microphone_device", "missing"))


if __name__ == "__main__":
    unittest.main()
