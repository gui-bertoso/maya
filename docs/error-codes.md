# erros e diagnósticos da maya

`helpers/errors.py` é a fonte dos códigos permanentes. `data/error_catalog.json` é o catálogo gerado; `docs/error-map.json` é o inventário estático dos pontos no código. Ambos são reconstruídos por `scripts/audit_errors.py`.

## três identificadores diferentes

- `MAY-NNNN`: classe estável de falha em execução. Não reutilizar nem renumerar.
- `MAYA-NNN`: ocorrência investigada no bug hunter, com evidência e status de correção. Pode se relacionar com vários códigos.
- `event_id`: uma ocorrência registrada. `correlation_id` liga falhas do mesmo comando, incluindo a fila de TTS; `fingerprint` agrupa código, operação e tipo de exceção.

Causa possível é hipótese, não diagnóstico confirmado. O tipo de exceção sozinho não determina a causa. Uma chamada de app bem-sucedida significa que o processo foi iniciado e não encerrou durante a observação inicial; não prova login, janela pronta ou reprodução de música.

## catálogo

| código | chave | categoria | gravidade | repetir? | resumo |
|---|---|---|---|---|---|
| MAY-0001 | unexpected | general | error | avaliar | Erro interno inesperado |
| MAY-0002 | diagnostics_write | general | warning | avaliar | Registro de diagnóstico indisponível |
| MAY-0101 | config_permission | configuration | error | avaliar | Sem acesso à configuração |
| MAY-0102 | config_layout | configuration | error | avaliar | Estrutura de dados inválida |
| MAY-0103 | config_value | configuration | error | avaliar | Configuração inválida |
| MAY-0104 | config_write | configuration | error | avaliar | Falha ao salvar configuração |
| MAY-0105 | config_apply | configuration | error | avaliar | Configuração não aplicada completamente |
| MAY-0201 | single_instance | activation | error | avaliar | Falha na trava de instância |
| MAY-0202 | hotkey | activation | warning | avaliar | Atalho global indisponível |
| MAY-0301 | microphone_dependency | speech_input | error | avaliar | Dependência de áudio indisponível |
| MAY-0302 | microphone_device | speech_input | error | sim | Microfone não encontrado |
| MAY-0303 | voice_model | speech_input | error | avaliar | Modelo de reconhecimento indisponível |
| MAY-0304 | voice_runtime | speech_input | error | sim | Falha no reconhecimento de voz |
| MAY-0305 | noise_suppression | speech_input | error | avaliar | Falha no tratamento de ruído |
| MAY-0306 | voice_timeout | speech_input | error | sim | Reconhecimento excedeu o tempo limite |
| MAY-0307 | voice_server | speech_input | error | sim | Servidor local de voz indisponível |
| MAY-0308 | voice_backpressure | speech_input | warning | sim | Fila de transcrição cheia |
| MAY-0401 | tts_init | speech_output | error | avaliar | Voz não inicializada |
| MAY-0402 | tts_runtime | speech_output | error | sim | Falha ao falar |
| MAY-0403 | tts_fallback | speech_output | warning | avaliar | Voz alternativa acionada |
| MAY-0501 | ui_init | interface | error | avaliar | Interface não inicializada |
| MAY-0502 | ui_runtime | interface | error | avaliar | Falha na interface |
| MAY-0503 | ui_screen | interface | error | avaliar | Monitor indisponível |
| MAY-0504 | ui_position | interface | error | avaliar | Janela não pôde ser posicionada |
| MAY-0601 | input_pipeline | commands | error | avaliar | Falha ao processar entrada |
| MAY-0602 | input_busy | commands | warning | sim | Fila de comandos cheia ou encerrada |
| MAY-0603 | parser | commands | error | avaliar | Falha ao interpretar comando |
| MAY-0604 | dev_command | commands | error | avaliar | Ferramenta de desenvolvimento falhou |
| MAY-0701 | memory_storage | persistence | error | avaliar | Memória local indisponível |
| MAY-0702 | routine_storage | persistence | error | avaliar | Rotina local indisponível |
| MAY-0703 | knowledge_invalid | persistence | warning | avaliar | Registro de conhecimento inválido |
| MAY-0704 | container_invalid | persistence | warning | avaliar | Container de dados inválido |
| MAY-0705 | container_reload | persistence | warning | sim | Falha ao atualizar containers |
| MAY-0706 | knowledge_write | persistence | error | avaliar | Conhecimento não pôde ser salvo |
| MAY-0707 | storage_corrupt | persistence | warning | avaliar | Arquivo de dados ilegível |
| MAY-0708 | backup_failure | persistence | error | avaliar | Backup não pôde ser criado |
| MAY-0801 | app_launch | applications | error | avaliar | Aplicativo não pôde ser aberto |
| MAY-0802 | app_missing | applications | error | avaliar | Aplicativo não encontrado |
| MAY-0803 | app_exit | applications | error | sim | Aplicativo encerrou durante a abertura |
| MAY-0804 | app_stale_lock | applications | error | avaliar | Trava órfã do aplicativo |
| MAY-0805 | app_target | applications | error | avaliar | Alvo da ação indisponível |
| MAY-0901 | web_request | network | error | sim | Serviço web indisponível |
| MAY-0902 | web_timeout | network | error | sim | Consulta web excedeu o tempo limite |
| MAY-0903 | web_payload | network | error | avaliar | Resposta web inválida |
| MAY-1001 | installer | installation | error | avaliar | Falha no instalador |
| MAY-1002 | app_control | installation | error | avaliar | Executável bloqueado pelo Windows |

