"""Read-only capability inventory backed by allowlisted Python definitions.

No eval/import of inspected source, arbitrary paths, secrets or model-made tools.
"""
import ast
from functools import lru_cache
from pathlib import Path
import re
import unicodedata

from helpers.config import get_env, get_resource_path, get_runtime_path
from helpers.local_dialogue import runtime_status

# id, description, source, class, required method, attached component, example
CAPABILITIES = (
    ('dialogue', 'conversar com contexto', 'core/dialogue.py', 'DialogueEngine', 'reply', 'memory', 'vamos conversar sobre uma ideia'),
    ('memory', 'guardar e recuperar memória local', 'core/memory.py', 'Memory', 'save', 'memory', 'meu jogo se chama Remnants'),
    ('learning', 'aprender respostas e atalhos explícitos', 'core/learning.py', 'LearningEngine', 'handle', 'knowledge_base', 'aprenda: pergunta => resposta'),
    ('apps', 'abrir e fechar aplicativos', 'helpers/app_launcher.py', 'AppLauncher', 'launch', 'app_launcher', 'open spotify'),
    ('windows', 'organizar janelas pela interface', 'core/process.py', 'Process', 'parse_external_window_move_request', 'parent', 'mova spotify para esquerda'),
    ('web', 'pesquisar com fontes na internet', 'helpers/web_assistant.py', 'WebAssistant', 'research', 'web_assistant', 'pesquise e aprenda sobre Python'),
    ('spotify', 'pedir buscas no Spotify', 'helpers/spotify_assistant.py', 'SpotifyAssistant', 'parse_request', 'spotify_assistant', 'search spotify for jazz'),
    ('projects', 'criar projetos a partir de modelos', 'helpers/dev_assistant.py', 'DevAssistant', 'create_project', 'dev_assistant', 'create python project called exemplo'),
    ('routine', 'acompanhar a rotina configurada', 'core/routine_manager.py', 'RoutineManager', 'handle_command', 'routine_manager', 'minha rotina'),
    ('voice', 'reconhecer fala', 'input/voice.py', 'Voice', 'start_background', None, 'falar depois da palavra de ativação'),
    ('speech', 'produzir respostas faladas', 'output/speaker.py', 'Speaker', 'speak', None, 'responder por voz'),
    ('local_model', 'gerar conversa com o modelo local', 'helpers/local_dialogue.py', 'LocalDialogueRuntime', 'generate', 'memory', 'me ajuda a pensar nessa ideia'),
)
EXTRA_SOURCES = ('core/local_conversation.py', 'core/conversation.py', 'helpers/self_knowledge.py')


@lru_cache(maxsize=64)
def _index(path, modified_ns, size):
    if size > 1_000_000:
        return {}
    tree = ast.parse(Path(path).read_text(encoding='utf-8'))
    result = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith('_'):
            result.setdefault('module', {})[node.name] = node.lineno
        if isinstance(node, ast.ClassDef):
            result[node.name] = {method.name: method.lineno for method in node.body
                                 if isinstance(method, (ast.FunctionDef, ast.AsyncFunctionDef))
                                 and not method.name.startswith('_')}
    return result


def inspect_source(relative):
    allowed = {spec[2] for spec in CAPABILITIES} | set(EXTRA_SOURCES)
    if relative not in allowed:
        return {}
    path = get_resource_path(relative)
    try:
        # Do not follow a replacement symlink outside the source tree.
        if not path.resolve().is_relative_to(get_resource_path('.').resolve()):
            return {}
        info = path.stat()
        return _index(str(path), info.st_mtime_ns, info.st_size)
    except (OSError, SyntaxError, UnicodeError):
        return {}


def snapshot(process):
    items = []
    for key, label, path, cls, method, component, example in CAPABILITIES:
        implemented = method in inspect_source(path).get(cls, {})
        connected = getattr(process, component, None) is not None if component else False
        detail = 'componente conectado; execução ainda depende do alvo e do sistema'
        parent = getattr(process, 'parent', None)
        if key == 'windows':
            connected = getattr(parent, 'renderer', None) is not None
            detail = 'interface conectada; controle depende do backend de janelas'
        elif key == 'voice':
            voice = getattr(parent, 'voice', None)
            connected = voice is not None and bool(getattr(parent, 'microphone_enabled', False))
            detail = 'microfone habilitado; reconhecimento não testado por esta inspeção'
        elif key == 'speech':
            connected = getattr(parent, 'speaker', None) is not None and not bool(getattr(parent, 'speech_muted', True))
            detail = 'saída de voz habilitada; som não testado por esta inspeção'
        elif key == 'local_model':
            connected = (str(get_env('LOCAL_DIALOGUE_ENABLED', 'false')).lower() == 'true'
                         and str(get_env('DIALOGUE_ENABLED', 'true')).lower() == 'true'
                         and get_runtime_path('.runtime/local-dialogue/install.json').is_file())
            detail = 'instalação detectada; o estado do runtime é informado separadamente'
        items.append(dict(id=key, label=label, implemented=implemented, connected=connected, detail=detail, example=example))
    voice = getattr(getattr(process, 'parent', None), 'voice', None)
    speech_input = dict(selected=get_env('STT_ENGINE', 'vosk'),
                        active=getattr(voice, 'active_engine', None) or ('whisper.cpp' if hasattr(voice, 'backend') else 'vosk' if voice else None),
                        status=getattr(voice, 'status', 'not_connected'),
                        fallback_enabled=get_env('STT_FALLBACK_ENABLED', 'false') == 'true')
    return dict(capabilities=items, model=runtime_status(), speech_input=speech_input,
                limits=['o gerador não executa comandos', 'sem autoedição do código',
                        'inspeção estrutural não comprova funcionamento de um recurso',
                        'sem acesso irrestrito a arquivos ou segredos'])


