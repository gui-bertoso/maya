import unittest

from core.process import Process


class ContentExpansionTests(unittest.TestCase):
    def test_alias_catalog_has_at_least_150_new_commands(self):
        process = Process()
        alias_count = sum(len(values) for values in process.command_aliases.values())
        self.assertGreaterEqual(alias_count, 150)

    def test_response_expansions_are_merged(self):
        process = Process()
        self.assertIn("tamo junto. vou contar isso como xp da equipe.", process.responses["thanks_pt"])

    def test_new_natural_phrases_reach_existing_intents(self):
        process = Process()
        cases = (
            ("me tira da procrastinacao", "asks_focus_help"),
            ("manda as manchetes", "asks_news"),
            ("lista seus comandos", "asks_capabilities"),
            ("fica aqui comigo", "asks_lonely"),
            ("tira esse popup", "hide_input_window"),
        )
        for phrase, flag in cases:
            with self.subTest(phrase=phrase):
                self.assertTrue(process.detect_patterns(phrase)[flag])


if __name__ == "__main__":
    unittest.main()