## eventos locais e interface

As fronteiras de comandos, settings, voz, TTS, persistência, containers, lançamento de apps e operações de janela usam `report_error`. Um erro chega ao texto com código, resumo e próxima ação; falhas de TTS não tentam falar o próprio erro. Avisos e fallbacks não abrem pop-ups automaticamente. Ocorrências repetidas continuam registradas, mas avisos visuais iguais são limitados a um a cada três segundos.

`logs/errors.jsonl` usa o contrato `docs/schemas/error-event.schema.json`. Cada arquivo fica limitado a aproximadamente 1 MiB, com três rotações: no máximo quatro arquivos. O tamanho pode ultrapassar o limite em um registro. A criação usa permissão 0600 em Unix. Falha no registro não interrompe a operação original; ela incrementa um contador e emite uma indicação curta `MAY-0002`, sem despejar o conteúdo do evento.

O evento inclui tipo da exceção, errno/returncode quando existirem e arquivo/linha da origem. Não inclui a mensagem bruta da exceção, traceback completo, variáveis locais, áudio, transcrição, pergunta ou valores do `.env`. Contexto é uma lista restrita de metadados; nunca use uma frase do usuário como nome de operação. Logs antigos `session.log`, logs nativos e stdout/stderr podem conter mensagens legadas e não entram no exportador estruturado.

## mapa e limites

Foram examinados 45 arquivos Python de primeira parte: 178 handlers, 141 retornos de falha, 64 pontos de propagação, 20 atribuições legadas e 70 chamadas explícitas ao registro padrão. As linhas são regeneradas; o identificador do ponto é um fingerprint estático de arquivo, função, tipo e posição relativa.

O mapa cobre a raiz, `core`, `input`, `output`, `helpers` e `scripts`. Cada ponto tem localização, função, tipo, código sugerido e classificação. Código sugerido exige revisão semântica. Os rótulos de fallback/probe descrevem políticas de fronteira e não comprovam que todos os caminhos estejam instrumentados nem que a falha seja inofensiva. O mapa não mede cobertura de execução.

Sete handlers do bootstrap do instalador continuam destacados para revisão: importar dependências novas ali sem validar a máquina limpa pode impedir a instalação. Componentes nativos Qt/ALSA/Whisper, processos externos e o sistema operacional não são varridos pelo AST Python. Falhas nativas fatais ou encerramentos abruptos podem impedir a escrita de um último evento. Precisão de ASR, dessincronização visual e falsas confirmações continuam sendo problemas comportamentais: não podem ser diagnosticados automaticamente como exceções.

## adicionar ou alterar um erro

1. Reutilize uma definição somente se significado e ação forem compatíveis. Adicione códigos novos antes de utilizá-los.
2. Defina português e inglês, categoria, gravidade, repetibilidade e causas possíveis.
3. Registre na fronteira que sabe o resultado da operação. Não marque um fallback como falha definitiva nem um retorno `False` como sucesso.
4. Preserve contratos existentes; não execute recuperação destrutiva a partir do código de erro.
5. Passe somente operação constante e contexto permitido. Não passe texto reconhecido, senha, token, URL de consulta ou dados pessoais.
6. Faça um teste de falha controlada e execute a auditoria para verificar códigos e sintaxe.

## atualizar e exportar

```bash
.venv/bin/python scripts/audit_errors.py
.venv/bin/python scripts/export_diagnostics.py --output /caminho/diagnostico.json
QT_QPA_PLATFORM=offscreen .venv/bin/python -m unittest discover -s tests -v
```

O exportador inclui somente eventos estruturados recentes e o catálogo. Não lê `.env`, memória, áudio ou logs brutos; reconstruções de mensagem e ação vêm do registro de códigos. O mapa estático e o bug hunter podem ser compartilhados separadamente.
