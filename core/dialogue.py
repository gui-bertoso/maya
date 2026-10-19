"""Native contextual retrieval: lexical evidence, conversation frames and replies."""
import json
import math
import re
import unicodedata
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path
from helpers.config import get_env, get_resource_path


def normalize(text):
    text = ''.join(c for c in unicodedata.normalize('NFKD', str(text).lower()) if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9 ]', ' ', text).strip()


STOP = set('a o as os um uma de do da dos das e em no na nos nas para pra por que como eu voce me meu minha um sobre fala fale explica explique quero saber pode poderia qual'.split())


def tokens(text):
    return {word[:-1] if word.endswith('s') and len(word) > 3 else word
            for word in set(normalize(text).split()) - STOP}


class DialogueEngine:
    ACTIONS = ('launch_app', 'close_app', 'spotify_action', 'subapp_action', 'web_action',
               'media_action', 'move_window', 'window_state', 'move_app', 'scale_app',
               'window_showcase', 'exit_self', 'background_app', 'hide_input_window',
               'dev_project_action', 'dev_workspace_action', 'dev_workspace_exit_action',
               'thoughtful_workspace_action', 'sets_fact', 'sets_preference', 'removes_preference')

    def __init__(self, path=None):
        path = Path(path) if path else get_resource_path('data/dialogue_catalog.json')
        self.topics = json.loads(path.read_text(encoding='utf-8'))['topics']
        self.by_id = {topic['id']: topic for topic in self.topics}
        if len(self.by_id) != len(self.topics):
            raise ValueError('Duplicate dialogue topic ID')
        self.documents = {t['id']: tokens(' '.join([t['title'], *t['aliases']])) for t in self.topics}
        counts = Counter(word for document in self.documents.values() for word in document)
        self.idf = {word: math.log(1 + len(self.topics) / count) for word, count in counts.items()}

    @staticmethod
    def frame(memory):
        return memory.state.setdefault('dialogue', {'topic': None, 'last_kind': None,
            'recent': [], 'notes': [], 'entity': None, 'pending_topics': []})

    def ranked_topics(self, text):
        query = tokens(text)
        results = []
        clean = normalize(text)
        for topic in self.topics:
            document = self.documents[topic['id']]
            overlap = query & document
            lexical = sum(self.idf[w] for w in overlap) / max(1, sum(self.idf.get(w, 2) for w in query))
            exact = any(re.search(r'\b' + re.escape(normalize(alias)) + r'\b', clean) for alias in [topic['title'], *topic['aliases']])
            # Character similarity is supporting evidence, never an action router.
            query_text = ' '.join(sorted(query))
            fuzzy = max((SequenceMatcher(None, query_text, ' '.join(sorted(tokens(a)))).ratio() for a in topic['aliases']), default=0)
            if not overlap and fuzzy >= .88 and len(query_text) >= 5:
                lexical = .7 * fuzzy
            score = .78 * lexical + .22 * fuzzy + (.3 if exact else 0)
            if exact or (score >= .68 and (overlap or fuzzy > .87)):
                results.append((score, topic))
        return sorted(results, key=lambda item: item[0], reverse=True)

    @staticmethod
    def kind(text):
        clean = normalize(text)
        for key, pattern in [
            ('why', r'\b(por que|porque|motivo|importancia)\b'),
            ('example', r'\b(exemplo|exemplifica|exemplifique)\b'),
            ('pitfall', r'\b(erro|erros|armadilha|cuidado|evitar)\b'),
            ('challenge', r'\b(desafio|exercicio|praticar|pratica)\b'),
            ('reflection', r'\b(pergunta|refletir|reflexao)\b'),
            ('next', r'\b(proximo passo|depois disso|e depois|outra dica|mais uma)\b'),
            ('how', r'\b(como|comecar|comeco|primeiro passo|aplicar)\b'),
        ]:
            if re.search(pattern, clean):
                return key
        return 'intro'

    def reply(self, text, memory, patterns):
        if not memory or get_env('DIALOGUE_ENABLED', 'true').lower() != 'true':
            return None
        memory.short_term_limit = max(memory.short_term_limit, 80)
        frame = self.frame(memory)
        clean = normalize(text)
        if clean in {'limpa o contexto', 'limpar contexto', 'esquece essa conversa', 'clear context'}:
            memory.state.pop('dialogue', None)
            memory.clear_short_term()
            return 'contexto da conversa limpo. suas preferências e fatos salvos continuam guardados.'
        if any(patterns.get(flag) for flag in self.ACTIONS):
            return None
        # Named user entities are explicit statements, not guesses from questions.
        match = re.fullmatch(r'(?:meu|minha) (jogo|projeto|app|aplicativo|personagem) (?:se chama|chama|e chamado|e chamada) (.{1,80})', clean)
        if match:
            kind, name = match.groups()
            original = re.search(r'(?:se chama|chama|é chamado|é chamada)\s+(.+)', text, re.I)
            name = original.group(1).strip(' .!?') if original else name
            frame['entity'] = {'kind': kind, 'name': name, 'details': []}
            frame.setdefault('entities', {})[kind] = frame['entity']
            return f'beleza, seu {kind} se chama {name}. vou usar essa referência enquanto conversamos.'
        entity = frame.get('entity')
        detail = re.fullmatch(r'(?:ele|ela|esse projeto|esse jogo) (?:usa|e feito em|foi feito em) (.{1,100})', clean)
        if detail and entity:
            fact = f"{entity['name']} usa {detail.group(1)}"
            entity['details'].append(fact)
            entity['details'] = entity['details'][-12:]
            if fact not in frame['notes']:
                frame['notes'].append(fact)
            return f"anotado no contexto: {fact}."
        mentioned = re.search(r'\b(jogo|projeto|app|aplicativo|personagem)\b', clean)
        if mentioned and mentioned.group(1) in frame.get('entities', {}):
            entity = frame['entities'][mentioned.group(1)]
        if entity and re.search(r'\b(qual|lembra|lembre|recorda|aquele|aquela)\b', clean) and re.search(r'\b(jogo|projeto|app|ele|ela)\b', clean):
            details = '; '.join(entity['details'])
            return f"você me disse que seu {entity['kind']} se chama {entity['name']}." + (f' também disse: {details}.' if details else '')
        if clean in {'resume nossa conversa', 'resuma nossa conversa', 'o que conversamos', 'resuma o contexto'}:
            notes = frame['notes'][-6:]
            topic = self.by_id.get(frame.get('topic'))
            pieces = ([f"o assunto mais recente foi {topic['title']}"] if topic else []) + notes
            return ('até aqui: ' + '; '.join(pieces) + '.') if pieces else 'ainda não tenho contexto suficiente pra resumir. me conta o que você está fazendo.'
        # Retrieve only actual saved user facts, retaining their provenance.
        if re.search(r'\b(lembra|lembre|recorda)\b.*\b(sobre|de|do|da)\b', clean):
            query = tokens(clean) - {'lembra', 'lembre', 'recorda'}
            facts = [*frame['notes'], *memory.get_known_facts()]
            matches = [(len(tokens(fact) & query), fact) for fact in facts]
            matches = sorted((m for m in matches if m[0]), reverse=True)
            if matches:
                return 'você me contou: ' + '; '.join(f for _, f in matches[:3]) + '.'
        ranked = self.ranked_topics(text)
        pending = frame.get('pending_topics', [])
        if pending:
            selected = next((t for _, t in ranked if t['id'] in pending), None)
            if selected:
                ranked = [(2.0, selected)]
                frame['pending_topics'] = []
        if len(ranked) > 1 and abs(ranked[0][0] - ranked[1][0]) < .10:
            candidates = [ranked[0][1], ranked[1][1]]
            frame['pending_topics'] = [t['id'] for t in candidates]
            return f"você quer falar de {candidates[0]['title']} ou de {candidates[1]['title']}?"
        active = self.by_id.get(frame.get('topic'))
        if active and not ranked:
            if clean in {'nao entendi', 'como assim', 'explica melhor', 'me explica melhor'}:
                return f"vamos por uma ação concreta em {active['title']}: " + active['replies']['how']
            if clean in {'discordo', 'nao concordo'}:
                return f"qual parte da ideia sobre {active['title']} você discorda? podemos comparar as premissas."
            if clean in {'fiz', 'terminei', 'consegui', 'pronto'} and frame.get('last_kind') == 'challenge':
                return 'boa. o que você observou ao fazer o exercício? ' + active['replies']['reflection']
            if re.match(r'^(?:acho que|pra mim|eu penso que|o problema e|eu prefiro|tenho dificuldade com|nao consegui)\b', clean):
                note = f"sobre {active['title']}, você disse: {text.strip()}"
                frame['notes'] = (frame['notes'] + [note])[-64:]
                return f"vou manter essa observação no contexto de {active['title']}. " + active['replies']['reflection']
        followup = bool(re.fullmatch(r'(?:e )?(?:por que|porque|como assim|me da um exemplo|um exemplo|exemplo|como comecar|como aplicar|e depois|depois disso|proximo passo|outra dica|mais uma|continua|continue|me explica melhor|qual o cuidado|qual o erro|um desafio|me desafia|uma pergunta)(?: entao)?', clean))
        topic = ranked[0][1] if ranked else (self.by_id.get(frame.get('topic')) if followup else None)
        if topic is None:
            if followup:
                return 'sobre qual assunto? ainda não tenho uma referência clara pra continuar.'
            return None
        kind = self.kind(text)
        if followup and kind == 'intro':
            kind = 'how' if frame.get('last_kind') != 'how' else 'example'
        interaction = topic['replies'][kind]
        key = topic['id'] + ':' + kind
        frame['topic'], frame['last_kind'] = topic['id'], kind
        frame['recent'] = (frame['recent'] + [key])[-32:]
        memory.set_last_topic(topic['title'])
        return interaction

    @staticmethod
    def remember_app(memory, target, window_id=None):
        import time
        if memory:
            memory.state['app_reference'] = {'target': target, 'window_id': window_id,
                                             'used_at': time.time()}

    @staticmethod
    def resolve_action(text, memory):
        import time
        if get_env('DIALOGUE_ENABLED', 'true').lower() != 'true':
            return text, None
        clean = normalize(text)
        clean = re.sub(r'^(?:agora|now|entao)\s+', '', clean)
        # Resolve only explicit command shapes. Never replace words inside stories.
        move = re.fullmatch(r'(?:move|mova|arrasta|arraste|joga|jogue|coloca|coloque)\s+(?:ele|ela|isso|it|essa janela|esse app)\s+(?:para|pra|pro|to)\s+(.+)', clean)
        short = re.fullmatch(r'(?:para|pra|pro|to)\s+(.+)', clean)
        close = re.fullmatch(r'(?:fecha|feche|close)\s+(?:ele|ela|isso|it|essa janela|esse app)', clean)
        if not (move or short or close):
            return text, None
        reference = memory.state.get('app_reference') if memory else None
        if not reference or time.time() - reference.get('used_at', 0) > 180:
            return text, 'qual aplicativo você quer dizer? diga o nome pra eu usar a referência certa.'
        target = reference['target']
        if close:
            return f'close {target}', None
        return f"mova {target} para {(move or short).group(1)}", None
