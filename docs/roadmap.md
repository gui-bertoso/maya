# Roadmap

O mapa visual detalhado está no [Miro](https://miro.com/app/board/uXjVHr5wgpk=/).

## Próximos três

1. Telemetria real de latência por etapa.
2. Barge-in robusto: parar a resposta quando o usuário começar a falar.
3. Diagnóstico e calibração de áudio.

## Fases

### 0 — Fundação e estabilidade

Health checks, logs estruturados com privacidade, recuperação de crashes, validação de configuração e organização contínua do repositório. Meta: 99% dos startups sem erro.

### 1 — Voz em tempo real

Streaming ASR/TTS, cancelamento de eco, seleção automática de microfone e benchmark. Metas: p50 abaixo de 500 ms e p95 abaixo de 900 ms.

### 2 — Cérebro modular

Registro de comandos/plugins, roteamento por confiança, contexto com expiração, fallback inteligente e testes amplos de intenção em português.

### 3 — Life OS

Calendário, planejamento adaptativo, pomodoro, quiet hours, dashboard semanal, exportação e sugestões proativas controláveis.

### 4 — Experiência

Onboarding, ícone na bandeja, painel de diagnóstico, acessibilidade, temas e controles visuais de voz/microfone.

### 5 — Produto e distribuição

CI, assinatura digital, instalação em máquina limpa, atualização com rollback, release notes, documentação de privacidade, backup e restauração.

## Qualidade transversal

Testes unitários e de integração, soak test de áudio, limites de threads/filas, tratamento de permissões e nenhuma gravação de áudio por padrão.

## Pesquisa futura

Wake word neural customizada, diarização, visão de tela opcional, automações por plugins, modelo local pequeno, sincronização entre dispositivos e aplicativo móvel companheiro.
