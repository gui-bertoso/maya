# Native conversation context

Conversation uses `core/dialogue.py` and `data/dialogue_catalog.json`, without a language model, service or additional installation. The catalog contains 32 topics with eight authored interactions each: introduction, rationale, application, caution, challenge, example, reflection and next step.

The catalog currently retains Portuguese conversation phrases. English desktop commands remain available. Examples of exact supported phrases:

- `me fala de bugs` opens the bugs topic.
- `e por que?`, `me dá um exemplo`, `um desafio` continue the active topic.
- `meu jogo se chama Remnants`, `ele usa Godot` store explicit entities.
- `lembra do meu jogo?`, `resume nossa conversa`, `limpa o contexto` retrieve, summarize or clear context.

Statements beginning with `acho que`, `pra mim`, `eu penso que`, `o problema é`, `eu prefiro`, `tenho dificuldade com` or `não consegui` may be saved under the active topic. Retrieved information is attributed to the user. Missing facts are never invented.

## Application references

`open spotify` opens Spotify. After a successful launch, `joga ele pra esquerda` moves that window left. `agora pra direita` reuses the reference for three minutes. `fecha ele` requires a recent reference, which is cleared after a successful close.

Actions still use the original parser. Approximate scoring applies only to conversation. Once a window is identified, its ID accompanies subsequent movement of the same reference to avoid selecting another window by name.

The engine retrieves and combines structured content; it is not a generative model or general language understanding. Entities use explicit formats. Disable `DIALOGUE_ENABLED` in settings to restore the original flow.
