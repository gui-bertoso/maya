# Arquitetura

## Fluxo principal

```text
Microfone / texto / hotkey / palmas
                ↓
        Voice + wake detection
                ↓
       AsyncInputPipeline
                ↓
        App → Process → ações
          ↙       ↓       ↘
       dados   Renderer   Speaker
```

`app.py` compõe os serviços e controla o ciclo de vida. Ele não deve concentrar regras específicas que possam viver em módulos menores.

## Responsabilidades

- `core/`: regras de domínio, intenções, memória, rotina e coordenação assíncrona.
- `input/`: captura e interpretação de sinais de entrada.
- `output/`: apresentação visual e sonora.
- `helpers/`: adaptadores para sistema operacional e serviços externos.
- `data/`: conteúdo editável e estado persistente local.
- `scripts/`: tarefas operacionais que não fazem parte do runtime.

## Concorrência

A captura do microfone, o reconhecimento, o processamento de comandos, a interface e o TTS trabalham fora uns dos outros. O `AsyncInputPipeline` impede que trabalho pesado bloqueie o áudio. Um semáforo serializa alterações de estado e outro limita entradas pendentes.

Filas devem continuar limitadas. Criar mais threads sem medir não aumenta desempenho e pode piorar ordem, memória e desligamento.

## Dependências

O núcleo depende de interfaces simples expostas pelo `App`. Integrações de sistema ficam em `helpers/`; o domínio não deve importar componentes visuais. Novos recursos grandes devem ganhar módulo e testes próprios.
