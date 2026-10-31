#!/usr/bin/env python3
"""Live model -> ordered worker -> real Qt renderer, without microphone/TTS."""
import json
import os
from pathlib import Path
import queue
import sys
import tempfile
import time
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ['LOCAL_DIALOGUE_ENABLED'] = 'true'
os.environ['DIALOGUE_ENABLED'] = 'true'
os.environ['LANGUAGE'] = 'pt-BR'
os.environ['RESPONSE_BUBBLE_MODE'] = 'always'

from PySide6.QtCore import QTimer
from core.input_pipeline import AsyncInputPipeline
from core.knowledge_base import KnowledgeBase
from core.memory import Memory
from core.process import Process
from helpers.local_dialogue import runtime
from output.renderer import Renderer


def main():
    output = Path(sys.argv[1])
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as directory:
        events = queue.Queue()
        process = Process()
        process.memory = Memory()
        process.knowledge_base = KnowledgeBase(Path(directory) / 'knowledge.json')
        process.parent = SimpleNamespace(send_event=lambda event, value: events.put((event, value)))
        errors = []
        pipeline = AsyncInputPipeline(on_error=lambda error: errors.append(type(error).__name__))
        renderer = Renderer(events, submit_input_callback=lambda text: pipeline.submit(process.handle_input, text))
        window = renderer.settings_window
        window.load_values()
        category = window.category_filter.findData('Jeito de conversar')
        window.category_filter.setCurrentIndex(category)
        window.apply_filter('')
        window.resize(860, 900)
        window.show()
        completed = {'heartbeats': 0}
        started = time.monotonic()
        accepted = pipeline.submit(process.handle_input, 'maya, explica em duas frases por que lembrar o contexto ajuda numa conversa.')
        assert accepted
        pulse = QTimer()

        def check():
            completed['heartbeats'] += 1
            if renderer.response_text:
                completed.update(reply=renderer.response_text, seconds=round(time.monotonic()-started, 3),
                                 engine=process.memory.state.get('dialogue', {}).get('last_engine'))
                window.grab().save(str(output / 'maya-settings-conversa.png'))
                pulse.stop()
                renderer.app.quit()
            elif errors or time.monotonic() - started > 75:
                pulse.stop()
                renderer.app.quit()

        pulse.timeout.connect(check)
        pulse.start(50)
        try:
            renderer.run()
            assert not errors, errors
            assert completed.get('engine') == 'local_model', completed
            assert completed['heartbeats'] > 5, 'Qt did not keep processing events while generation ran'
            assert process.memory.short_term[-1]['content'] == renderer.response_text
            assert 'LOCAL_DIALOGUE_TEMPERATURE' in window.inputs
            assert category >= 0
            completed['passed'] = True
            (output / 'maya-local-interface.json').write_text(json.dumps(completed, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
            print(json.dumps(completed, ensure_ascii=False), flush=True)
        finally:
            pulse.stop()
            renderer.timer.stop()
            renderer.tray_icon.hide()
            for name in ('root', 'quick_input_window', 'response_bubble', 'settings_window',
                         'dev_editor_window', 'window_showcase_window'):
                getattr(renderer, name).hide()
            pipeline.shutdown()
            runtime().close()


if __name__ == '__main__':
    main()
