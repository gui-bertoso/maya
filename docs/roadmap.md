# Roadmap

The detailed visual map is available on [Miro](https://miro.com/app/board/uXjVHr5wgpk=/).

## Next priorities

1. Measure latency at each processing stage.
2. Implement robust barge-in that stops a response when the user starts speaking.
3. Improve audio diagnostics and calibration.

## Phases

### 0 — Foundation and stability

Health checks, privacy-aware structured logs, crash recovery, configuration
validation and continued repository organization. Target: 99% error-free startups.

### 1 — Real-time voice

Streaming ASR/TTS, echo cancellation, automatic microphone selection and
benchmarks. Targets: p50 below 500 ms and p95 below 900 ms.

### 2 — Modular processing

Command/plugin registry, confidence-based routing, expiring context, intelligent
fallback and broad intent tests, including Portuguese support.

### 3 — Life OS

Calendar, adaptive planning, pomodoro, quiet hours, weekly dashboard, exports and
controllable proactive suggestions.

### 4 — Experience

Onboarding, tray icon, diagnostics panel, accessibility, themes and visual
voice/microphone controls.

### 5 — Product and distribution

CI, digital signing, clean-machine installation, rollback-capable updates,
release notes, privacy documentation, backup and restoration.

## Cross-cutting quality

Unit and integration tests, audio soak tests, thread/queue limits, permission
handling and no audio recording by default.

## Future research

Custom neural wake words, diarization, optional screen vision, plugin automation,
small local models, cross-device synchronization and a mobile companion.
These are research topics rather than enabled runtime integrations.
