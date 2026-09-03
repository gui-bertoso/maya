### Maya: Assistente Virtual Local-First

A Maya é uma assistente virtual local, funcional e altamente customizável, desenvolvida em Python. Projetada para uso em desktop, a Maya prioriza a privacidade e o funcionamento offline, oferecendo uma interface de overlay fluida para automação do sistema e assistência pessoal via comandos de voz.

---

### 🚀 Principais Funcionalidades

*   **Interação de Voz Offline:** Utiliza `Vosk` para reconhecimento de fala e `Piper` (ou TTS do sistema) para síntese de voz, garantindo que todos os dados de voz permaneçam locais.
*   **Métodos de Ativação Inteligentes:** Ativada por palma dupla (microfone) ou atalho global, eliminando a necessidade de gatilhos em nuvem que "escutam o tempo todo".
*   **Interface de Overlay Flutuante:** Construída com `PySide6`, oferece uma interface não intrusiva e semi-transparente que permanece sobre outras janelas.
*   **Memória e Conhecimento Persistentes:** Armazena preferências do usuário, fatos aprendidos e histórico de conversas em arquivos JSON locais para construir contexto a longo prazo.
*   **Automação de Desktop:**
    *   **Integração com Spotify:** Comandos em linguagem natural para tocar músicas, playlists ou artistas específicos.
    *   **Lançador de Apps e Sites:** Abre rapidamente aplicativos do sistema ou sites específicos.
    *   **Resumo Diário (Daily Brief):** Fornece clima, manchetes e resumo de hora/data ao iniciar ou sob demanda.
*   **Modos Especializados:**
    *   **Modo Reflexivo (Thoughtful Mode):** Um modo de assistência focado em brainstorming ou suporte emocional.
    *   **Modo Dev:** Automatiza a preparação do ambiente de trabalho para desenvolvedores.
*   **Suporte Multi-idioma:** Localização completa para Inglês (EN) e Português (PT-BR).

---

### 🛠️ Stack Técnica

*   **Linguagem:** Python 3.11+
*   **Framework GUI:** PySide6 (Qt para Python)
*   **Reconhecimento de Voz (STT):** Vosk (Modelos de ML offline)
*   **Síntese de Voz (TTS):** Piper (TTS neural baseado em ONNX) e pyttsx3 (fallback do sistema)
*   **Manipulação de Áudio:** `sounddevice` e `PortAudio`
*   **Gerenciamento de Ambiente:** `python-dotenv` para configurações via `.env`
*   **Armazenamento de Dados:** JSON estruturado para memória, base de conhecimento e vocabulário.

---

### 📂 Arquitetura do Projeto

*   `app.py`: Ponto de entrada principal e orquestração do loop de eventos.
*   `core/`: Contém o "cérebro" da Maya (Processamento de Linguagem Natural, Memória, Base de Conhecimento).
*   `input/`: Lida com gravação de áudio, processamento de STT e detecção de palmas.
*   `output/`: Gerencia o renderizador PySide6 e motores de TTS.
*   `helpers/`: Assistentes utilitários para Spotify, Web e integração com o sistema.
*   `data/`: Arquivos de configuração e bancos de dados JSON persistentes.

---

### 🛠️ Primeiros Passos

1.  **Configuração do Ambiente:** Instale Python 3.11+ e o PortAudio.
2.  **Instalação:**
    ```bash
    pip install -r requirements.txt
    python scripts/download_piper_models.py
    ```
3.  **Execução:**
    ```bash
    python app.py
    ```

---

*A Maya é um projeto em andamento, evoluindo constantemente de uma coleção de heurísticas simples para uma assistente local mais robusta.*
