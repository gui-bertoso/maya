import pyaudio
import vosk
import random
import settings
import data_management
import synthesizer
import log
import results_bank
import pygame


class Main:
    def __init__(self):
        data_management.read_data()

        pygame.display.set_caption("mayaProject")
        self.window = pygame.display.set_mode((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT))
        self.clock = pygame.time.Clock()
        self.running = True

        self.recognition_model = vosk.Model(settings.RECOGNITION_MODEL_PATH)
        self.recognizer = vosk.KaldiRecognizer(self.recognition_model, 8000)

        self.cap = pyaudio.PyAudio()
        self.stream = self.cap.open(format=pyaudio.paInt16, channels=1, rate=8000, input=True, frames_per_buffer=8192)

        self.loop()

    def verify_result(self, text):
        for result in results_bank.results_dictionary:
            if result == text:
                results_list = results_bank.results_dictionary[result]
                final_result = random.choice(results_list)
                synthesizer.speak(final_result)

    def loop(self):
        while self.running:
            self.clock.tick(settings.SCREEN_FRAME_RATE)
            self.window.fill(settings.THEME_COLOR0)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False

            self.draw_interface()
            self.recognize()

            pygame.display.flip()

    def draw_interface(self):
        pygame.draw.circle(
            self.window,
            settings.THEME_COLOR3,
            (
                settings.SCREEN_WIDTH / 2 + random.randint(-4, 4),
                settings.SCREEN_HEIGHT / 2 + random.randint(-4, 4)),
            (80 * (
                settings.INTERFACE_SCALE / 100)),
            8
        )
        pygame.draw.circle(
            self.window,
            settings.THEME_COLOR2,
            (
                settings.SCREEN_WIDTH / 2 + random.randint(-2, 2),
                settings.SCREEN_HEIGHT / 2 + random.randint(-2, 2)
            ),
            (80 * (settings.INTERFACE_SCALE / 100)),
            8
        )
        pygame.draw.circle(
            self.window,
            settings.THEME_COLOR1,
            (settings.SCREEN_WIDTH / 2, settings.SCREEN_HEIGHT / 2),
            (80 * (settings.INTERFACE_SCALE / 100)),
            8
        )

    def recognize(self):
        data = self.stream.read(4096*2)
        if self.recognizer.AcceptWaveform(data):
            result_text = self.recognizer.FinalResult()
            result_size = len(str(result_text))

            final_result = str(result_text)[14:result_size - 3]

            print(final_result)
            log.create_log(f"VOICE INPUT: {final_result}")
            self.verify_result(final_result)


if __name__ == "__main__":
    Main()
