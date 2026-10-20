import errno
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import Mock,patch

from helpers.diagnostics import ErrorReporter,error_scope,safe_context,CORRELATION_ID
from helpers.errors import ERRORS,classify_exception,user_message
from scripts.audit_errors import build_inventory,build_catalog
from scripts.export_diagnostics import export_report


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.reporter=ErrorReporter(self.root/'errors.jsonl')
    def tearDown(self):self.reporter.close();self.temp.cleanup()
    def events(self):return [json.loads(line) for line in self.reporter.path.read_text().splitlines()]

    def test_event_has_stable_contract_and_no_exception_message(self):
        with error_scope('a'*32):
            event=self.reporter.report('input_pipeline',ValueError('private question password=not-public'),operation='command.process')
        self.assertEqual(event['code'],'MAY-0601')
        self.assertEqual(event['correlation_id'],'a'*32)
        self.assertEqual(event['exception'],{'type':'ValueError'})
        self.assertNotIn('private question',json.dumps(self.events()))
        schema=json.loads((Path(__file__).parents[1]/'docs/schemas/error-event.schema.json').read_text())
        self.assertEqual(set(schema['required']),set(event))
        self.assertEqual(set(schema['properties']),set(event))
        self.assertEqual(set(schema['properties']['code']['enum']),{value.code for value in ERRORS.values()})

    def test_exception_source_has_location_but_no_input_or_locals(self):
        try:raise OSError(errno.ENOSPC,'sensitive content')
        except OSError as error:event=self.reporter.report('memory_storage',error,operation='memory.save')
        self.assertEqual(event['exception']['errno'],errno.ENOSPC)
        self.assertEqual(event['exception']['source']['file'],'test_diagnostics.py')
        self.assertNotIn('sensitive',self.reporter.path.read_text())

    def test_context_whitelist_and_redaction(self):
        event=self.reporter.report('voice_runtime',context={'engine':'token=secretvalue','transcript':'private speech','env':{'key':'password'}})
        self.assertEqual(event['context'],{'engine':'[redacted]'})
        self.assertEqual(safe_context({'timeout_seconds':float('nan')}),{})

    def test_file_rotation_is_bounded(self):
        self.reporter.close();self.reporter=ErrorReporter(self.root/'errors.jsonl',max_bytes=1200,backups=2)
        for _ in range(20):self.reporter.report('input_busy',notify=False)
        files=list(self.root.glob('errors.jsonl*'))
        self.assertLessEqual(len(files),3)
        self.assertTrue(all(file.stat().st_size<=1800 for file in files))

    @unittest.skipUnless(os.name=='posix','Unix file permissions')
    def test_error_file_is_private(self):
        self.reporter.report('unexpected')
        self.assertEqual(self.reporter.path.stat().st_mode&0o777,0o600)

    def test_log_failure_does_not_break_original_operation(self):
        self.reporter.path=self.root/'occupied'/'errors.jsonl'
        (self.root/'occupied').write_text('not a directory')
        event=self.reporter.report('input_pipeline',RuntimeError('private payload'))
        self.assertEqual(event['code'],'MAY-0601')
        self.assertEqual(self.reporter.write_failures,1)
        self.assertEqual(self.reporter.last_write_failure['code'],'MAY-0002')

    def test_repeated_errors_are_logged_but_notifications_throttled(self):
        sink=Mock();self.reporter.sink=sink
        for _ in range(3):self.reporter.report('input_pipeline',operation='same.operation')
        self.assertEqual(len(self.events()),3);sink.assert_called_once()

    def test_warning_does_not_open_error_popup(self):
        sink=Mock();self.reporter.sink=sink
        self.reporter.report('input_busy');sink.assert_not_called()

    def test_broken_ui_sink_is_isolated(self):
        self.reporter.sink=Mock(side_effect=RuntimeError('UI gone'))
        event=self.reporter.report('unexpected');self.assertEqual(event['code'],'MAY-0001')

    def test_threads_write_valid_independent_events(self):
        threads=[threading.Thread(target=lambda:self.reporter.report('input_busy')) for _ in range(20)]
        for thread in threads:thread.start()
        for thread in threads:thread.join(2)
        events=self.events();self.assertEqual(len(events),20)
        self.assertEqual(len({event['event_id'] for event in events}),20)

    def test_nested_scopes_restore_correlation(self):
        self.assertIsNone(CORRELATION_ID.get())
        with error_scope('a'*32):
            with error_scope('b'*32):self.assertEqual(CORRELATION_ID.get(),'b'*32)
            self.assertEqual(CORRELATION_ID.get(),'a'*32)
        self.assertIsNone(CORRELATION_ID.get())

    def test_export_excludes_raw_logs_and_rebuilds_messages(self):
        event=self.reporter.report('unexpected')
        self.reporter.close()
        event['message']='password=do-not-export';event['exception']={'type':'ValueError','message':'private'}
        self.reporter.path.write_text(json.dumps(event)+'\n{broken\n')
        (self.root/'session.log').write_text('private transcript')
        (self.root/'.env').write_text('API_KEY=private')
        result=export_report(self.reporter.path,self.root/'report.json')
        text=(self.root/'report.json').read_text()
        self.assertNotIn('do-not-export',text);self.assertNotIn('private transcript',text)
        self.assertNotIn('API_KEY',text);self.assertEqual(result['malformed_event_lines'],1)

    def test_every_definition_has_metadata_and_both_languages(self):
        for key,value in ERRORS.items():
            with self.subTest(key=key):
                self.assertTrue(value.category and value.title_en and value.action_en and value.possible_causes)
                self.assertIn(value.code,user_message(key,'en'))
                self.assertIn(value.code,user_message(key,'pt-BR'))

    def test_inventory_scans_all_first_party_files_and_has_no_unknown_codes(self):
        inventory=build_inventory()
        self.assertFalse(inventory['parse_errors']);self.assertFalse(inventory['unknown_literal_codes'])
        self.assertGreater(inventory['files_scanned'],40)
        self.assertTrue(any(site['classification']=='installer_bootstrap_review' for site in inventory['sites']))
        self.assertEqual(len(build_catalog()['definitions']),len(ERRORS))

    def test_classifier_preserves_area_and_timeout(self):
        self.assertEqual(classify_exception(TimeoutError(),'voice.whisper').code,'MAY-0306')
        self.assertEqual(classify_exception(FileNotFoundError(),'app.launch').code,'MAY-0802')
        self.assertEqual(classify_exception(ValueError(),'config.save').code,'MAY-0103')
        self.assertEqual(classify_exception(RuntimeError(),'renderer.update').code,'MAY-0502')

    def test_launcher_reports_early_exit_with_numeric_code(self):
        from helpers.app_launcher import AppLauncher,ApplicationStartupError
        launcher=AppLauncher.__new__(AppLauncher)
        launcher.apps={'spotify':{'command':'spotify'}}
        launcher.get_platform_value=lambda config,key:config[key]
        launcher._installed_desktop_command=lambda config:None
        launcher._resolve_platform_command=lambda config:['spotify']
        launcher._spawn=Mock(side_effect=ApplicationStartupError(1))
        with patch('helpers.app_launcher.report_error') as report:
            self.assertEqual(launcher.launch('spotify'),(False,'launch_failed'))
        self.assertEqual(report.call_args.args[0],'app_exit')
        self.assertEqual(report.call_args.args[1].returncode,1)

    def test_command_failures_share_correlation_with_nested_operation(self):
        from core.input_pipeline import AsyncInputPipeline
        done=threading.Event()
        def work():
            self.reporter.report('voice_timeout',operation='nested.voice')
            raise RuntimeError('do not store user input')
        def failure(error):
            self.reporter.report('input_pipeline',error,operation='command.process');done.set()
        pipeline=AsyncInputPipeline(on_error=failure)
        pipeline.submit(work)
        self.assertTrue(done.wait(2));pipeline._executor.shutdown(wait=True)
        events=self.events()
        self.assertEqual(len(events),2)
        self.assertEqual(events[0]['correlation_id'],events[1]['correlation_id'])

    def test_speech_queue_preserves_command_correlation(self):
        import queue
        from output.speaker import Speaker
        speaker=Speaker.__new__(Speaker);speaker.queue=queue.Queue()
        speaker.muted=False;speaker.is_running=True;speaker.engine_preference='kokoro';speaker._prepared_engine=None
        speaker._speak_with_kokoro=Mock(side_effect=RuntimeError('private phrase'))
        with error_scope('c'*32):speaker.speak('never log my spoken text')
        speaker.queue.put(None)
        with patch('output.speaker.report_error',side_effect=lambda key,error,**kwargs:self.reporter.report(key,error,**kwargs)):
            speaker._run()
        event=self.events()[0]
        self.assertEqual(event['correlation_id'],'c'*32)
        self.assertEqual(event['code'],'MAY-0402')
        self.assertNotIn('never log',self.reporter.path.read_text())

    def test_unknown_key_has_fallback_code(self):
        event=self.reporter.report('not_registered')
        self.assertEqual(event['code'],'MAY-0001')
        self.assertEqual(event['key'],'unexpected')


if __name__=='__main__':unittest.main()
