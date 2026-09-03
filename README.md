# Maya

Assistente pessoal local-first para Windows, feita em Python. A Maya escuta comandos em português, automatiza o desktop, acompanha sua rotina e responde por uma interface flutuante ou por voz.

> Projeto funcional e experimental. O foco atual é baixa latência, privacidade local e evolução incremental com testes.

## Destaques

- reconhecimento offline com Vosk e wake words `Maya` / `Maia`;
- supressão adaptativa de ruído e encerramento rápido de fala;
- pipeline assíncrono com filas limitadas e semáforos;
- TTS do Windows pré-aquecido, com Piper e Edge opcionais;
- rotinas A/B, recálculo por atraso, lembretes, XP e streak;
- overlay PySide6, quick input, notificações e configurações;
- memória, vocabulário e respostas persistidos localmente;
- automações para aplicativos, web, Spotify e ambientes de trabalho;
- instalador gráfico e inicialização automática.

## Início rápido no Windows

Pressione **End + Page Down** para mostrar a Maya de qualquer lugar. Se ela já estiver aberta, iniciar o programa novamente apenas traz a janela existente para frente.

Requisitos: Python 3.11, Git e um microfone funcional.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-windows.txt
.\.venv\Scripts\python.exe app.py
```

Com `uv`:

```powershell
uv run --python 3.11 --with-requirements requirements-windows.txt python app.py
```

Para baixar vozes neurais opcionais:

```powershell
.\.venv\Scripts\python.exe scripts\download_piper_models.py --model pt
```

## Comandos de rotina

| Comando | Função |
|---|---|
| `!today` | Mostra o plano de hoje |
| `!done <atividade>` | Conclui uma atividade e concede XP |
| `!skip <atividade>` | Ignora uma atividade |
| `!routine a` / `b` | Alterna entre treino às 06:00 ou 14:00 |
| `!status` | Exibe progresso, XP e streak |
| `!week` | Resume a semana |
| `!awake HH:MM` | Recalcula o dia após acordar atrasado |

## Estrutura

```text
maya/
├── app.py          # composição e ciclo de vida
├── core/           # processamento, memória, rotina e concorrência
├── input/          # microfone, Vosk, ruído e palmas
├── output/         # interface e síntese de voz
├── helpers/        # integrações e utilitários
├── data/           # conteúdo e estado local em JSON
├── models/         # modelos locais de voz
├── scripts/        # execução, downloads e builds
├── tests/          # testes automatizados
└── docs/           # documentação por assunto
```

## Documentação

- [Visão geral em português](docs/overview.pt-BR.md)
- [Overview in English](docs/overview.en.md)
- [Arquitetura](docs/architecture.md)
- [Pipeline de voz](docs/voice-pipeline.md)
- [Rotinas pessoais](docs/routines.md)
- [Desenvolvimento e testes](docs/development.md)
- [Roadmap](docs/roadmap.md)

Mapa visual: [Maya — Arquitetura, Fluxos e Roadmap](https://miro.com/app/board/uXjVHr5wgpk=/)

## Testes

```powershell
uv run --python 3.11 --with-requirements requirements-windows.txt python -m unittest discover -s tests -v
```

## Build

```powershell
.\scripts\build_windows.ps1
.\scripts\build_setup_windows.ps1
```

Artefatos como `setup.exe`, `build/`, `dist/`, logs e caches não pertencem ao Git. Gere-os localmente ou publique-os em uma release.

## Privacidade

O reconhecimento Vosk e os dados pessoais funcionam localmente. Áudio não é gravado por padrão. Motores e integrações online são opcionais e devem ser ativados conscientemente.

## Estado atual

A base já é utilizável, mas ainda precisa de telemetria real de latência, diagnóstico de áudio, barge-in robusto, assinatura do instalador e testes em máquina limpa. Consulte o [roadmap](docs/roadmap.md).
