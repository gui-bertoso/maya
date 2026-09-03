# Data Expansions

Os containers `data/expansions/DataExpansionN.json` ampliam a Maya sem alterar o processador principal.

```json
{
  "name": "nome-do-pacote",
  "version": 1,
  "commands": {
    "asks_joke": ["nova forma de pedir uma piada"]
  },
  "responses": {
    "asks_joke_pt": ["nova resposta"]
  }
}
```

## Funcionamento

- Os arquivos são descobertos automaticamente e carregados pela ordem numérica: `0`, `1`, `2`…
- Comandos e respostas repetidos são removidos durante a união.
- Um container inválido é ignorado sem derrubar os demais.
- Mudanças são detectadas durante o uso, no máximo um segundo depois de salvar o arquivo.
- Não é necessário editar `core/process.py` para adicionar conteúdo a uma intenção existente.

O nome da intenção precisa existir no dicionário `patterns` do processador. Novas funcionalidades ainda exigem código; novas maneiras de falar e responder, não.
