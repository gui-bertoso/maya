# Códigos de erro da Maya

Todo erro conhecido usa `MAY-NNNN`. Erros ainda não classificados recebem `MAY-0001`, então nenhum traceback fica sem identificador.

| Código | Área | Significado | Primeira ação |
|---|---|---|---|
| MAY-0001 | Geral | Erro interno inesperado | Consultar o traceback no log |
| MAY-0101 | Configuração | Sem acesso ao `.env` | Fechar duplicatas e conferir permissões |
| MAY-0102 | Configuração | Estrutura local inválida | Restaurar os arquivos locais |
| MAY-0103 | Configuração | Valor inválido | Corrigir o campo indicado |
| MAY-0201 | Processo | Trava de instância falhou | Encerrar instâncias antigas |
| MAY-0202 | Atalho | Atalho global indisponível | Conferir permissões e `pynput` |
| MAY-0301 | Voz | Dependência de áudio ausente | Reinstalar dependências |
| MAY-0302 | Voz | Microfone não encontrado | Selecionar um dispositivo de entrada |
| MAY-0303 | Voz | Modelo Vosk indisponível | Conferir o modelo e seu caminho |
| MAY-0304 | Voz | Reconhecimento falhou | Conferir microfone e log |
| MAY-0305 | Voz | Supressão de ruído falhou | Revisar os parâmetros de áudio |
| MAY-0401 | Fala | Motor TTS não iniciou | Trocar ou reinstalar o motor |
| MAY-0402 | Fala | Reprodução da voz falhou | Tentar outro motor de voz |
| MAY-0501 | Interface | Qt não iniciou | Conferir PySide6 e DLLs |
| MAY-0502 | Interface | Interface falhou em execução | Reabrir e consultar o log |
| MAY-0601 | Entrada | Pipeline de comando falhou | Repetir o comando |
| MAY-0701 | Dados | Memória não pôde ser salva | Conferir a pasta `data` |
| MAY-0702 | Dados | Rotina não pôde ser salva | Conferir `routine.json` |
| MAY-0801 | Apps | Aplicativo não abriu | Conferir caminho e permissão |
| MAY-0901 | Web | Serviço externo indisponível | Conferir conexão |
| MAY-1001 | Instalação | Instalador falhou | Consultar o log do instalador |
| MAY-1002 | Instalação | Windows bloqueou o executável | Assinar ou liberar pela política |

## Regra para novos erros

1. Reutilize um código quando causa e ação forem as mesmas.
2. Crie o código em `helpers/errors.py` antes de usá-lo.
3. Registre contexto técnico no log, mas mostre ao usuário código, resumo e ação.
4. Nunca exponha apenas `PermissionError`, `OSError` ou um traceback sem código.

## Faixas reservadas

- `0000`: falhas gerais
- `0100`: configuração
- `0200`: processo e ativação
- `0300`: entrada de voz
- `0400`: saída de voz
- `0500`: interface
- `0600`: processamento de comandos
- `0700`: persistência
- `0800`: aplicativos locais
- `0900`: rede
- `1000`: instalação e atualização
