import sys
import types
import unittest

dotenv_stub = types.ModuleType("dotenv")
dotenv_stub.dotenv_values = lambda *args, **kwargs: {}
dotenv_stub.load_dotenv = lambda *args, **kwargs: False
dotenv_stub.set_key = lambda *args, **kwargs: None
sys.modules.setdefault("dotenv", dotenv_stub)

from helpers.config import ENV_FIELD_MAP
from helpers.i18n import is_portuguese, localize_env_field, ui_text


class UiI18nTests(unittest.TestCase):
    def test_portuguese_ui_texts_are_mapped(self):
        self.assertEqual(ui_text("quick_input_placeholder", "pt-BR"), "Fala com a Maya...")
        self.assertEqual(
            ui_text("settings_window_caption", "pt-BR", caption="maya"),
            "maya configuracoes",
        )

    def test_portuguese_env_field_metadata_is_localized(self):
        language_field = ENV_FIELD_MAP["LANGUAGE"]

        localized = localize_env_field(language_field, "pt-BR")

        self.assertEqual(localized["category"], "Geral")
        self.assertEqual(localized["label"], "Idioma")
        self.assertEqual(localized["help_text"], "Codigo de idioma da assistente.")

    def test_is_portuguese_accepts_pt_br_variants(self):
        self.assertTrue(is_portuguese("pt-BR"))
        self.assertTrue(is_portuguese("pt"))
        self.assertFalse(is_portuguese("en"))


if __name__ == "__main__":
    unittest.main()
