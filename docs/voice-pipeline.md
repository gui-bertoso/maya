# Pipeline de voz

## Entrada

1. `sounddevice` captura áudio mono em 16 kHz e blocos de 125 ms.
2. O supressor remove offset DC, estima o ruído ambiente e aplica um noise gate adaptativo.
3. Um pequeno hangover preserva finais de palavras e pausas naturais.
4. A fila limitada descarta o pacote mais antigo quando há atraso, evitando respostas para áudio velho.
5. Vosk produz resultados parciais e finais localmente.
6. O fast endpoint encerra uma frase reconhecida após 375 ms de silêncio configurado.

## Processamento e saída

O callback final apenas valida o wake word e envia o comando ao pipeline assíncrono. A thread do reconhecimento volta a ouvir imediatamente. A resposta segue para o `Speaker`, cuja thread prepara o TTS do Windows no startup e prepara um novo motor após cada fala.

## Configurações principais

- `VOICE_BLOCK_SIZE=2000`
- `VOICE_NOISE_SUPPRESSION=true`
- `VOICE_NOISE_GATE=180`
- `VOICE_NOISE_MULTIPLIER=2.2`
- `VOICE_SPEECH_HANGOVER=4`
- `VOICE_FAST_ENDPOINT=true`
- `VOICE_ENDPOINT_SILENCE_MS=375`
- `VOSK_MODEL_PATH=models/vosk-model-small-pt-0.3`
- `TTS_ENGINE=system`

## Latência

As faixas atuais são estimativas, não telemetria:

- versão original: 1100–2550 ms;
- reconhecimento otimizado: 560–1300 ms;
- com TTS pré-aquecido: 415–780 ms.

O próximo passo correto é registrar timestamps monotônicos em captura, endpoint, processamento, enqueue do TTS e primeiro áudio reproduzido.
