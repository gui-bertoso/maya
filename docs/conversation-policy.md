# Conversa contextual local

`core/conversation.py` acrescenta uma política determinística ao `DialogueEngine`.
Ela roda depois da proteção dos comandos explícitos e da recuperação de memória,
antes da busca no catálogo. STT, TTS e executores continuam nos fluxos existentes.

- Relatos explícitos de solidão, desânimo, questões existenciais e pedidos de papo
  casual recebem respostas próprias. Não há inferência de diagnóstico.
- “só quero desabafar”, “vamos analisar”, “me motiva” e “muda de assunto” mudam
  a postura. Acolhimento evita transformar cada relato em conselho.
- Generalizações negativas são questionadas sem promessas de sucesso ou concordância
  automática. Perguntas filosóficas mantêm a incerteza.
- A identidade de IA é explícita quando relevante; não se promete exclusividade,
  reciprocidade emocional ou substituição das relações humanas.
- Falas pessoais ficam em `Memory.state['dialogue']['conversation']`, com texto
  original limitado a 600 caracteres, assunto e papel. São no máximo 12 falas.
  Não se tornam fatos permanentes. A serialização existente preserva o contexto;
  “limpa o contexto” apaga também essas falas, mantendo fatos salvos separadamente.
- Resumo e busca de lembranças podem recuperar essas falas com atribuição ao usuário.
- Variações alternam por assunto/modo. Um novo assunto técnico encerra o contexto
  pessoal ativo; três entradas não reconhecidas também expiram a continuidade.
- “to …” em português não deve ser confundido com a forma curta inglesa de mover
  janela; essa forma inglesa agora exige uma direção reconhecida.

Limites: correspondência lexical e respostas escritas à mão não equivalem a
compreensão aberta. Há paráfrases não reconhecidas; variações acabam se repetindo.
A detecção explícita de perigo não é avaliação clínica. O próximo salto de qualidade
exige um gerador local opcional, avaliação por conversas e recuperação de memória
com proveniência e possibilidade de correção, preservando a autoridade do executor.

Validação: testes de diálogo e política, passagem pelo Process sem pesquisa online,
persistência/reabertura, limpeza, troca de assunto, limites de contexto, modos,
comandos explícitos e regressões de interação. Não foi validada a qualidade de uma
conversa falada ao vivo nesta alteração.

## Modelo local opcional

`core/local_conversation.py` seleciona contexto e aplica a identidade fixa;
`helpers/local_dialogue.py` gerencia o processo `llama-server`. O modelo instalado
é Qwen3-8B Q4_K_M, do repositório oficial Qwen, com runtime llama.cpp Vulkan.
O instalador fixa versões e verifica SHA-256 dos dois downloads. Pesos, binários,
manifesto e configuração privada ficam ignorados pelo Git.

O servidor escuta apenas em loopback, em porta escolhida na inicialização, com
chave aleatória por processo. Não segue redirecionamentos nem usa proxies de rede.
O modelo não recebe ferramentas e nenhuma resposta dele volta ao parser como
comando. Aprendizados explícitos e os executores existentes mantêm suas rotas.
O backend carrega por demanda, descansa após o intervalo configurado e é encerrado
junto do processo Python. Mudanças em contexto, camadas GPU, threads ou descanso
reiniciam o backend no próximo pedido. O padrão mantém 8192 tokens de contexto,
cache KV Q8, todas as camadas possíveis na GPU e descanso de 180 segundos.

Histórico recente e lembranças recuperadas possuem orçamentos separados. Até 256
trocas ficam no contexto persistente por padrão, com autor e horário. A recuperação
é lexical, não vetorial: não garante reconhecer toda paráfrase. Nenhuma afirmação
do modelo vira automaticamente um fato do usuário. A troca explícita de assunto
recorta o histórico enviado para evitar carregar vulnerabilidades do papo anterior
para um novo tema. Nomes declarados de entidades selecionadas também podem ser
recuperados pelo motor nativo, com atribuição, sem depender da geração.

