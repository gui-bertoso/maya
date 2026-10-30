# Voice pipeline

## Input

1. `sounddevice` captures 16 kHz mono audio in 125 ms blocks.
2. The suppressor removes DC offset, estimates ambient noise and applies an adaptive noise gate.
3. A short hangover preserves word endings and natural pauses.
4. A bounded queue drops the oldest packet when delayed, avoiding responses to stale audio.
5. Vosk produces partial and final results locally.
6. Fast endpoint detection ends a recognized phrase after the configured 375 ms of silence.

## Processing and output

The final callback validates the wake word and sends the command to the
asynchronous pipeline. Recognition immediately resumes listening. Responses go
to `Speaker`, whose thread prewarms Windows TTS at startup and prepares a fresh
engine after each utterance.

## Main settings

- `VOICE_BLOCK_SIZE=2000`
- `VOICE_NOISE_SUPPRESSION=true`
- `VOICE_NOISE_GATE=180`
- `VOICE_NOISE_MULTIPLIER=2.2`
- `VOICE_SPEECH_HANGOVER=4`
- `VOICE_FAST_ENDPOINT=true`
- `VOICE_ENDPOINT_SILENCE_MS=375`
- `VOSK_MODEL_PATH=models/vosk-model-small-pt-0.3` for the Portuguese recognition model.
- `TTS_ENGINE=system`

## Latency

These ranges are estimates rather than measured telemetry:

- Original version: 1100–2550 ms.
- Optimized recognition: 560–1300 ms.
- Prewarmed TTS: 415–780 ms.

The next step is to record monotonic timestamps at capture, endpoint detection,
processing, TTS enqueue and the first played audio sample.
