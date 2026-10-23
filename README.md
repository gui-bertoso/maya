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

## Instalação visual no Linux

Para instalar sem preparar Python, baixe **Maya-Setup-x86_64.AppImage** nas [releases](https://github.com/gui-bertoso/maya/releases). Nas propriedades do arquivo, permita executá-lo como programa e abra com dois cliques. O pacote inclui Python e a interface do setup; a Maya e os modelos são baixados durante a instalação. Disponível para Linux x86_64.

O setup guarda seu runtime em `~/.local/share/maya/setup-runtimes/` (ou `$XDG_DATA_HOME/maya/setup-runtimes/`). Assim, o ambiente instalado continua funcionando quando o AppImage é fechado, movido ou apagado. Para verificar o pacote em um desktop, execute-o com `--self-test`: o teste abre a interface e verifica um ambiente Python novo, os headers e os certificados HTTPS.

Para gerar o pacote a partir do código, use Python 3.12 ou mais novo: `python3 scripts/build_setup_appimage.py`. O build baixa versões fixas do Python standalone e das ferramentas AppImage, verifica SHA256 e grava o AppImage, seu checksum e o manifesto em `dist/`. Não inclui modelos de voz nem dados pessoais.

Alternativamente, use o bootstrap pequeno:

Baixe `setup.sh` da branch `IA_Improvementes` e execute:

```bash
bash setup.sh
```

A janela permite escolher a branch do GitHub, baixar a voz offline e abrir a Maya ao terminar. O arquivo inicial é pequeno: código, dependências, Python compatível (se necessário) e modelos são baixados durante a instalação. O repositório precisa estar público para instalação e atualização sem autenticação.

No Fedora e Ubuntu/Debian/Mint, o setup prepara os componentes do sistema automaticamente, incluindo a interface do instalador, as bibliotecas de áudio e o XWayland. Quando necessário, o Linux abre sua janela de autorização: informe a senha ali e a instalação continua, sem comandos adicionais. É necessário um desktop com polkit/pkexec e um agente gráfico de autenticação ativo. Se você cancelar a autorização, basta iniciar a instalação novamente.

Somente o gerenciador de pacotes recebe privilégios de administrador; o instalador, o ambiente Python e a Maya continuam como seu usuário. Pacotes já instalados não são reinstalados. No Linux, o atalho usa `python-xlib` diretamente via X11/XWayland: `pynput` e `evdev` não são dependências da instalação, e o setup não exige compilador nem headers para o atalho. Em Wayland, o alcance do atalho depende dos aplicativos conectados ao XWayland; a abertura pelo menu de aplicativos continua disponível. Em outras distribuições, os componentes do sistema precisam estar disponíveis previamente.

A instalação usa `~/.local/share/maya/versions/`, cria um atalho no menu e o comando `~/.local/bin/maya`. Em Wayland, é necessário XWayland. O reconhecimento inicial é Vosk em inglês, com voz Kokoro `af_heart`; nenhum modelo de conversação é baixado ou ativado.

Para atualizar, rode `setup.sh` novamente, use **Atualizar Maya…** no menu da bandeja ou envie `update maya`, `atualizar maya` ou `!update`. O instalador lembra a branch. Feche a Maya pela bandeja **antes de clicar em instalar**: a versão nova recebe uma cópia das configurações e dos dados pessoais, reaproveita os modelos e mantém a pasta anterior. A troca do atalho ocorre somente depois de preparar a instalação. Se uma branch antiga não tiver o backend Linux, o instalador informa isso.

Executar `bash setup.sh --local-source` instala a cópia local, sem baixar o código do GitHub (voltado a desenvolvimento). Instalações existentes mantêm suas opções de voz.

## Início rápido no Windows

Pressione **Delete + Page Up** para mostrar a Maya de qualquer lugar. Se ela já estiver aberta, iniciar o programa novamente apenas traz a janela existente para frente.

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
- [Códigos de erro](docs/error-codes.md)
- [Comandos e exemplos](docs/commands.md)
- [Containers DataExpansion](docs/data-expansions.md)
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
