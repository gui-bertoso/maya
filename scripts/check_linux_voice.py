"""Check downloaded recognition and actual offline synthesis without microphone/playback."""
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from helpers.linux_speech import kokoro_espeak_config
from vosk import KaldiRecognizer, Model, SetLogLevel
from kokoro_onnx import Kokoro
import onnxruntime as ort

ROOT = Path(__file__).resolve().parent.parent

def main():
    SetLogLevel(-1)
    model = Model(str(ROOT / 'models/vosk-model-small-en-us-0.15'))
    recognizer = KaldiRecognizer(model, 16000)
    recognizer.AcceptWaveform(bytes(32000))
    recognizer.FinalResult()
    print('reconhecimento offline: modelo carregado.', flush=True)
    options = ort.SessionOptions()
    options.intra_op_num_threads = 4
    options.inter_op_num_threads = 1
    session = ort.InferenceSession(str(ROOT / 'models/kokoro/kokoro-v1.0.onnx'),
                                  sess_options=options, providers=['CPUExecutionProvider'])
    voice = Kokoro.from_session(session, str(ROOT / 'models/kokoro/voices-v1.0.bin'),
                                espeak_config=kokoro_espeak_config())
    audio, rate = voice.create('Maya is ready.', voice='af_heart', lang='en-us')
    if len(audio) < rate // 2:
        raise RuntimeError('a síntese de voz não gerou o áudio esperado.')
    print(f'voz af_heart: {len(audio) / rate:.1f}s de áudio gerado localmente.', flush=True)

if __name__ == '__main__':
    main()
