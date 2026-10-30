# Architecture

## Main flow

```text
Microphone / text / hotkey / claps
                ↓
        Voice + wake detection
                ↓
       AsyncInputPipeline
                ↓
        App → Process → actions
          ↙       ↓       ↘
        data   Renderer   Speaker
```

`app.py` composes services and controls their lifecycle. Domain-specific rules
that can live in smaller modules should not accumulate there.

## Responsibilities

- `core/`: domain rules, intents, memory, routines and asynchronous coordination.
- `input/`: input-signal capture and interpretation.
- `output/`: visual and audio presentation.
- `helpers/`: operating-system and external-service adapters.
- `data/`: editable content and persistent local state.
- `scripts/`: operational tasks outside the application runtime.

## Concurrency

Microphone capture, recognition, command processing, the interface and TTS run
independently. `AsyncInputPipeline` keeps expensive work out of the audio path.
One semaphore serializes state changes and another bounds pending input.

Keep queues bounded. Adding threads without measurement can worsen ordering,
memory use and shutdown behavior rather than improve performance.

## Dependencies

The core uses simple interfaces exposed by `App`. System integrations belong in
`helpers/`; domain code should not import visual components. Substantial new
features should have dedicated modules and tests.
