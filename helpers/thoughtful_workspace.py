import time

from helpers.app_launcher import AppLauncher
from helpers.spotify_assistant import SpotifyAssistant
from helpers.web_assistant import WebAssistant


class ThoughtfulWorkspaceOrchestrator:
    def __init__(self):
        self.app_launcher = AppLauncher()
        self.spotify_assistant = SpotifyAssistant()
        self.web_assistant = WebAssistant()

    def run(self):
        firefox_key = self.app_launcher.resolve_alias("firefox")
        instagram_url = "https://www.instagram.com/"
        chatgpt_url = "https://chatgpt.com/"

        if firefox_key:
            self.app_launcher.launch_with_target(firefox_key, instagram_url)
            time.sleep(0.5)
            self.app_launcher.launch_with_target(firefox_key, chatgpt_url)
        else:
            self.web_assistant.open_url(instagram_url)
            time.sleep(0.5)
            self.web_assistant.open_url(chatgpt_url)

        self.spotify_assistant.open_app(self.app_launcher)
