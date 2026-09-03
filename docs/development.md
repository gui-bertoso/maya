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
