"""Local conversational policy; never parses or executes desktop actions.

State belongs to the clearable dialogue frame, not permanent user facts.
Matching is deliberately explicit: an unknown statement isn't evidence of a mood.
"""
import re


class ConversationPolicy:
    MODES = {
        'acolher': r'\b(so (?:quero )?desabafar|sem conselhos|so me escuta|modo acolher)\b',
        'racional': r'\b(seja racional|modo racional|analisa comigo|vamos analisar)\b',
        'casual': r'\b(muda de assunto|mudar de assunto|papo leve|modo casual)\b',
        'motivar': r'\b(me motiva|me da um incentivo|modo motivacional)\b',
    }
    TOPICS = (
        ('solidao', r'\b(?:me sinto|me sentindo|estou|to|tou)\b.{0,35}\b(?:sozinh[oa]|solitari[oa]|solitario|solitaria)\b|\bninguem (?:liga pra mim|se importa comigo)\b'),
        ('desanimo', r'\b(?:estou|to|me sinto|me sentindo)\b.{0,25}\b(?:desanimad[oa]|sem motivacao|fracassad[oa]|inutil)\b|\bnao consigo fazer nada\b'),
        ('existencial', r'\b(?:qual (?:e )?o sentido da vida|nada faz sentido|vida nao tem sentido|por que existimos|medo de morrer|livre arbitrio)\b'),
        ('racional', r'\b(?:todo mundo me odeia|sempre estrago tudo|nunca vou conseguir|sou um fracasso|concorda comigo)\b'),
        ('casual', r'\b(?:vamos conversar|bora conversar|puxa (?:um )?assunto|me distrai|conversa comigo)\b'),
    )
    REPLIES = {
        'solidao': (
            'sentir falta de companhia pesa. quer contar o que mais fez falta hoje, ou prefere um papo leve por enquanto?',
            'essa falta de companhia aparece mais em algum momento do dia, ou hoje aconteceu alguma coisa específica?',
            'podemos conversar sobre isso aqui. também vale pensar em alguém com quem você gostaria de retomar contato, sem precisar fazer um grande desabafo.',
        ),
        'desanimo': (
            'estar travado não prova que você é incapaz. o que está pegando mais: cansaço, medo de dar errado ou não saber por onde começar?',
            'vamos diminuir a cobrança: qual pedacinho disso cabe na energia que você tem hoje?',
            'um dia ruim é uma informação sobre o dia, não um veredito sobre você. dá pra ajustar a expectativa antes de exigir mais esforço.',
        ),
        'existencial': (
            'não tenho uma resposta definitiva sobre o sentido da vida. você está pensando nisso como uma questão filosófica ou isso está pesando no seu dia?',
            'uma possibilidade é que sentido seja algo construído nas relações e escolhas. isso não resolve tudo: o que faria essa ideia parecer insuficiente pra você?',
            'se o universo não entrega um propósito pronto, isso implica ausência de valor? acho que essa passagem merece ser questionada.',
        ),
        'racional': (
            'eu não compraria essa conclusão sem examinar. o que aconteceu de concreto, e o que você está inferindo a partir disso?',
            'vamos testar a ideia: existe algum caso que contrarie esse “sempre”, “nunca” ou “todo mundo”? uma exceção já muda a conclusão.',
            'posso concordar com parte do argumento e discordar do salto final. qual evidência faria você mudar de opinião?',
        ),
        'casual': (
            'tá: se você pudesse inventar uma regra absurda pra um jogo, qual seria? eu apostaria num inventário que reclama das suas escolhas.',
            'um dilema inútil porém respeitável: morar numa floresta com internet perfeita ou numa cidade onde nunca existe barulho de obra?',
            'acho interessante como um jogo consegue tornar divertido algo que seria um inferno na vida real. organizar inventário, por exemplo. por quê?',
        ),
    }

    @staticmethod
    def _pick(state, key, choices):
        counts = state.setdefault('reply_counts', {})
        index = counts.get(key, 0)
        counts[key] = index + 1
        return choices[index % len(choices)]

    def reply(self, text, clean, frame):
        state = frame.setdefault('conversation', {'topic': None, 'mode': None, 'turns': [], 'idle': 0})
        # Boundaries also apply outside an active emotional conversation.
        if re.search(r'\b(?:so preciso de voce|so voce me entende|nao preciso de (?:mais )?ninguem|voce e humana|voce tem sentimentos)\b', clean):
            return 'sou uma ia, sem sentimentos ou vivências humanas. posso conversar e ajudar a organizar ideias, mas não substituo relações com pessoas. o que está faltando nas suas conversas fora daqui?'
        if re.search(r'\b(?:quero me matar|vou me matar|vou me machucar|quero acabar com minha vida)\b', clean):
            return 'vou levar isso a sério. você está em perigo imediato ou já se machucou? procure alguém de confiança para ficar com você agora e, se houver risco imediato, acione o serviço de emergência local. afaste de você o que poderia usar para se ferir, se conseguir fazer isso com segurança.'
        mode = next((name for name, pattern in self.MODES.items() if re.search(pattern, clean)), None)
        topic = next((name for name, pattern in self.TOPICS if re.search(pattern, clean)), None)
        # Abstract discussions remain in the knowledge catalog.
        if clean.startswith(('fale sobre ', 'um exemplo de ', 'uma pergunta sobre ')):
            topic = None
        active = state.get('topic') if state.get('idle', 0) < 3 else None
        followup = bool(active and re.match(r'^(?:e por que|por que|como assim|continua|continue|nao sei|acho que|porque|e que|mas |sim\b|nao\b|hoje\b|desde\b|isso\b|eu \b|so \b|talvez\b|discordo\b)', clean))
        if not (mode or topic or followup):
            state['idle'] = state.get('idle', 0) + 1
            return None
        previous = active
        topic = topic or ('casual' if mode == 'casual' else active) or 'desanimo'
        if mode:
            state['mode'] = mode
        elif topic != previous:
            state['mode'] = None
        state['topic'], state['idle'] = topic, 0
        # Keep exact user words and provenance; don't infer diagnoses or stored traits.
        state['turns'] = (state.get('turns', []) + [{'role': 'user', 'text': text.strip()[:600], 'topic': topic}])[-12:]
        frame['topic'] = None  # Don't attach personal follow-ups to an old technical topic.
        frame['pending_topics'] = []
        if mode == 'acolher':
            return 'tá, sem tentar consertar tudo. pode contar do seu jeito, sem precisar organizar antes.'
        if clean in {'discordo', 'nao concordo'}:
            return 'justo questionar. qual parte não se sustenta pra você? eu também posso estar usando uma premissa errada.'
        if state.get('mode') == 'acolher' and followup and not topic == 'casual':
            return self._pick(state, 'acolher', (
                'o que você contou não precisa virar uma tarefa agora. pode continuar, estou acompanhando o que você escreve.',
                'qual parte disso você queria que as pessoas entendessem melhor?',
            ))
        if mode == 'motivar' or (state.get('mode') == 'motivar' and followup):
            return self._pick(state, 'motivar', (
                'não vou te prometer que vai dar tudo certo. mas dá pra escolher um passo pequeno que dependa de você, sem resolver a vida inteira hoje.',
                'se hoje só cabe uma tentativa curta, ela ainda conta. qual é a menor versão daquilo que você quer fazer?',
            ))
        if mode == 'racional' or (state.get('mode') == 'racional' and followup):
            return self._pick(state, 'analise', (
                'vamos separar o acontecimento, sua interpretação e o que ainda não sabemos. qual foi o acontecimento?',
                'que outra explicação cabe nos mesmos fatos? não precisa ser mais otimista, só plausível.',
            ))
        if followup and topic == previous and clean not in {'continua', 'continue', 'e por que', 'por que', 'como assim', 'nao sei', 'sim'}:
            return self._pick(state, topic + ':followup', (
                f'você disse: “{text.strip()[:180]}”. qual parte disso pesa mais agora?',
                'isso muda o foco da conversa. você quer explorar o motivo ou pensar no que fazer com essa situação?',
            ))
        return self._pick(state, topic, self.REPLIES[topic])
