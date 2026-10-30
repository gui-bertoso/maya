# Native teaching and research

This feature uses no language model. Research extracts topic-related sentences from attributed sources. Research results are marked as unverified by the user and are never executed as code or commands.

## Teach responses

The native learning grammar currently supports these Portuguese aliases (quoted exactly for compatibility):

- `aprenda: onde fica meu projeto? => na pasta Remnants` teaches a response.
- `quando eu disser "quem manda aqui", responda o pato, infelizmente` teaches a phrase.
- `corrija: onde fica meu projeto? => na pasta Jogos/Remnants` corrects an answer.
- `corrige isso: na pasta Jogos/Remnants` corrects the most recently consulted or taught entry.
- `fonte disso` shows the recent entry's source.
- `esqueça o aprendizado sobre onde fica meu projeto?` removes the entry.
- `lista aprendizados` lists taught questions and phrases.

## Teach phrases for existing actions

`quando eu disser "bora ouvir", faça open spotify`

Saving a phrase does not execute it. Saying `bora ouvir` later routes the command through the original parser and executor. Matching is normalized and exact; approximate similarity never selects actions. Each phrase supports one command, and conflicts with native actions are rejected. New actions still require implementation. Teaching an explanation does not install an executable skill.

## Research

- `pesquise e aprenda sobre Python programming language`
- `aprenda sobre Python programming language usando https://www.python.org/about/`

Research consults attributed abstracts and Wikipedia articles, checks a minimum lexical relationship, avoids disambiguation pages and does not turn RelatedTopics into an answer. It can also extract text from a user-specified HTTPS page. Network errors or missing evidence return a readable failure without saving an empty answer.

Relevance is heuristic, not fact checking. The summary selects source excerpts; it does not understand arbitrary tutorials. Sources remain available for user review and correction.

## Persistence

`KnowledgeBase` preserves legacy answers and adds records containing provenance, sources, UTC timestamps, state and up to ten previous versions of corrected answers. Entries without sources are identified as legacy. Writes use a temporary file and atomic replacement; failure also restores the prior in-memory state. Updates do not clear the original knowledge base.
