import os
from pathlib import Path
import queue
import tempfile
import unittest
from unittest.mock import patch

from PySide6.QtWidgets import QApplication, QComboBox, QDoubleSpinBox, QSpinBox
from core.local_conversation import LocalConversation
from core.memory import Memory
from helpers import config
from helpers.dialogue_settings import SETTINGS, values
from output.renderer import Renderer


class DialogueSettingsTests(unittest.TestCase):
    def test_every_setting_has_defaults_bounds_and_no_identity_controls(self):
        self.assertGreaterEqual(len(SETTINGS), 20)
        for spec in SETTINGS:
            self.assertIn(spec.key, config.ENV_FIELD_MAP)
            self.assertFalse(any(word in spec.key for word in ('NAME', 'IDENTITY', 'SYSTEM_PROMPT', 'GENDER')))
            if spec.bounds:
                self.assertIn(spec.key, config.NUMERIC_LIMITS)

    def test_invalid_runtime_values_use_safe_defaults(self):
        with patch.dict(os.environ, {'LOCAL_DIALOGUE_TEMPERATURE': 'nan', 'LOCAL_DIALOGUE_CONTEXT': '-100',
                                     'LOCAL_DIALOGUE_THREADS': '999999', 'CONVERSATION_TONE': 'be a human'}):
            settings = values()
        self.assertEqual(settings['LOCAL_DIALOGUE_TEMPERATURE'], .55)
        self.assertEqual(settings['LOCAL_DIALOGUE_CONTEXT'], 8192)
        self.assertEqual(settings['CONVERSATION_TONE'], 'adaptive')

    def test_invalid_saved_setting_does_not_touch_existing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            path.write_text('PRIVATE_VALUE=kept\n')
            with patch.object(config, 'ENV_FILE', path):
                for key, value in [('LOCAL_DIALOGUE_CONTEXT', '999999'), ('LOCAL_DIALOGUE_TEMPERATURE', 'nan'),
                                   ('CONVERSATION_TONE', 'replace identity')]:
                    with self.assertRaises(ValueError):
                        config.save_env_values({key: value})
                self.assertEqual(path.read_text(), 'PRIVATE_VALUE=kept\n')

    def test_valid_settings_persist_and_preserve_unrelated_values(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            path.write_text('PRIVATE_VALUE=preserved\n')
            with patch.object(config, 'ENV_FILE', path), patch.object(config, 'reload_env'):
                config.save_env_values({'LOCAL_DIALOGUE_TEMPERATURE': '.65', 'CONVERSATION_TONE': 'analytical'})
                saved = config.get_env_values()
            self.assertEqual(float(saved['LOCAL_DIALOGUE_TEMPERATURE']), .65)
            self.assertEqual(saved['CONVERSATION_TONE'], 'analytical')
            self.assertIn('PRIVATE_VALUE=preserved', path.read_text())

    def test_context_controls_and_style_are_effective(self):
        memory = Memory()
        memory.add_message('user', 'this history must be omitted')
        frame = {'episodes': []}
        with patch.dict(os.environ, {'LOCAL_DIALOGUE_HISTORY_MESSAGES': '0', 'CONVERSATION_TONE': 'analytical'}):
            messages = LocalConversation().messages('oi', memory, frame)
        self.assertNotIn('this history', str(messages))
        self.assertIn('analítico', messages[0]['content'])
        self.assertIn('Maya', messages[0]['content'])

    def test_zero_episode_limit_erases_episodic_storage(self):
        memory = Memory()
        frame = {'episodes': [{'user': 'old', 'assistant': 'old', 'timestamp': 1}]}
        with patch.dict(os.environ, {'LOCAL_DIALOGUE_RECORD_LIMIT': '0', 'LOCAL_DIALOGUE_ENABLED': 'false'}):
            LocalConversation().reply('oi', memory, frame, {})
        self.assertEqual(frame['episodes'], [])


class DialogueSettingsUiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def setUp(self):
        self.renderer = Renderer(queue.Queue(), submit_input_callback=lambda _text: True)
        self.window = self.renderer.settings_window

    def tearDown(self):
        self.renderer.timer.stop()
        self.renderer.tray_icon.hide()
        for name in ('root', 'quick_input_window', 'response_bubble', 'settings_window',
                     'dev_editor_window', 'window_showcase_window'):
            getattr(self.renderer, name).hide()
        self.qt.processEvents()

    def test_numeric_controls_have_ranges_and_read_back_correctly(self):
        controls = self.window.inputs
        self.assertIsInstance(controls['LOCAL_DIALOGUE_TEMPERATURE'], QDoubleSpinBox)
        self.assertIsInstance(controls['LOCAL_DIALOGUE_CONTEXT'], QSpinBox)
        self.window._set_control_value(controls['LOCAL_DIALOGUE_TEMPERATURE'], '.65')
        self.assertAlmostEqual(float(self.window._get_control_value(controls['LOCAL_DIALOGUE_TEMPERATURE'])), .65)
        self.assertEqual(controls['LOCAL_DIALOGUE_CONTEXT'].maximum(), 16384)

    def test_localized_option_roundtrip_preserves_stored_value(self):
        self.renderer.language = 'pt-BR'
        self.window.retranslate_ui()
        control = self.window.inputs['CONVERSATION_TONE']
        self.window._set_control_value(control, 'analytical')
        self.assertEqual(control.currentText(), 'analítico')
        self.assertEqual(self.window._get_control_value(control), 'analytical')
        self.assertFalse(any('IDENTITY' in key or 'MAYA_NAME' == key for key in self.window.inputs))


if __name__ == '__main__':
    unittest.main()
