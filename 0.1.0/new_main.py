import pygame
import threading
import pyttsx3
import vosk
from new_settings import *
import new_log


class App:
    def __init__(self) -> None:
        #Initializing base packages
        new_log.create_log("Initializing packages")
        pygame.init()
        pygame.mixer.init()
        pyttsx3.init()

        #Initializing voice engine
        new_log.create_log("Initializing voice engine")
        self.voice_engine = pyttsx3.Engine()
        self.voice_engine.setProperty("rate", VOICE_ENGINE_RATE)
        self.voice_engine.setProperty("volume", VOICE_ENGINE_VOLUME)

        new_log.create_log("Setting variables")
        self.voice_thread = None
        self.recognition_thread = None
        self.render_thread = None

        self.window = None

        self.stop_event = threading.Event()

        self.init_window()

        new_log.create_log("Running base")
        self.init_subthreads()
        self.process_function()

    def init_window(self):
        self.window = pygame.display.set_mode(
            (SCREEN_WIDTH, SCREEN_HEIGHT),
            pygame.NOFRAME
        )
        pygame.display.set_caption("mayaProject")


    def init_subthreads(self) -> None:
        #init subthreads for functions
        new_log.create_log("Settings subthread references")
        self.voice_thread = threading.Thread(target=self.speak_function)
        self.recognition_thread = threading.Thread(target=self.recognition_function)
        self.render_thread = threading.Thread(target=self.render_function)

        new_log.create_log("Starting render subthread")
        self.render_thread.start()
        new_log.create_log("Starting voice subthread")
        self.voice_thread.start()
        new_log.create_log("Starting recognition subthread")
        self.recognition_thread.start()

        new_log.create_log("All subthread ready")

    def catch_events(self):
        try:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    if not self.stop_event.is_set():
                        self.stop_event.set()
                        pygame.quit()
                if event.type == pygame.MOUSEBUTTONUP:
                    if event.button == 1:
                        if self.is_on_button(((SCREEN_WIDTH / 2)-10, (SCREEN_HEIGHT / 2)-10), (20, 20)):
                            if not self.stop_event.is_set():
                                self.stop_event.set()
                                pygame.quit()
        except Exception as error:
            new_log.create_log("ERROR: " + str(error))

    def process_function(self) -> None:
        while not self.stop_event.is_set():
            self.catch_events()

    def render_function(self) -> None:
        while not self.stop_event.is_set():
            pygame.draw.rect(self.window, (255, 0, 0), ((SCREEN_WIDTH / 2), (SCREEN_HEIGHT / 2), 20, 20))
            pygame.display.flip()
        try:
            if self.render_thread.is_alive():
                self.render_thread.join()
        except Exception as error:
            new_log.create_log("ERROR: render_function - " + str(error))

    def speak_function(self) -> None:
        while not self.stop_event.is_set():
            self.catch_events()
        try:
            if self.voice_thread.is_alive():
                self.voice_thread.join()
        except Exception as error:
            new_log.create_log("ERROR: speak_function - " + str(error))

    def recognition_function(self) -> None:
        while not self.stop_event.is_set():
            self.catch_events()
        try:
            if self.recognition_thread.is_alive():
                self.recognition_thread.join()
        except Exception as error:
            new_log.create_log("ERROR: recognition_function - " + str(error))

    def is_on_button(self, position: tuple, size: tuple) -> bool:
        mouse_position = pygame.mouse.get_pos()
        if position[0] + size[0] < mouse_position[0] > position[0] and position[1] + size[1] < mouse_position[1] > position[1]:
            return True
        else:
            return False


if __name__ == "__main__":
    new_log.create_log("Starting application")
    app = App()