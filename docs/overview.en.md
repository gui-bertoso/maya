### Maya: Local-First Virtual Assistant

Maya is a functional, experimental, and highly customizable local virtual assistant built with Python. Designed for desktop use, Maya prioritizes privacy and offline functionality, providing a seamless overlay interface for voice-controlled system automation and personal assistance.

---

### 🚀 Key Features

*   **Offline Voice Interaction:** Uses `Vosk` for speech recognition and `Piper` (or system TTS) for speech synthesis, ensuring all voice data remains local.
*   **Intelligent Wake Methods:** Activated by a double clap (microphone) or a global hotkey, eliminating the need for constant "Always-Listening" cloud triggers.
*   **Floating Overlay UI:** Built with `PySide6`, providing a non-intrusive, semi-transparent interface that stays on top of other windows.
*   **Persistent Memory & Knowledge:** Stores user preferences, learned facts, and conversation history in local JSON files to build long-term context.
*   **Desktop Automation:**
    *   **Spotify Integration:** Natural language commands to play music, playlists, or specific artists.
    *   **App & Web Launcher:** Quickly open system applications or specific websites.
    *   **Daily Brief:** Provides weather, headlines, and time/date summaries on startup or request.
*   **Specialized Modes:**
    *   **Thoughtful Mode:** A reflective assistant mode designed to help with brainstorming or emotional support.
    *   **Dev Mode:** Automates workspace setup for developers, focusing on productivity.
*   **Multi-language Support:** Full localization for English (EN) and Portuguese (PT-BR).

---

### 🛠️ Technical Stack

*   **Language:** Python 3.11+
*   **GUI Framework:** PySide6 (Qt for Python)
*   **Speech-to-Text (STT):** Vosk (Offline ML models)
*   **Text-to-Speech (TTS):** Piper (ONNX-based neural TTS) & pyttsx3 (System fallback)
*   **Audio Handling:** `sounddevice` and `PortAudio`
*   **Environment Management:** `python-dotenv` for `.env` configurations
*   **Data Storage:** Structured JSON for memory, knowledge base, and vocabulary.

---

### 📂 Project Architecture

*   `app.py`: Main entry point and event loop orchestration.
*   `core/`: Contains the "brain" of Maya (Natural Language Processing, Memory management, Knowledge Base).
*   `input/`: Handles voice recording, STT processing, and clap detection.
*   `output/`: Manages the PySide6 renderer and TTS engines.
*   `helpers/`: Utility assistants for Spotify, Web, and system integration.
*   `data/`: Configuration files and persistent JSON databases.

---

### 🛠️ Getting Started

1.  **Environment Setup:** Install Python 3.11+ and PortAudio.
2.  **Installation:**
    ```bash
    pip install -r requirements.txt
    python scripts/download_piper_models.py
    ```
3.  **Run:**
    ```bash
    python app.py
    ```

---

*Maya is an ongoing project, constantly evolving from a collection of simple heuristics to a more robust local assistant.*
