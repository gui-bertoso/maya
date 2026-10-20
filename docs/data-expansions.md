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

## Conhecimento consultável

Um `.myde` também pode declarar `knowledge`, sem remover `commands` ou `responses`:

```json
{
  "format": "maya-data-expansion",
  "format_version": 1,
  "name": "exemplo",
  "version": 1,
  "knowledge": [{
    "questions": ["what is a python list", "explain python list"],
    "answer": "Lists hold ordered items and can be changed after creation.",
    "sources": [{"title": "Python data structures", "url": "https://docs.python.org/3/tutorial/datastructures.html"}]
  }]
}
```

As consultas são normalizadas e exatas: isso é recuperação de registros, não geração livre de respostas. Perguntas diferentes precisam de aliases explícitos. Fontes são obrigatórias; texto dos pacotes nunca é executado. `source` ou `fonte disso` mostra as fontes do último registro consultado. Um aprendizado pessoal para a mesma pergunta tem prioridade sobre o pacote; correções não alteram o arquivo distribuído. Remover um pacote remove seu conhecimento após a próxima atualização, sem apagar a memória pessoal.

Cada container é validado integralmente antes de entrar em uso. Um pacote com seção ou fonte inválida é recusado sem publicar seus aliases parcialmente. Perguntas que conflitam com um pacote anterior recusam o pacote posterior, com erro disponível em `expansion_loader.errors`.

Pacotes novos: `DataExpansion4` (Python), `5` (Godot), `6` (Git), `7` (arquivos e caminhos Linux), `8` (computação e web). São 100 registros escritos em inglês e 600 aliases de consulta, com links para documentação primária. Exemplos: `what is python list`, `explain godot signal`, `what is git staging area`, `linux inode`, `what is javascript event loop`.