def prompt_snapshot(process):
    data = snapshot(process)
    return dict(capabilities=[dict(id=i['id'], implemented=i['implemented'], connected=i['connected']) for i in data['capabilities']],
                model=data['model'], speech_input=data['speech_input'], limits=data['limits'])


def reply(text, process):
    clean = ''.join(c for c in unicodedata.normalize('NFKD', text.lower()) if not unicodedata.combining(c))
    clean = re.sub(r'[^a-z0-9 ]', ' ', clean).strip()
    version_query = (re.search(r'\b(?:your version|sua versao)\b', clean)
                     or re.search(r'\bwhat version (?:are you|is maya)\b', clean)
                     or (re.search(r'\bqual.*versao\b', clean) and re.search(r'\b(?:sua|maya|voce)\b', clean)))
    if version_query:
        from helpers.version import get_version_display
        version = get_version_display()
        return f'my application version is {version}.' if str(get_env('LANGUAGE', 'en')).startswith('en') else f'minha versão da aplicação é {version}.'
    capability_query = bool(re.search(r'\b(?:seus poderes|suas capacidades|suas funcoes|seus limites|suas limitacoes|o que voce (?:pode|consegue|sabe) fazer|o que pode fazer|quais poderes)\b', clean))
    code_query = bool(re.search(r'\b(?:seu codigo|proprio codigo|sua arquitetura|como voce funciona|onde fica (?:sua|seu)|quais arquivos)\b', clean))
    status_query = clean in {'status do modelo local', 'status do seu motor', 'diagnostico da maya', 'status da maya', 'status da voz', 'status do motor de voz'}
    if not (capability_query or code_query or status_query):
        return None
    data = snapshot(process)
    if status_query:
        if clean in {'status da voz', 'status do motor de voz'}:
            voice = data['speech_input']
            return f"reconhecimento selecionado: {voice['selected']}; motor em uso: {voice['active'] or 'nenhum conectado'}; estado: {voice['status']}. reserva automática: {'habilitada' if voice['fallback_enabled'] else 'desabilitada'}."
        model = data['model']
        connected = next(i['connected'] for i in data['capabilities'] if i['id'] == 'local_model')
        states = {'stopped': 'parado, carrega quando necessário', 'loading': 'carregando',
                  'ready': 'a última solicitação terminou com sucesso', 'fallback': 'indisponível, usando alternativa nativa'}
        count = len(process.memory.state.get('dialogue', {}).get('episodes', [])) if process.memory else 0
        return f"modelo local {'habilitado' if connected else 'desabilitado ou não instalado'}; runtime: {states.get(model['state'], model['state'])}. tenho {count} trocas no histórico episódico. isso descreve meu funcionamento, não consciência ou sentimentos."
    if code_query:
        aliases = {'voz': 'input/voice.py', 'microfone': 'input/voice.py', 'stt': 'input/voice.py',
                   'fala': 'output/speaker.py', 'tts': 'output/speaker.py', 'memoria': 'core/memory.py',
                   'modelo': 'helpers/local_dialogue.py', 'personalidade': 'core/local_conversation.py',
                   'poderes': 'helpers/self_knowledge.py', 'funcoes': 'core/process.py'}
        selected = next((path for word, path in aliases.items() if re.search(r'\b'+word+r'\b', clean)), None)
        sources = [selected] if selected else ['core/process.py', 'core/dialogue.py', 'core/local_conversation.py', 'helpers/local_dialogue.py', 'core/memory.py']
        pieces = []
        for path in sources:
            index = inspect_source(path)
            symbols = [f'{cls}.{name} (linha {line})' for cls, methods in index.items() for name, line in methods.items()]
            pieces.append(f"{path}: " + (', '.join(symbols[:8]) if symbols else 'fonte ou métodos de classe não disponíveis nesta instalação'))
        return 'inspecionei as definições dos meus arquivos locais, sem executar esse código:\n' + '\n'.join(pieces) + '\nisso é um mapa estrutural; não significa que eu possa editar meu código sozinha.'
    available = [i for i in data['capabilities'] if i['implemented'] and i['connected']]
    absent = [i['label'] for i in data['capabilities'] if not (i['implemented'] and i['connected'])]
    result = 'nesta sessão tenho componentes conectados para: ' + ('; '.join(i['label'] for i in available) or 'nenhum recurso confirmado') + '.'
    result += '\nexemplos de pedidos: ' + '; '.join(i['example'] for i in available[:5]) + '.'
    if absent:
        result += '\nsem disponibilidade confirmada agora: ' + '; '.join(absent) + '.'
    return result + '\ncomponente conectado não garante sucesso: apps, permissões e internet podem limitar a execução. o modelo conversa; ações passam pelos executores. não me autoedito nem ganho funções só por descrever uma ideia.'
