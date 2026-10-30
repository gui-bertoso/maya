# Local whisper.cpp bridge

Selecting `STT_ENGINE=whisper.cpp` in settings uses `WhisperVoice`, preserving the text callback received by `App`. `STT_ENGINE=vosk` restores the previous backend. Kokoro output with `af_heart` is independent of this setting.

```mermaid
flowchart LR
  A[16 kHz microphone] --> B[Noise gate and sentence endpoint]
  B --> C[Bounded queue]
  C --> D[Local whisper-server with resident model]
  D --> E[Final text]
  E --> F[Existing Maya wake word and parser]
```

The server is a Maya child process bound only to `127.0.0.1` on a dynamically selected port. Mono PCM WAV is assembled in memory, sent to `/inference` and discarded after the response. Microphone audio is not saved. Code and model remain local after the initial download. `/health` confirms model readiness before capture is announced as ready. Stopping or switching the backend terminates the process owned by that instance.

Whisper transcribes complete sentences; this integration does not provide partial word-by-word text. Capture continues on its thread while another thread transcribes. At most one sentence waits alongside the current transcription. Segments shorter than two speech blocks are ignored; sentences are limited to 15 seconds. Names in `WHISPER_PROMPT` are vocabulary hints, not accuracy guarantees.

Capture currently uses half-duplex operation: audio is not sent for transcription while Maya speaks. This reduces recognition of its own voice but does not support voice interruption during TTS. Keyboard shortcuts and text input remain available.

## Reference installation

- Official source: `ggml-org/whisper.cpp`, tag `v1.9.5`, under `.runtime/whisper.cpp`.
- Server: `.runtime/whisper.cpp/build/bin/whisper-server`.
- Vulkan backend for the AMD GPU.
- Model: `models/whisper/ggml-small.en.bin`.
- Model SHA-256: `c6138d6d58ecc8322097e0f987c32f1be8bb0a18532a3f88f734d1bbf9c41e5d`.
- Vulkan/SPIR-V headers and glslc from signature-verified Fedora RPMs extracted locally, without system package installation.

This describes the original development machine. Rebuilding elsewhere requires C++, CMake, Ninja, Vulkan Headers, SPIRV-Headers and glslc, or a CPU-only build. Existing local binaries do not require rebuilding to run.

## Settings

`STT_ENGINE`, `WHISPER_CPP_SERVER`, `WHISPER_MODEL_PATH`, `WHISPER_THREADS`, `WHISPER_USE_GPU` and `WHISPER_PROMPT` appear under Voice. Capture must use 16000 Hz. The initial configuration used `small.en`, six threads and Vulkan.

Configure the official repository with `GGML_VULKAN=ON`, supply the local dependency prefix if necessary, and build `whisper-server` and `whisper-cli`. For CPU operation, disable `GGML_VULKAN` and set `WHISPER_USE_GPU=false`.

References: [server protocol](https://github.com/ggml-org/whisper.cpp/tree/v1.9.5/examples/server), [Vulkan support](https://github.com/ggml-org/whisper.cpp#vulkan-gpu-support), [model distribution](https://huggingface.co/ggerganov/whisper.cpp).