Pedidos explícitos de exclusividade emocional ou intenção imediata de se ferir
passam por limites nativos. Um filtro limitado barra alguns relatos claramente
humanos inventados pelo modelo. Isso não prova ausência de outras alucinações.
Se o backend falhar ou produzir uma saída rejeitada, o motor nativo tenta responder;
quando não consegue, informa a indisponibilidade em vez de pesquisar online por
conta própria. O runtime usa um intervalo de 30 segundos antes de tentar novamente.

## Conhecimento das próprias funções

`helpers/self_knowledge.py` lê somente uma lista fixa de fontes Python, por análise
estrutural, sem importar ou executar o código inspecionado. Identifica classes,
funções públicas e linhas. Não lê `.env`, memórias pessoais ou caminhos arbitrários.

- “quais são seus poderes?” mostra funções implementadas e componentes conectados;
- “onde fica seu código de memória?” mostra os símbolos encontrados na fonte;
- “como você funciona?” mostra um mapa dos módulos principais;
- “status do modelo local” mostra o último estado conhecido e o volume de trocas.

O inventário também entra no contexto do modelo. “Conectado” não significa execução
comprovada: disponibilidade de apps, permissões, dispositivos e internet continua
sendo uma condição externa. Não há autoedição, criação espontânea de executores,
consciência subjetiva ou acesso irrestrito aos arquivos.

## Configurações

21 ajustes novos em `helpers/dialogue_settings.py`, além de ativar/desativar o
modelo: criatividade, variedade, limite de resposta, contexto, camadas GPU, threads,
descanso, tempos de espera, histórico recente, recuperação e retenção de trocas,
tamanho, tom, humor, informalidade, perguntas, emojis e intensidade do debate.
As categorias aparecem como “Modelo local — desempenho”, “Memória da conversa” e
“Jeito de conversar”. Números têm limites e controles próprios; opções têm tradução.
As alterações usam a persistência atômica existente. Nome, identidade, apresentação
no feminino, limites relacionais e transparência de IA não são configurações.

Aumentar contexto ou GPU pode exceder a VRAM disponível; a alternativa nativa continua
existindo. Zero no limite episódico apaga esse histórico no próximo pedido elegível.
Isso não apaga fatos pessoais salvos nem o histórico recente, que possuem controles
separados. “limpa o contexto” limpa todas as camadas de contexto de conversa.

## Verificação reproduzível

Teste automatizado: `LOCAL_DIALOGUE_ENABLED=false .venv/bin/python -m unittest
 tests.test_local_conversation tests.test_self_knowledge tests.test_dialogue_settings
 tests.test_conversation_policy tests.test_native_dialogue tests.test_input_pipeline
 tests.test_command_compatibility tests.test_learning_engine
 tests.test_interaction_regressions tests.test_portuguese_and_settings
 tests.test_ui_i18n -q` (em uma única linha).

`python scripts/smoke_local_dialogue.py --report arquivo.json` roda conversas
sintéticas no modelo real, incluindo lembrança após reabertura, troca de assunto,
recuperação de nomes e limites. `python scripts/smoke_local_dialogue_ui.py pasta`
testa geração real no worker e entrega pelo renderer Qt, verifica que a interface
continua processando eventos e salva imagem das configurações. Ambos usam memória
de teste; não gravam diálogos fictícios na memória real. O segundo não ativa STT/TTS.

## Rotas verificáveis e compatibilidade do histórico

O modo debug imprime `[dialogue] route=...` em cada resposta. `local_model` inclui
nome do modelo e tempo medido; `self_inspection`, `native_action`, `native_recall`,
`learned_or_catalog`, `native_parser` e `native_fallback` distinguem as outras rotas.
O marcador é atualizado por pedido, sem reaproveitar o resultado do pedido anterior.
Novas respostas em `Memory.short_term` registram também `source`; memórias antigas
continuam compatíveis.

Perguntas sociais de estado (“how are you”) e pedidos abertos de ajuda não bloqueiam
mais o gerador por flags amplas de `asks_status`/`asks_capabilities`. Pedidos de
capacidades efetivas e versão da aplicação são tratados pela inspeção real.
Templates legados de humor e trocas triviais repetidas de saudação são omitidos do
contexto enviado ao modelo, sem apagar a memória salva. Isso evita ensinar ao LLM
a copiar frases como “I'm doing friendly” de versões anteriores.
