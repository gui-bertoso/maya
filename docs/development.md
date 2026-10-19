# Desenvolvimento

## Ambiente recomendado

- Python 3.11
- Windows 10/11
- `requirements-windows.txt`
- modelos Vosk armazenados em `models/`

## Testar

```powershell
uv run --python 3.11 --with-requirements requirements-windows.txt python -m unittest discover -s tests -v
```

Testes de SQLite, quando adicionados, devem rodar serialmente para evitar bloqueio de banco no Windows.

## Regras de organização

- Código de domínio em `core/`; I/O em `input/` e `output/`.
- Integrações opcionais em `helpers/`.
- Um módulo novo deve ter teste correspondente em `tests/`.
- Estado, cache, log e binários gerados não entram no Git.
- Não versionar `.env`, dados pessoais ou áudio capturado.
- Alterações de configuração precisam aparecer na UI e na documentação quando forem relevantes ao usuário.

## Build Windows

```powershell
.\scripts\build_windows.ps1
.\scripts\build_setup_windows.ps1
```

O executável do instalador deve ser publicado como artefato de release, acompanhado de versão, hash e, futuramente, assinatura digital. Não deve ser commitado no repositório.

## Checklist de mudança

1. Preserve compatibilidade dos arquivos JSON ou forneça migração.
2. Execute testes relacionados e a suíte completa.
3. Valide inicialização, escuta e ao menos uma resposta falada.
4. Revise `git diff --check` e não inclua dados locais.
5. Faça commit pequeno e push após a alteração validada.

## Instalação local no Fedora

Use `scripts/start_maya.sh` para abrir o ambiente `.venv` e a interface de texto.
O inicializador usa XWayland para posicionar o overlay; o atalho Delete + Page Up
funciona nas janelas XWayland. Aplicativos Wayland nativos podem não repassar
essa combinação. A chamada por voz continua disponível.

A opção `app.py --show` abre a interface de texto ao iniciar. A configuração
local `.env` seleciona português, Vosk em português e síntese offline pelo Piper.

## Voz feminina offline

O motor `kokoro` usa o modelo local em `models/kokoro`. Instale os requisitos e
execute `python scripts/download_kokoro_models.py` uma vez. Configure
`TTS_ENGINE=kokoro`, `LANGUAGE=pt-BR` e `TTS_VOICE_ID=pf_dora` nas configurações.
A Dora é uma voz feminina em português brasileiro. Depois do download, a síntese
funciona sem rede, usando CPU. A voz sai no tom original, sem alterar o pitch.
O campo de velocidade continua usando `TTS_RATE`, com 180 como velocidade normal.
