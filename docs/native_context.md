# Contexto nativo

A conversa usa `core/dialogue.py` e `data/dialogue_catalog.json`, sem modelo de linguagem, serviço ou instalação adicional. O catálogo contém 32 assuntos com oito interações escritas por assunto: introdução, motivo, aplicação, cuidado, desafio, exemplo, reflexão e próximo passo.

Exemplo:

- `me fala de bugs`
- `e por que?`
- `me dá um exemplo`
- `um desafio`

Entidades e lembranças:

- `meu jogo se chama Remnants`
- `ele usa Godot`
- `lembra do meu jogo?`
- `resume nossa conversa`
- `limpa o contexto`

Observações iniciadas com `acho que`, `pra mim`, `eu penso que`, `o problema é`, `eu prefiro`, `tenho dificuldade com` ou `não consegui` podem ser guardadas no contexto do assunto ativo. A recuperação aponta que a informação veio do usuário. Não inventa um fato ausente.

Aplicativos:

- `open spotify` e, após abertura bem-sucedida, `joga ele pra esquerda`.
- `agora pra direita` reaproveita a referência durante três minutos.
- `fecha ele` exige uma referência recente; fechar com sucesso a limpa.

As ações continuam no parser original. A pontuação aproximada é exclusiva da conversa. Quando uma janela já foi identificada, o ID acompanha a próxima movimentação da mesma referência, evitando selecionar outra janela pelo nome.

Limites: o motor recupera e combina conteúdo estruturado; não é compreensão geral ou um modelo generativo. Entidades reconhecidas usam formatos explícitos, como os exemplos acima. O catálogo novo é em português; os comandos originais em inglês continuam disponíveis. Desativar `DIALOGUE_ENABLED` nas settings retorna ao fluxo original.
