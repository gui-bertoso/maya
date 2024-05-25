from pyttsx3 import Engine

voice_engine = Engine()


def speak(text):
    voice_engine.say(text)
    voice_engine.runAndWait()
