# Maya error codes

Known errors use `MAY-NNNN`. Unclassified errors receive `MAY-0001` so that every
traceback has an identifier.

| Code | Area | Meaning | First action |
|---|---|---|---|
| MAY-0001 | General | Unexpected internal error | Inspect the traceback in the log |
| MAY-0101 | Configuration | Cannot access `.env` | Close duplicate instances and check permissions |
| MAY-0102 | Configuration | Invalid local structure | Restore local files |
| MAY-0103 | Configuration | Invalid value | Correct the indicated field |
| MAY-0201 | Process | Instance lock failed | Stop older instances |
| MAY-0202 | Hotkey | Global shortcut unavailable | Check permissions and `pynput` |
| MAY-0301 | Voice input | Missing audio dependency | Reinstall dependencies |
| MAY-0302 | Voice input | Microphone not found | Select an input device |
| MAY-0303 | Voice input | Vosk model unavailable | Check the model and its path |
| MAY-0304 | Voice input | Recognition failed | Check the microphone and log |
| MAY-0305 | Voice input | Noise suppression failed | Review audio settings |
| MAY-0401 | Speech | TTS engine did not start | Switch or reinstall the engine |
| MAY-0402 | Speech | Voice playback failed | Try a different speech engine |
| MAY-0501 | Interface | Qt did not start | Check PySide6 and DLLs |
| MAY-0502 | Interface | Runtime interface failure | Reopen it and inspect the log |
| MAY-0601 | Input | Command pipeline failed | Repeat the command |
| MAY-0701 | Data | Memory could not be saved | Check the `data` folder |
| MAY-0702 | Data | Routine could not be saved | Check `routine.json` |
| MAY-0801 | Applications | Application did not open | Check its path and permissions |
| MAY-0901 | Web | External service unavailable | Check the connection |
| MAY-1001 | Installation | Installer failed | Inspect the installer log |
| MAY-1002 | Installation | Windows blocked the executable | Use signing or the applicable execution policy |

## New errors

1. Reuse an existing code when the cause and action are the same.
2. Add new codes to `helpers/errors.py` before using them.
3. Log technical context, but show the user a code, summary and recovery action.
4. Never expose only `PermissionError`, `OSError` or an uncoded traceback.

## Reserved ranges

- `0000`: general failures.
- `0100`: configuration.
- `0200`: processes and activation.
- `0300`: voice input.
- `0400`: voice output.
- `0500`: interface.
- `0600`: command processing.
- `0700`: persistence.
- `0800`: local applications.
- `0900`: networking.
- `1000`: installation and updates.
