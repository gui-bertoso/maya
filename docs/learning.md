# Ensino e pesquisa nativos

Não usa modelo de linguagem. A pesquisa extrai frases relacionadas ao tema de fontes com endereço registrado. Resultados pesquisados ficam marcados como não verificados pelo usuário e nunca são executados como código ou comandos.

## Ensinar respostas

- `aprenda: onde fica meu projeto? => na pasta Remnants`
- `quando eu disser "quem manda aqui", responda o pato, infelizmente`
- `corrija: onde fica meu projeto? => na pasta Jogos/Remnants`
- `corrige isso: na pasta Jogos/Remnants` corrige o aprendizado consultado ou ensinado mais recentemente.
- `fonte disso` mostra a origem do aprendizado recente.
- `esqueça o aprendizado sobre onde fica meu projeto?` remove esse registro.
- `lista aprendizados` lista perguntas e frases ensinadas.

## Ensinar frases para ações existentes

`quando eu disser "bora ouvir", faça open spotify`

Salvar não executa. Ao dizer `bora ouvir`, o comando passa pelo parser e executor originais. Frases são comparadas de forma normalizada e exata; ações não são escolhidas por semelhança aproximada. A implementação atual aceita um comando por frase e rejeita conflitos com ações nativas. Ações novas que o motor não conhece ainda exigem implementação; ensinar uma explicação não instala uma habilidade executável.

## Pesquisar

- `pesquise e aprenda sobre Python programming language`
- `aprenda sobre Python programming language usando https://www.python.org/about/`

A pesquisa consulta abstracts com fontes e artigos da Wikipedia, valida uma relação lexical mínima, evita páginas de desambiguação e não transforma RelatedTopics em resposta. Também pode extrair conteúdo de uma página HTTPS indicada pelo usuário. Erros de rede ou ausência de evidência retornam uma falha compreensível, sem registrar uma resposta vazia.

Esse critério de relevância é uma heurística, não verificação factual. O resumo é extrativo: seleciona trechos, sem compreensão geral de tutoriais. A fonte fica disponível para conferência e correção pelo usuário.

## Persistência

`KnowledgeBase` preserva as respostas legadas e acrescenta registros com origem, fontes, horário UTC, estado e até dez versões anteriores de uma resposta corrigida. Entradas antigas sem fonte são identificadas como legadas. A escrita usa arquivo temporário e substituição atômica; falhas restauram também o estado anterior na memória. A base original não foi limpa ou descartada na atualização.
