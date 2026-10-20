# update e bug hunter

O catálogo auditável está em `update-bug-hunter.json`. Ele registra somente o que foi encontrado nesta revisão: bugs confirmados, correções verificadas, limitações de plataforma e hipóteses que ainda precisam de reprodução. Não representa uma garantia de ausência de outros bugs.

O perfil `data/profiles/responsive-en.json` foi criado para manter inglês e `af_heart`. A captura passa de blocos de 125 para 100 ms e o silêncio configurado para finalizar fala passa de 375 para 300 ms. Isso reduz o atraso configurado; não equivale a uma medição completa de latência de ponta a ponta. A janela de interação aumenta para 12 s, rascunhos permanecem protegidos e as respostas em texto ficam visíveis em qualquer forma de chamada. Velocidade Kokoro: 190 em vez de 180.

As alterações de settings passam primeiro pela validação de todas as opções, depois são escritas em um arquivo temporário e publicadas atomicamente. Um erro de validação ou escrita deixa o `.env` anterior intacto. O snapshot anterior ao perfil fica somente em `work/`, com acesso privado; ele nunca deve ser versionado.

O conhecimento dos cinco novos containers é local e consultável por aliases exatos. Uma pergunta pessoal ensinada tem prioridade; comandos explícitos mantêm sua rota normal. Consultas explicativas que mencionam palavras como `open`, `run` ou `search` não autorizam ações.

A suíte completa pode ser executada com `QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v` no Linux. Testes que exigem APIs nativas de Windows são pulados nessa plataforma; isso não substitui validação em Windows.
