# Data Expansions

Os containers `data/expansions/DataExpansionN.myde` ampliam a Maya sem alterar o processador principal. `.myde` significa **Maya Data Expansion**: é um arquivo UTF-8 com JSON por dentro, então continua fácil de ler e editar.

```json
{
  "format": "maya-data-expansion",
  "format_version": 1,
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
- Todo `.myde` precisa declarar `format` e `format_version`; versões desconhecidas são recusadas com segurança.
- Containers `.json` antigos continuam aceitos para compatibilidade, mas novos pacotes devem usar `.myde`.
- Comandos e respostas repetidos são removidos durante a união.
- Um container inválido é ignorado sem derrubar os demais.
- Mudanças são detectadas durante o uso, no máximo um segundo depois de salvar o arquivo.
- Não é necessário editar `core/process.py` para adicionar conteúdo a uma intenção existente.

O nome da intenção precisa existir no dicionário `patterns` do processador. Novas funcionalidades ainda exigem código; novas maneiras de falar e responder, não.
