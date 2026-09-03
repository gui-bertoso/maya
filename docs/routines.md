# Rotinas pessoais

O `RoutineManager` mantém o planejamento diário em `data/routine.json`.

## Presets

- Rotina A: treino às 06:00 e blocos de trabalho/estudo ao longo do dia.
- Rotina B: treino às 14:00 e manhã ajustada para trabalho e descanso.

Atividades podem estar pendentes, em andamento, concluídas ou ignoradas. Conclusões concedem XP somente uma vez; o streak considera dias com progresso real.

## Adaptação

`!awake HH:MM` desloca blocos flexíveis quando o usuário acorda atrasado, preservando compromissos fixos. A prioridade atual é: compromissos fixos, trabalho, Rust, inglês, planejamento internacional e lazer.

## Persistência

O arquivo contém versão do esquema, rotina ativa, dias registrados e preferências. Mudanças futuras devem incluir migração explícita do esquema e nunca apagar histórico silenciosamente.

## Lembretes

O runtime verifica lembretes por minuto e registra os já enviados para evitar repetição. Futuras quiet hours devem bloquear interrupções sem perder o evento pendente.
