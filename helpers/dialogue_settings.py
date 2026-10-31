"""Tunable behavior and resource budgets. Maya's identity is intentionally fixed."""
from dataclasses import dataclass
import math


@dataclass(frozen=True)
class Setting:
    key: str
    default: str
    cast: type
    category: str
    label: str
    help: str
    pt_label: str
    pt_help: str
    options: tuple = ()
    bounds: tuple | None = None


def number(key, default, cast, category, label, pt_label, help_text, bounds):
    return Setting(key, str(default), cast, category, label, help_text, pt_label, help_text, bounds=bounds)


def choice(key, default, label, pt_label, options, help_text):
    return Setting(key, default, str, 'Conversation style', label, help_text, pt_label, help_text, options)


SETTINGS = (
    number('LOCAL_DIALOGUE_TEMPERATURE', .55, float, 'Local model', 'Creativity', 'Criatividade', '0 = mais previsível; valores altos aumentam variedade e também erros.', (0, 1.5)),
    number('LOCAL_DIALOGUE_TOP_P', .8, float, 'Local model', 'Word variety', 'Variedade de palavras', 'Limita as alternativas de geração. O padrão costuma funcionar melhor.', (.1, 1)),
    number('LOCAL_DIALOGUE_MAX_TOKENS', 384, int, 'Local model', 'Reply budget', 'Limite de resposta (tokens)', 'Respostas maiores demoram mais. Aproximadamente 1 token por palavra curta ou parte dela.', (64, 1024)),
    number('LOCAL_DIALOGUE_CONTEXT', 8192, int, 'Local model', 'Context capacity', 'Capacidade de contexto (tokens)', 'Aumentar usa mais VRAM. 8192 é o padrão para esta instalação de 8 GB.', (4096, 16384)),
    number('LOCAL_DIALOGUE_GPU_LAYERS', 99, int, 'Local model', 'GPU layers', 'Camadas na GPU', '0 usa CPU; 99 tenta colocar todas as camadas na GPU. Valores menores economizam VRAM.', (0, 99)),
    number('LOCAL_DIALOGUE_THREADS', 8, int, 'Local model', 'CPU threads', 'Threads da CPU', 'Trabalho de CPU do motor local. Mais threads nem sempre significam mais velocidade.', (1, 32)),
    number('LOCAL_DIALOGUE_IDLE_SECONDS', 180, int, 'Local model', 'GPU idle sleep (seconds)', 'Descanso da GPU (segundos)', 'Libera o modelo após inatividade; 0 mantém carregado. A próxima conversa recarrega.', (0, 3600)),
    number('LOCAL_DIALOGUE_TIMEOUT', 45, float, 'Local model', 'Reply timeout (seconds)', 'Espera máxima pela resposta (segundos)', 'Ao exceder, a Maya usa o diálogo nativo e espera antes de tentar novamente.', (5, 180)),
    number('LOCAL_DIALOGUE_STARTUP_TIMEOUT', 60, float, 'Local model', 'Load timeout (seconds)', 'Espera máxima para carregar (segundos)', 'Tempo permitido para carregar os pesos na primeira conversa.', (5, 180)),
    number('LOCAL_DIALOGUE_HISTORY_MESSAGES', 12, int, 'Conversation memory', 'Recent messages', 'Mensagens recentes no contexto', 'Conta mensagens do usuário e da Maya; 0 desliga o histórico recente enviado ao modelo.', (0, 40)),
    number('LOCAL_DIALOGUE_HISTORY_CHARS', 6000, int, 'Conversation memory', 'Recent text budget', 'Tamanho do histórico recente', 'Limite em caracteres; mensagens antigas saem primeiro para respeitar o contexto.', (500, 14000)),
    number('LOCAL_DIALOGUE_RECALL_COUNT', 3, int, 'Conversation memory', 'Retrieved exchanges', 'Conversas antigas recuperadas', 'Quantidade de trocas antigas relacionadas ao assunto; 0 desliga essa busca.', (0, 8)),
    number('LOCAL_DIALOGUE_RECORD_LIMIT', 256, int, 'Conversation memory', 'Stored exchanges', 'Limite de trocas guardadas', 'Máximo de trocas episódicas locais; 0 apaga e desliga esse histórico na próxima conversa.', (0, 2048)),
    number('LOCAL_DIALOGUE_RECORD_CHARS', 4000, int, 'Conversation memory', 'Retrieved text budget', 'Espaço para lembranças recuperadas', 'Limite em caracteres para fatos, entidades e trechos anteriores enviados ao modelo.', (500, 8000)),
    choice('CONVERSATION_LENGTH', 'balanced', 'Response length', 'Tamanho preferido das respostas', ('short', 'balanced', 'detailed'), 'É uma preferência; perguntas complexas ainda podem precisar de explicação.'),
    choice('CONVERSATION_TONE', 'adaptive', 'Tone', 'Tom da conversa', ('adaptive', 'gentle', 'direct', 'analytical', 'playful'), 'Adapta o jeito de responder. Em sofrimento, acolhimento continua tendo prioridade.'),
    choice('CONVERSATION_HUMOR', 'moderate', 'Humor', 'Intensidade do humor', ('off', 'low', 'moderate', 'high'), 'Controla brincadeiras, sem usar ironia em momentos de sofrimento.'),
    choice('CONVERSATION_PROFANITY', 'light', 'Informal language', 'Palavrões e informalidade', ('off', 'light', 'natural'), 'Permite linguagem informal com moderação, sem ataques ou humilhação.'),
    choice('CONVERSATION_QUESTIONS', 'balanced', 'Follow-up questions', 'Perguntas de continuação', ('sparse', 'balanced', 'curious'), 'Define se a Maya pergunta pouco ou explora mais o assunto. Sem interrogatório automático.'),
    choice('CONVERSATION_EMOJIS', 'occasional', 'Emojis', 'Uso de emojis', ('none', 'occasional', 'frequent'), 'Preferência de expressão na conversa, sem afetar identidade ou limites.'),
    choice('CONVERSATION_CHALLENGE', 'balanced', 'Critical discussion', 'Intensidade do debate', ('gentle', 'balanced', 'challenging'), 'Ajusta o quanto questiona premissas. Discordância deve ter razões em qualquer modo.'),
)


def values():
    from helpers.config import get_env
    result = {}
    for spec in SETTINGS:
        raw = get_env(spec.key, spec.default)
        try:
            value = spec.cast(raw)
            if spec.bounds and (not math.isfinite(value) or not spec.bounds[0] <= value <= spec.bounds[1]):
                raise ValueError('Out of range')
            if spec.options and value not in spec.options:
                raise ValueError('Invalid option')
        except (ValueError, TypeError, OverflowError):
            value = spec.cast(spec.default)
        result[spec.key] = value
    return result


OPTION_PT = {
    'short': 'curtas', 'balanced': 'equilibrado', 'detailed': 'detalhadas',
    'adaptive': 'adaptativo', 'gentle': 'acolhedor', 'direct': 'direto',
    'analytical': 'analítico', 'playful': 'brincalhão', 'off': 'desligado',
    'low': 'baixo', 'moderate': 'moderado', 'high': 'alto', 'light': 'leve',
    'natural': 'natural', 'sparse': 'poucas', 'curious': 'curiosa', 'none': 'nenhum',
    'occasional': 'ocasionais', 'frequent': 'frequentes', 'challenging': 'questionador',
}
