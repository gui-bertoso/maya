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

        self.stop_event = threading.Event()

        new_log.create_log("Running base")
        self.init_subthreads()

        self.process_function()

    def init_subthreads(self) -> None:
        #init subthreads for functions
        new_log.create_log("Initializing subthreads")
        self.voice_thread = threading.Thread(target=self.speak_function)
        self.recognition_thread = threading.Thread(target=self.recognition_function)
        self.render_thread = threading.Thread(target=self.render_function)

    def process_function(self) -> None:
        while not self.stop_event.is_set():
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.stop_event.set()
                    pygame.quit()

    def render_function(self) -> None:
        while not self.stop_event.is_set():
            pass

    def speak_function(self) -> None:
        while not self.stop_event.is_set():
            pass

    def recognition_function(self) -> None:
        while not self.stop_event.is_set():
            pass


if __name__ == "__main__":
    new_log.create_log("Starting application")
    app = App()