# Maya errors and diagnostics

`helpers/errors.py` defines permanent codes. `data/error_catalog.json` is the
generated catalog; `docs/error-map.json` inventories static code sites. Rebuild
both with `scripts/audit_errors.py`.

## Three distinct identifiers

- `MAY-NNNN`: a stable runtime failure class; never reuse or renumber it.
- `MAYA-NNN`: a bug-hunter investigation with evidence and correction status; it can relate to multiple codes.
- `event_id`: a recorded occurrence. `correlation_id` links failures from one command, including TTS; `fingerprint` groups the code, operation and exception type.

A possible cause is a hypothesis, not a confirmed diagnosis. Exception type alone
does not establish cause. Successful application launch means a process started
and survived initial observation, not that login, its window or music playback is ready.

## Catalog

| Code | Key | Category | Severity | Retry? | Summary |
|---|---|---|---|---|---|
| MAY-0001 | unexpected | general | error | evaluate | Unexpected internal error |
| MAY-0002 | diagnostics_write | general | warning | evaluate | Diagnostic log unavailable |
| MAY-0101 | config_permission | configuration | error | evaluate | Settings access denied |
| MAY-0102 | config_layout | configuration | error | evaluate | Invalid local data layout |
| MAY-0103 | config_value | configuration | error | evaluate | Invalid setting |
| MAY-0104 | config_write | configuration | error | evaluate | Could not save settings |
| MAY-0105 | config_apply | configuration | error | evaluate | Settings were not fully applied |
| MAY-0201 | single_instance | activation | error | evaluate | Instance lock failed |
| MAY-0202 | hotkey | activation | warning | evaluate | Global shortcut unavailable |
| MAY-0301 | microphone_dependency | speech_input | error | evaluate | Audio dependency unavailable |
| MAY-0302 | microphone_device | speech_input | error | yes | Microphone unavailable |
| MAY-0303 | voice_model | speech_input | error | evaluate | Speech model unavailable |
| MAY-0304 | voice_runtime | speech_input | error | yes | Speech recognition failed |
| MAY-0305 | noise_suppression | speech_input | error | evaluate | Audio noise processing failed |
| MAY-0306 | voice_timeout | speech_input | error | yes | Speech recognition timed out |
| MAY-0307 | voice_server | speech_input | error | yes | Local speech server unavailable |
| MAY-0308 | voice_backpressure | speech_input | warning | yes | Transcription queue full |
| MAY-0401 | tts_init | speech_output | error | evaluate | Speech output could not start |
| MAY-0402 | tts_runtime | speech_output | error | yes | Speech playback failed |
| MAY-0403 | tts_fallback | speech_output | warning | evaluate | Alternative voice engine selected |
| MAY-0501 | ui_init | interface | error | evaluate | Interface could not start |
| MAY-0502 | ui_runtime | interface | error | evaluate | Interface operation failed |
| MAY-0503 | ui_screen | interface | error | evaluate | Monitor unavailable |
| MAY-0504 | ui_position | interface | error | evaluate | Could not position the window |
| MAY-0601 | input_pipeline | commands | error | evaluate | Command processing failed |
| MAY-0602 | input_busy | commands | warning | yes | Command queue full or closed |
| MAY-0603 | parser | commands | error | evaluate | Could not interpret the command |
| MAY-0604 | dev_command | commands | error | evaluate | Development tool failed |
| MAY-0701 | memory_storage | persistence | error | evaluate | Could not save local memory |
| MAY-0702 | routine_storage | persistence | error | evaluate | Routine data unavailable |
| MAY-0703 | knowledge_invalid | persistence | warning | evaluate | Invalid knowledge record |
| MAY-0704 | container_invalid | persistence | warning | evaluate | Invalid data container |
| MAY-0705 | container_reload | persistence | warning | yes | Could not reload data packs |
| MAY-0706 | knowledge_write | persistence | error | evaluate | Could not save knowledge |
| MAY-0707 | storage_corrupt | persistence | warning | evaluate | Unreadable data file |
| MAY-0708 | backup_failure | persistence | error | evaluate | Could not create a backup |
| MAY-0801 | app_launch | applications | error | evaluate | Application could not be opened |
| MAY-0802 | app_missing | applications | error | evaluate | Application not found |
| MAY-0803 | app_exit | applications | error | yes | Application exited during startup |
| MAY-0804 | app_stale_lock | applications | error | evaluate | Stale application lock |
| MAY-0805 | app_target | applications | error | evaluate | Application or window target unavailable |
| MAY-0901 | web_request | network | error | yes | Web service unavailable |
| MAY-0902 | web_timeout | network | error | yes | Web request timed out |
| MAY-0903 | web_payload | network | error | evaluate | Invalid web response |
| MAY-1001 | installer | installation | error | evaluate | Installer failed |
| MAY-1002 | app_control | installation | error | evaluate | Windows blocked the executable |

## Local events and interface

Commands, settings, voice, TTS, persistence, containers, application launch and
window operations use `report_error` at their boundaries. Text errors include a
code, summary and recovery action; TTS failures do not attempt to speak their own
error. Warnings/fallbacks do not automatically open popups. Repeated events remain
logged, but identical visual warnings are limited to one every three seconds.

`logs/errors.jsonl` follows `docs/schemas/error-event.schema.json`. Each file is
limited to approximately 1 MiB with three rotations, at most four files; one record
may exceed the size limit. Unix creation permissions are 0600. Logging failure
does not interrupt the original operation: it increments a counter and emits a
short `MAY-0002` notice without dumping the event content.

Events contain the exception type, errno/return code when present and source
file/line. They exclude raw exception messages, full tracebacks, local variables,
audio, transcripts, questions and `.env` values. Context uses an allowlist of
metadata; never use user text as an operation name. Older session logs, native
logs and stdout/stderr may contain legacy messages and are excluded from the
structured exporter.

## Map and limitations

The original inventory examined 45 first-party Python files: 178 handlers, 141
failure returns, 64 propagation points, 20 legacy assignments and 70 explicit
standard-report calls. Regenerate the map for current counts and lines. Site IDs
are static fingerprints of file, function, kind and relative position.

Scope covers root files plus `core`, `input`, `output`, `helpers` and `scripts`.
Each site includes location, function, kind, suggested code and classification.
Suggested codes require semantic review. Fallback/probe labels describe boundary
policies rather than proving instrumentation or harmless failures. This is not
runtime coverage measurement.

Seven bootstrap handlers remain highlighted: importing new dependencies there
without clean-machine validation can break installation. Native Qt/ALSA/Whisper,
external processes and the operating system are outside the Python AST scan.
Fatal native failures or abrupt termination can prevent a final event. ASR
accuracy, visual desynchronization and false success confirmations remain
behavioral problems rather than automatically diagnosable exceptions.

## Add or change an error

1. Reuse a definition only when its meaning and recovery action match. Define new codes before use.
2. Provide English and optional Portuguese text, category, severity, retryability and possible causes.
3. Record at the boundary that knows the result. Do not mark a fallback as final failure or `False` as success.
4. Preserve existing contracts; never trigger destructive recovery from an error code.
5. Pass a constant operation and allowed context only, without recognized text, passwords, tokens, query URLs or personal data.
6. Test a controlled failure and run the audit to verify codes and syntax.

## Refresh and export

```bash
.venv/bin/python scripts/audit_errors.py
.venv/bin/python scripts/export_diagnostics.py --output /path/to/diagnostics.json
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v
```

The exporter includes only recent structured events and the catalog. It does not
read `.env`, memory, audio or raw logs; messages/actions are reconstructed from
the registry. Static maps and bug-hunter evidence may be shared separately.
