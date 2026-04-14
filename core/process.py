import json
import re
import random
import datetime
import difflib
import unicodedata
from core import vocabulary_manager
from core.knowledge_base import KnowledgeBase
from core.memory import Memory
from helpers.config import get_env, get_path

RESPONSES_PATH = get_path("RESPONSES_PATH", "data/responses.json")

class Assistant:
    def __init__(self):
        self.memory = Memory()

    def process_input(self, text):
        text_lower = text.lower().strip()

        self.memory.add_message("user", text)

        patterns = self.detect_patterns(text_lower)
        self.apply_memory_updates(patterns, text)
        response = self.generate_response(text, patterns)

        self.memory.add_message("assistant", response)
        return response

class Process:
    def __init__(self):
        self.parent = None
        self.weights_amount = 128
        self.memory = None
        self.app_launcher = None
        self.dev_assistant = None
        self.web_assistant = None
        self.spotify_assistant = None
        self.knowledge_base = KnowledgeBase()

        self.DEBUG_MODE = get_env("DEBUG_MODE", "false").lower() == "true"
        self.UI_MODE = get_env("UI_MODE", "maya")
        self.LANGUAGE = get_env("LANGUAGE", "en")
        self.responses = self.load_responses()

    @staticmethod
    def _choose(options):
        return random.choice(options)

    def load_responses(self):
        with open(RESPONSES_PATH, "r", encoding="utf-8") as file:
            return json.load(file)

    def pick_response(self, key, **values):
        response_key = key
        if str(self.LANGUAGE).lower().startswith("pt") and f"{key}_pt" in self.responses:
            response_key = f"{key}_pt"
        templates = self.responses.get(response_key, [])
        if not templates:
            raise KeyError(f"missing response templates for key: {key}")
        return self._choose(templates).format(**values)

    @staticmethod
    def _first_or_none(items):
        return items[0] if items else None

    def _build_memory_hint(self, preferences, known_facts):
        preference = self._first_or_none(preferences)
        fact = self._first_or_none(known_facts)
        is_pt = str(self.LANGUAGE).lower().startswith("pt")

        if preference and fact:
            if is_pt:
                return f" eu lembro que voce gosta de {preference} e que {fact}."
            return f" i remember that you like {preference}, and that {fact}."

        if preference:
            if is_pt:
                return f" eu lembro que voce gosta de {preference}."
            return f" i remember that you like {preference}."

        if fact:
            if is_pt:
                return f" eu lembro que {fact}."
            return f" i remember that {fact}."

        return ""

    def _find_previous_user_message(self, current_text):
        if not self.memory:
            return None

        recent_messages = self.memory.get_recent_messages(8)
        for message in reversed(recent_messages[:-1]):
            if message.get("role") == "user":
                content = message.get("content", "").strip()
                if content and content != current_text.strip():
                    return content
        return None

    def _topic_follow_up(self, last_topic, preferences, known_facts, user_name):
        if last_topic == "preferences":
            if preferences:
                return self.pick_response("follow_up_preferences", preferences=", ".join(preferences))
            return self.pick_response("follow_up_preferences_empty")

        if last_topic == "facts":
            if known_facts:
                return self.pick_response("follow_up_facts", facts="; ".join(known_facts[:3]))
            return self.pick_response("follow_up_facts_empty")

        if last_topic == "name":
            if user_name:
                return self.pick_response("follow_up_name", user_name=user_name)
            return self.pick_response("follow_up_name_empty")

        return self.pick_response("follow_up_generic")

    def _build_personal_fallback(self, user_name, preferences, known_facts):
        if user_name:
            return self.pick_response(
                "fallback_known_name",
                user_name=user_name,
                memory_hint=self._build_memory_hint(preferences, known_facts),
            )

        if preferences or known_facts:
            return self.pick_response(
                "fallback_known_memory",
                memory_hint=self._build_memory_hint(preferences, known_facts),
            )

        return self.pick_response("fallback_default")

    def _personalized_response(self, known_key, unknown_key, user_name=None, **values):
        if user_name:
            return self.pick_response(known_key, user_name=user_name, **values)
        return self.pick_response(unknown_key, **values)

    @staticmethod
    def get_current_time_text():
        return datetime.datetime.now().strftime("%H:%M")

    @staticmethod
    def get_current_date_text():
        return datetime.datetime.now().strftime("%B %d, %Y")

    @staticmethod
    def is_knowledge_request(text_lower):
        knowledge_starters = (
            "what's ",
            "whats ",
            "what is ",
            "who is ",
            "where is ",
            "when is ",
            "why is ",
            "how does ",
            "how do ",
            "explain ",
            "define ",
            "translate ",
            "meaning of ",
            "tell me about ",
            "summarize ",
        )
        return text_lower.startswith(knowledge_starters)

    @staticmethod
    def contains_any(text, phrases):
        normalized_text = Process.normalize_text(text)
        return any(Process.contains_phrase(normalized_text, phrase) for phrase in phrases)

    @staticmethod
    def starts_with_any(text, phrases):
        normalized_text = Process.normalize_text(text)
        return any(normalized_text.startswith(Process.normalize_text(phrase)) for phrase in phrases)

    @staticmethod
    def normalize_text(text):
        normalized = unicodedata.normalize("NFKD", (text or "").strip().lower())
        normalized = "".join(char for char in normalized if not unicodedata.combining(char))
        normalized = normalized.replace("-", " ").replace("_", " ")
        normalized = re.sub(r"[^a-z0-9\s']+", " ", normalized)
        return " ".join(normalized.split())

    @staticmethod
    def _token_similarity(a, b):
        if not a or not b:
            return 0.0
        return difflib.SequenceMatcher(None, a, b).ratio()

    @classmethod
    def _tokens_match(cls, actual, expected):
        if actual == expected:
            return True
        if abs(len(actual) - len(expected)) > 2:
            return False
        threshold = 0.84 if max(len(actual), len(expected)) >= 5 else 0.9
        return cls._token_similarity(actual, expected) >= threshold

    @classmethod
    def contains_phrase(cls, text, phrase):
        normalized_text = cls.normalize_text(text)
        normalized_phrase = cls.normalize_text(phrase)
        if not normalized_text or not normalized_phrase:
            return False
        if normalized_phrase in normalized_text:
            return True

        text_tokens = cls.tokenize(normalized_text)
        phrase_tokens = cls.tokenize(normalized_phrase)
        if not text_tokens or not phrase_tokens or len(phrase_tokens) > len(text_tokens):
            return False

        for index in range(len(text_tokens) - len(phrase_tokens) + 1):
            window = text_tokens[index:index + len(phrase_tokens)]
            if all(cls._tokens_match(actual, expected) for actual, expected in zip(window, phrase_tokens)):
                return True
        return False

    @staticmethod
    def strip_polite_prefixes(text):
        return re.sub(
            r"^(?:please|hey maya|hi maya|hello maya|oi maya|ola maya|olá maya|maya|can you|could you|would you)\s+",
            "",
            text.strip(),
            flags=re.IGNORECASE,
        )

    @staticmethod
    def extract_browser_clause(text):
        known_browser_aliases = {
            "firefox",
            "chrome",
            "edge",
            "opera",
            "brave",
            "browser",
            "internet browser",
        }
        stripped = text.strip()
        lowered = stripped.lower()

        for browser_alias in sorted(known_browser_aliases, key=len, reverse=True):
            for connector in (" using ", " in ", " on ", " no ", " na ", " em "):
                suffix = f"{connector}{browser_alias}"
                if lowered.endswith(suffix):
                    return stripped[: -len(suffix)].strip(), browser_alias

        return stripped, None

    def parse_natural_media_action(self, text_lower):
        cleaned = self.strip_polite_prefixes(text_lower)
        without_browser, browser_alias = self.extract_browser_clause(cleaned)
        tokens = self.tokenize(without_browser)
        token_set = set(tokens)

        launch_like_match = re.match(
            r"^(?:open|launch|start|run|abre|abrir|inicia|iniciar|roda|rodar)\s+([a-zA-Z0-9 .+-]+?)(?:\s+(?:for me|please|pra mim|por favor))?$",
            without_browser,
            flags=re.IGNORECASE,
        )
        if launch_like_match and self.app_launcher:
            launch_target = launch_like_match.group(1).strip()
            if self.app_launcher.resolve_alias(launch_target):
                return None

        if not token_set.intersection({"play", "open", "search", "find", "show", "toca", "toque", "tocar", "bota", "coloca", "reproduz", "reproduzir", "abre", "abrir"}):
            return None

        if "youtube music" in without_browser:
            query = re.sub(r"\s+on\s+youtube music$", "", without_browser, flags=re.IGNORECASE).strip()
            query = re.sub(r"^(?:play|open|search|find|show|toca|toque|abre|abrir|procura|pesquisa|mostra)\s+", "", query, flags=re.IGNORECASE).strip()
            query = re.sub(r"^(?:some|a|uma|um)\s+", "", query, flags=re.IGNORECASE).strip()
            if query:
                return {
                    "kind": "media",
                    "service": "youtube_music",
                    "query": query,
                    "browser_alias": browser_alias,
                }

        if self.spotify_assistant:
            spotify_request = self.spotify_assistant.parse_request(without_browser)
            if spotify_request:
                spotify_request["kind"] = "spotify"
                return spotify_request

        video_tokens = {"video", "videos", "clip", "clips"}
        image_tokens = {"image", "images", "picture", "pictures", "photo", "photos", "pics"}

        if token_set.intersection(video_tokens):
            query = re.sub(r"^(?:play|open|search|find|show(?: me)?|toca|toque|abre|abrir|procura|pesquisa|mostra)\s+", "", without_browser, flags=re.IGNORECASE).strip()
            query = re.sub(r"^(?:some|a|uma|um)\s+", "", query, flags=re.IGNORECASE).strip()
            query = re.sub(r"^(?:video|videos|clip|clips)\b", "", query, flags=re.IGNORECASE).strip()
            query = re.sub(r"\s+(?:video|videos|clip|clips)\b", "", query, flags=re.IGNORECASE).strip()
            query = re.sub(r"^(?:of|for|about|de|sobre)\s+", "", query, flags=re.IGNORECASE).strip()
            query = re.sub(r"\s+on\s+youtube$", "", query, flags=re.IGNORECASE).strip()
            if query:
                return {
                    "kind": "web",
                    "mode": "video",
                    "query": query,
                    "browser_alias": browser_alias,
                }

        if token_set.intersection(image_tokens):
            query = re.sub(r"^(?:open|search|find|show(?: me)?|look up|abre|abrir|procura|pesquisa|mostra)\s+", "", without_browser, flags=re.IGNORECASE).strip()
            query = re.sub(r"^(?:some|a|uma|um)\s+", "", query, flags=re.IGNORECASE).strip()
            query = re.sub(r"^(?:image|images|picture|pictures|photo|photos|pics)\b", "", query, flags=re.IGNORECASE).strip()
            query = re.sub(r"\s+(?:image|images|picture|pictures|photo|photos|pics)\b", "", query, flags=re.IGNORECASE).strip()
            query = re.sub(r"^(?:of|for|de)\s+", "", query, flags=re.IGNORECASE).strip()
            if query:
                return {
                    "kind": "web",
                    "mode": "image",
                    "query": query,
                    "browser_alias": browser_alias,
                }

        return None

    def parse_natural_site_action(self, text_lower):
        cleaned = self.strip_polite_prefixes(text_lower)
        without_browser, browser_alias = self.extract_browser_clause(cleaned)
        match = re.match(r"^(?:open|go to|visit|abre|abrir|acessa|acessar|visita|visitar|ir para|vai para)\s+(.+)$", without_browser, flags=re.IGNORECASE)
        if not match:
            return None

        target = match.group(1).strip()
        explicit_site = bool(re.match(r"^(?:the\s+)?(?:site|website)\s+", target, flags=re.IGNORECASE))
        target = re.sub(r"^(?:the\s+)?(?:site|website)\s+", "", target, flags=re.IGNORECASE).strip()
        if not target:
            return None

        if not browser_alias and not explicit_site and "." not in target and not re.match(r"^https?://", target, flags=re.IGNORECASE):
            return None

        if any(token in target for token in [" video", " image", " playlist", "youtube music"]):
            return None

        if "spotify" in target and not browser_alias:
            return None

        if re.search(r"\b(?:project|app)\b", target):
            return None

        return {
            "mode": "site",
            "query": target,
            "browser_alias": browser_alias,
        }

    def parse_hosted_app_action(self, text_lower):
        if not self.app_launcher:
            return None

        cleaned = self.strip_polite_prefixes(text_lower)
        cleaned = re.sub(r"[.!?,;:]+$", "", cleaned).strip()
        match = re.match(
            r"^(?:open|launch|start|run|play|abre|abrir|inicia|iniciar|roda|rodar|joga|jogar)\s+(.+?)\s+(?:on|in|using|via|no|na|em|pelo|pela)\s+([a-zA-Z0-9 .+-]+?)(?:\s+(?:for me|please|pra mim|por favor))?$",
            cleaned,
            flags=re.IGNORECASE,
        )
        if not match:
            return None

        target_alias = match.group(1).strip()
        host_alias = match.group(2).strip()
        host_key = self.app_launcher.resolve_alias(host_alias)
        if not host_key:
            return None

        if host_key in {"firefox", "chrome", "edge", "opera", "brave"}:
            blocked_terms = (" video", " videos", " image", " images", " playlist", " youtube music")
            lowered_target = f" {target_alias.lower()} "
            if not any(term in lowered_target for term in blocked_terms):
                return {
                    "kind": "web",
                    "mode": "site",
                    "query": target_alias,
                    "browser_alias": host_alias,
                }

        subapp_key = self.app_launcher.resolve_subapp_alias(host_key, target_alias)
        if subapp_key or host_key == "steam":
            return {
                "kind": "subapp",
                "host_alias": host_alias,
                "host_key": host_key,
                "subapp_alias": target_alias,
                "subapp_key": subapp_key,
            }

        return None

    @staticmethod
    def normalize_move_position(raw_position):
        if not raw_position:
            return None

        normalized = raw_position.strip().lower()
        normalized = normalized.replace("-", " ").replace("_", " ")
        normalized = re.sub(r"[.!?,;:]+$", "", normalized).strip()
        normalized = re.sub(r"^(?:the\s+)?(?:position\s+)?", "", normalized, flags=re.IGNORECASE).strip()
        normalized = re.sub(r"\s+(?:please|now)$", "", normalized, flags=re.IGNORECASE).strip()

        mapping = {
            "top left": "top_left",
            "upper left": "top_left",
            "canto superior esquerdo": "top_left",
            "top": "top",
            "top center": "top",
            "top middle": "top",
            "top right": "top_right",
            "upper right": "top_right",
            "canto superior direito": "top_right",
            "left": "left",
            "esquerda": "left",
            "center": "center",
            "middle": "center",
            "centro": "center",
            "right": "right",
            "direita": "right",
            "bottom left": "bottom_left",
            "lower left": "bottom_left",
            "canto inferior esquerdo": "bottom_left",
            "bottom": "bottom",
            "bottom center": "bottom",
            "bottom right": "bottom_right",
            "lower right": "bottom_right",
            "canto inferior direito": "bottom_right",
        }
        return mapping.get(normalized)

    def parse_window_move_request(self, text_lower):
        text_lower = re.sub(r"[.!?,;:]+$", "", text_lower.strip()).strip()

        patterns = [
            r"(?:move|go|put|place|send)\s+(?:maya|yourself|the window)?\s*(?:to\s+)?(.+?)\s+(?:on|to)\s+(?:monitor|display|screen)\s+(\d+)$",
            r"(?:vai|va|fica|move)\s+(?:a maya|a janela|você)?\s*(?:para\s+)?(.+?)\s+(?:no|na)\s+(?:monitor|tela|display)\s+(\d+)$",
        ]

        for pattern in patterns:
            match = re.search(pattern, text_lower, flags=re.IGNORECASE)
            if not match:
                continue

            position = self.normalize_move_position(match.group(1))
            if not position:
                continue

            monitor = int(match.group(2))
            return {
                "position": position,
                "monitor": max(1, monitor),
                "monitor_text": f"monitor {max(1, monitor)}",
            }

        monitor_only_patterns = [
            r"(?:move|go|send)\s+(?:maya|yourself|the window)?\s*(?:to\s+)?(?:monitor|display|screen)\s+(\d+)$",
            r"(?:vai|va|move)\s+(?:a maya|a janela|você)?\s*(?:para\s+)?(?:o\s+)?(?:monitor|display|tela)\s+(\d+)$",
        ]

        for pattern in monitor_only_patterns:
            match = re.search(pattern, text_lower, flags=re.IGNORECASE)
            if not match:
                continue

            monitor = int(match.group(1))
            return {
                "position": "current",
                "monitor": max(1, monitor),
                "monitor_text": f"monitor {max(1, monitor)}",
            }

        relative_monitor_patterns = [
            r"(?:move|go|send)\s+(?:maya|yourself|the window)?\s*(?:to\s+)?(?:the\s+)?(?:(other|next|another)\s+(?:monitor|display|screen))$",
            r"(?:move|go|send)\s+(?:maya|yourself|the window)?\s*(?:to\s+)?(.+?)\s+(?:on|to)\s+(?:the\s+)?(?:(other|next|another)\s+(?:monitor|display|screen))$",
            r"(?:vai|va|move)\s+(?:a maya|a janela|você)?\s*(?:para\s+)?(?:o\s+)?(?:(outro|próximo|proximo)\s+(?:monitor|display|tela))$",
            r"(?:vai|va|move)\s+(?:a maya|a janela|você)?\s*(?:para\s+)?(.+?)\s+(?:no|na)\s+(?:o\s+)?(?:(outro|próximo|proximo)\s+(?:monitor|display|tela))$",
        ]

        for pattern in relative_monitor_patterns:
            match = re.search(pattern, text_lower, flags=re.IGNORECASE)
            if not match:
                continue

            raw_position = match.group(1) if match.lastindex and match.lastindex > 1 else None
            if raw_position and raw_position.lower() in {"other", "next", "another", "outro", "próximo", "proximo"}:
                raw_position = None

            position = self.normalize_move_position(raw_position) if raw_position else None
            return {
                "position": position or "current",
                "monitor": "other",
                "monitor_text": "the other monitor",
            }

        same_monitor_patterns = [
            r"(?:move|go|put|place|send)\s+(?:maya|yourself|the window)?\s*(?:to\s+)?(.+)$",
            r"(?:vai|va|fica|move)\s+(?:a maya|a janela|você)?\s*(?:para\s+)?(.+)$",
        ]

        for pattern in same_monitor_patterns:
            match = re.search(pattern, text_lower, flags=re.IGNORECASE)
            if not match:
                continue

            raw_position = match.group(1).strip()
            position = self.normalize_move_position(raw_position)
            if not position:
                continue

            return {
                "position": position,
                "monitor": "current",
                "monitor_text": "this monitor",
            }

        return None

    @staticmethod
    def parse_scale_request(text_lower):
        normalized = text_lower.strip().lower()

        fixed_aliases = {
            "make yourself smaller": {"mode": "decrease", "value": 0.2},
            "make yourself bigger": {"mode": "increase", "value": 0.2},
            "make yourself larger": {"mode": "increase", "value": 0.2},
            "scale down": {"mode": "decrease", "value": 0.2},
            "scale up": {"mode": "increase", "value": 0.2},
            "be smaller": {"mode": "decrease", "value": 0.2},
            "be bigger": {"mode": "increase", "value": 0.2},
            "fica menor": {"mode": "decrease", "value": 0.2},
            "fica maior": {"mode": "increase", "value": 0.2},
            "diminui seu tamanho": {"mode": "decrease", "value": 0.2},
            "aumenta seu tamanho": {"mode": "increase", "value": 0.2},
            "reset your scale": {"mode": "set", "value": 1.0},
            "reset scale": {"mode": "set", "value": 1.0},
            "reset your size": {"mode": "set", "value": 1.0},
        }

        if normalized in fixed_aliases:
            return fixed_aliases[normalized]

        patterns = [
            (r"(?:set|change|make)\s+(?:your|the|maya'?s)\s+(?:scale|size)\s+(?:to|at|in)\s+(\d+(?:\.\d+)?)$", "set"),
            (r"(?:reduce|decrease|shrink|lower)\s+(?:your|the|maya'?s)\s+(?:scale|size)\s+(?:to|at|in)\s+(\d+(?:\.\d+)?)$", "set"),
            (r"(?:increase|grow|enlarge|raise)\s+(?:your|the|maya'?s)\s+(?:scale|size)\s+(?:to|at|in)\s+(\d+(?:\.\d+)?)$", "set"),
            (r"(?:reduce|decrease|shrink|lower)\s+(?:your|the|maya'?s)\s+(?:scale|size)\s+by\s+(\d+(?:\.\d+)?)$", "decrease"),
            (r"(?:increase|grow|enlarge|raise)\s+(?:your|the|maya'?s)\s+(?:scale|size)\s+by\s+(\d+(?:\.\d+)?)$", "increase"),
            (r"(?:scale|size)\s+(?:to|at|in)\s+(\d+(?:\.\d+)?)$", "set"),
            (r"(?:make|set)\s+yourself\s+(?:to\s+)?(\d+(?:\.\d+)?)\s*(?:x|scale)?$", "set"),
            (r"(?:make|set)\s+yourself\s+(\d+(?:\.\d+)?)\s*(?:x|times)?\s+(?:bigger|larger)$", "set"),
            (r"(?:make|set)\s+yourself\s+(\d+(?:\.\d+)?)\s*(?:x|times)?\s+(?:smaller)$", "set_inverse"),
            (r"(?:be|become)\s+(\d+(?:\.\d+)?)\s*(?:x|times)?\s+(?:bigger|larger)$", "set"),
            (r"(?:be|become)\s+(\d+(?:\.\d+)?)\s*(?:x|times)?\s+(?:smaller)$", "set_inverse"),
            (r"(?:half|halve)\s+(?:your\s+)?(?:scale|size)$", "set", 0.5),
            (r"(?:double)\s+(?:your\s+)?(?:scale|size)$", "set", 2.0),
            (r"(?:deixa|faz)\s+(?:você|voce|a maya)?\s*(?:menor|pequena)$", "decrease"),
            (r"(?:deixa|faz)\s+(?:você|voce|a maya)?\s*(?:maior|grande)$", "increase"),
            (r"(?:reduz|diminui)\s+(?:sua|o seu)\s+(?:escala|tamanho)\s+em\s+(\d+(?:\.\d+)?)$", "decrease"),
            (r"(?:aumenta)\s+(?:sua|o seu)\s+(?:escala|tamanho)\s+em\s+(\d+(?:\.\d+)?)$", "increase"),
            (r"(?:reduz|diminui)\s+(?:sua|o seu)\s+(?:escala|tamanho)\s+para\s+(\d+(?:\.\d+)?)$", "set"),
            (r"(?:aumenta)\s+(?:sua|o seu)\s+(?:escala|tamanho)\s+para\s+(\d+(?:\.\d+)?)$", "set"),
        ]

        for entry in patterns:
            pattern = entry[0]
            mode = entry[1]
            default_value = entry[2] if len(entry) > 2 else None
            match = re.search(pattern, text_lower, flags=re.IGNORECASE)
            if not match:
                continue

            value = default_value if default_value is not None else float(match.group(1))
            if mode == "set_inverse":
                value = 1.0 / value if value else 1.0
                mode = "set"
            return {
                "mode": mode,
                "value": round(value, 3),
            }

        percentage_match = re.search(
            r"(?:set|make|become|reduce|increase|scale)\s+(?:yourself|your|the)?\s*(?:scale|size)?\s*(?:to|by)?\s*(\d+(?:\.\d+)?)\s*%$",
            text_lower,
            flags=re.IGNORECASE,
        )
        if percentage_match:
            return {
                "mode": "set",
                "value": round(float(percentage_match.group(1)) / 100.0, 3),
            }

        return None

    @staticmethod
    def parse_dev_workspace_request(text_lower):
        normalized = Process.normalize_text(Process.strip_polite_prefixes(text_lower))
        intent_phrases = [
            "enter dev mode",
            "start dev mode",
            "open dev mode",
            "enable dev mode",
            "activate dev mode",
            "go to dev mode",
            "switch to dev mode",
            "dev mode",
            "modo dev",
            "entra no modo dev",
            "ativa modo dev",
            "abre modo dev",
            "vai pro modo dev",
        ]
        if any(Process.contains_phrase(normalized, phrase) for phrase in intent_phrases):
            return {
                "spotify_query": "pique anos 80",
                "layout": "default_dual_monitor",
            }
        patterns = [
            r"(?:enter|start|open|enable|activate)\s+(?:the\s+)?(?:dev|developer)\s+mode(?:\s+(?:now|please))?$",
            r"(?:go|switch)\s+(?:to\s+)?(?:dev|developer)\s+mode(?:\s+(?:now|please))?$",
            r"(?:dev|developer)\s+mode(?:\s+(?:now|please))?$",
            r"(?:modo\s+dev|modo\s+developer)(?:\s+(?:agora|por favor))?$",
            r"(?:entra|entre|ativa|ative|abre|abrir)\s+(?:o\s+)?(?:modo\s+dev|modo\s+developer)(?:\s+(?:agora|por favor))?$",
            r"(?:vai|ir)\s+(?:pro|para o)\s+(?:modo\s+dev|modo\s+developer)(?:\s+(?:agora|por favor))?$",
        ]
        if any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in patterns):
            return {
                "spotify_query": "pique anos 80",
                "layout": "default_dual_monitor",
            }
        return None

    @staticmethod
    def parse_dev_workspace_exit_request(text_lower):
        normalized = Process.normalize_text(Process.strip_polite_prefixes(text_lower))
        intent_phrases = [
            "exit dev mode",
            "leave dev mode",
            "close dev mode",
            "disable dev mode",
            "stop dev mode",
            "switch out of dev mode",
            "sai do modo dev",
            "fecha modo dev",
            "desativa modo dev",
        ]
        if any(Process.contains_phrase(normalized, phrase) for phrase in intent_phrases):
            return True
        patterns = [
            r"(?:exit|leave|close|disable|stop)\s+(?:the\s+)?(?:dev|developer)\s+mode(?:\s+(?:now|please))?$",
            r"(?:go|switch)\s+out\s+of\s+(?:dev|developer)\s+mode(?:\s+(?:now|please))?$",
            r"(?:sai|sair|fecha|fechar|desativa|desativar)\s+(?:do|o\s+)?(?:modo\s+dev|modo\s+developer)(?:\s+(?:agora|por favor))?$",
        ]
        return any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in patterns)

    @staticmethod
    def parse_thoughtful_workspace_request(text_lower):
        normalized = Process.normalize_text(Process.strip_polite_prefixes(text_lower))
        intent_phrases = [
            "enter thoughtful mode",
            "start thoughtful mode",
            "open thoughtful mode",
            "activate thoughtful mode",
            "thinking mode",
            "thoughtful mode",
            "modo pensativo",
            "entra no modo pensativo",
            "ativa modo pensativo",
            "abre modo pensativo",
        ]
        if any(Process.contains_phrase(normalized, phrase) for phrase in intent_phrases):
            return True
        patterns = [
            r"(?:enter|start|open|enable|activate)\s+(?:the\s+)?(?:thoughtful|thinking)\s+mode(?:\s+(?:now|please))?$",
            r"(?:thoughtful|thinking)\s+mode(?:\s+(?:now|please))?$",
            r"(?:modo\s+pensativo|modo\s+pensando)(?:\s+(?:agora|por favor))?$",
            r"(?:entra|entre|ativa|ative|abre|abrir)\s+(?:o\s+)?(?:modo\s+pensativo|modo\s+pensando)(?:\s+(?:agora|por favor))?$",
        ]
        return any(re.search(pattern, normalized, flags=re.IGNORECASE) for pattern in patterns)

    @staticmethod
    def parse_window_showcase_request(text_lower):
        normalized = Process.normalize_text(text_lower)

        close_phrases = [
            "close the window showcase",
            "hide the window showcase",
            "close window showcase",
            "hide window showcase",
            "close the window disco",
            "hide the window disco",
            "fechar carrossel de janelas",
            "fecha o carrossel de janelas",
            "esconde o carrossel de janelas",
            "fecha o disco de janelas",
            "esconde o disco de janelas",
        ]
        if any(Process.contains_phrase(normalized, phrase) for phrase in close_phrases):
            return {"action": "close"}

        rotate_left_patterns = [
            r"(?:rotate|spin|turn|move)\s+(?:the\s+)?(?:window\s+)?(?:showcase|carousel|disco)\s+(?:to\s+)?(?:the\s+)?left$",
            r"(?:previous|back)\s+window(?:\s+in\s+(?:the\s+)?(?:showcase|carousel|disco))?$",
            r"(?:gira|roda|move)\s+(?:o\s+)?(?:carrossel|disco|varal)\s+de\s+janelas\s+(?:para\s+a\s+)?esquerda$",
            r"(?:janela|card)\s+anterior(?:\s+no\s+(?:carrossel|disco|varal))?$",
        ]
        for pattern in rotate_left_patterns:
            if re.search(pattern, normalized, flags=re.IGNORECASE):
                return {"action": "rotate", "step": -1}

        rotate_right_patterns = [
            r"(?:rotate|spin|turn|move)\s+(?:the\s+)?(?:window\s+)?(?:showcase|carousel|disco)\s+(?:to\s+)?(?:the\s+)?right$",
            r"(?:next)\s+window(?:\s+in\s+(?:the\s+)?(?:showcase|carousel|disco))?$",
            r"(?:gira|roda|move)\s+(?:o\s+)?(?:carrossel|disco|varal)\s+de\s+janelas\s+(?:para\s+a\s+)?direita$",
            r"(?:proxima|próxima)\s+(?:janela|card)(?:\s+no\s+(?:carrossel|disco|varal))?$",
        ]
        for pattern in rotate_right_patterns:
            if re.search(pattern, normalized, flags=re.IGNORECASE):
                return {"action": "rotate", "step": 1}

        open_phrases = [
            "show windows",
            "show my windows",
            "show open windows",
            "show the windows",
            "open the window showcase",
            "open window showcase",
            "window showcase",
            "window carousel",
            "window disco",
            "mostra as janelas",
            "mostra minhas janelas",
            "mostra as janelas abertas",
            "abre o carrossel de janelas",
            "abre o disco de janelas",
            "carrossel de janelas",
            "disco de janelas",
            "varal de janelas",
        ]
        if any(Process.contains_phrase(normalized, phrase) for phrase in open_phrases):
            return {"action": "open"}

        if re.search(r"(?:show|open|make)\s+.*(?:carousel|showcase|disco|varal).*(?:window|windows|janelas)$", normalized, flags=re.IGNORECASE):
            return {"action": "open"}

        if re.search(r"(?:quero|faz|faca|faz um|faz uma)\s+.*(?:disco|carrossel|varal).*(?:janela|janelas)$", normalized, flags=re.IGNORECASE):
            return {"action": "open"}

        return None

    def parse_natural_status_request(self, text_lower):
        cleaned = self.strip_polite_prefixes(text_lower)
        token_set = set(self.tokenize(cleaned))
        status_words = {"good", "okay", "ok", "fine", "alright", "well"}
        if {"are", "you"}.issubset(token_set) and token_set.intersection(status_words):
            return True
        if self.contains_any(cleaned, ["you good", "you okay", "you alright", "everything okay", "voce ta bem", "você ta bem", "voce esta bem", "você está bem", "ta tudo bem", "tá tudo bem"]):
            return True
        return False

    def parse_natural_capabilities_request(self, text_lower):
        cleaned = self.strip_polite_prefixes(text_lower)
        if self.contains_any(cleaned, ["what can you do", "your capabilities", "help me", "o que voce pode fazer", "o que você pode fazer", "quais suas capacidades", "me ajuda"]):
            return True
        if self.starts_with_any(cleaned, ["can you ", "could you "]) and "?" not in cleaned:
            return False
        return cleaned in {"help", "capabilities"}

    @staticmethod
    def is_useful_summary(summary):
        if not summary:
            return False

        clean = summary.strip()
        normalized = clean.lower().strip(" .!?")
        blocked = {"yes", "no", "ok", "okay", "maybe", "i don't know"}

        if normalized in blocked:
            return False

        if len(clean) < 20:
            return False

        if len(clean.split()) < 4:
            return False

        return True

    def auto_learn_answer(self, question):
        if not self.web_assistant:
            return None

        summary = self.web_assistant.get_text_summary(question)
        return self.store_learned_answer(question, summary)

    def store_learned_answer(self, question, summary):
        if not self.is_useful_summary(summary):
            return None

        self.knowledge_base.teach_answer(question, summary)
        if self.memory:
            self.memory.clear_pending_learning()
            self.memory.set_last_topic("learning")

        return summary

    def generate_response(self, text, patterns):
        user_name = self.memory.get_user_name() if self.memory else None
        preferences = self.memory.get_preferences() if self.memory else []
        known_facts = self.memory.get_known_facts() if self.memory else []
        mood = self.memory.get_mood() if self.memory else "neutral"
        last_topic = self.memory.get_last_topic() if self.memory else None
        pending_learning = self.memory.get_pending_learning() if self.memory else None
        memory_hint = self._build_memory_hint(preferences, known_facts)
        previous_user_message = self._find_previous_user_message(text)
        learned_answer = self.knowledge_base.get_answer(text)

        if patterns["cancel_learning"]:
            if self.memory and pending_learning:
                self.memory.clear_pending_learning()
                return self.pick_response("learning_cancelled")

        if learned_answer:
            return learned_answer

        if patterns["asks_name"]:
            return self.pick_response("asks_name")

        if patterns["asks_creator"]:
            return self.pick_response("asks_creator")

        if patterns["asks_age"]:
            return self.pick_response("asks_age")

        if patterns["asks_origin"]:
            return self.pick_response("asks_origin")

        if patterns["asks_language"]:
            return self.pick_response("asks_language")

        if patterns["asks_memory"]:
            if user_name:
                return self.pick_response("asks_memory_known", user_name=user_name)
            return self.pick_response("asks_memory_unknown")

        if patterns["asks_humanity"]:
            return self._personalized_response(
                "asks_humanity_known",
                "asks_humanity_unknown",
                user_name=user_name,
                memory_hint=memory_hint,
            )

        if patterns["asks_activity"]:
            return self._personalized_response(
                "asks_activity_known",
                "asks_activity_unknown",
                user_name=user_name,
                memory_hint=memory_hint,
            )

        if patterns["asks_user_name"]:
            if user_name:
                return self.pick_response("asks_user_name_known", user_name=user_name)
            return self.pick_response("asks_user_name_unknown")

        if patterns["says_name"]:
            return self.pick_response("says_name", user_name=patterns["user_name"])

        if patterns["greets"]:
            if user_name:
                return self.pick_response("greets_known", user_name=user_name, memory_hint=memory_hint)
            return self.pick_response("greets_unknown", memory_hint=memory_hint)

        if patterns["asks_status"]:
            if user_name:
                return self.pick_response("asks_status_known", mood=mood, user_name=user_name, memory_hint=memory_hint)
            return self.pick_response("asks_status_unknown", mood=mood, memory_hint=memory_hint)

        if patterns["asks_relationship"]:
            return self._personalized_response(
                "asks_relationship_known",
                "asks_relationship_unknown",
                user_name=user_name,
                memory_hint=memory_hint,
            )

        if patterns["asks_trust"]:
            return self._personalized_response(
                "asks_trust_known",
                "asks_trust_unknown",
                user_name=user_name,
                memory_hint=memory_hint,
            )

        if patterns["asks_lonely"]:
            return self._personalized_response(
                "asks_lonely_known",
                "asks_lonely_unknown",
                user_name=user_name,
                memory_hint=memory_hint,
            )

        if patterns["asks_busy"]:
            return self._personalized_response(
                "asks_busy_known",
                "asks_busy_unknown",
                user_name=user_name,
                memory_hint=memory_hint,
            )

        if patterns["asks_story"]:
            return self.pick_response("asks_story")

        if patterns["asks_advice"]:
            return self._personalized_response(
                "asks_advice_known",
                "asks_advice_unknown",
                user_name=user_name,
            )

        if patterns["asks_focus_help"]:
            return self._personalized_response(
                "asks_focus_help_known",
                "asks_focus_help_unknown",
                user_name=user_name,
            )

        if patterns["asks_overthinking_help"]:
            return self._personalized_response(
                "asks_overthinking_help_known",
                "asks_overthinking_help_unknown",
                user_name=user_name,
            )

        if patterns["asks_random_thought"]:
            return self.pick_response("asks_random_thought")

        if patterns["asks_music_taste"]:
            return self.pick_response("asks_music_taste")

        if patterns["asks_joke"]:
            return self.pick_response("asks_joke")

        if patterns["asks_encouragement"]:
            return self._personalized_response(
                "asks_encouragement_known",
                "asks_encouragement_unknown",
                user_name=user_name,
            )

        if patterns["shares_positive_feeling"]:
            return self._personalized_response(
                "shares_positive_feeling_known",
                "shares_positive_feeling_unknown",
                user_name=user_name,
            )

        if patterns["shares_negative_feeling"]:
            return self._personalized_response(
                "shares_negative_feeling_known",
                "shares_negative_feeling_unknown",
                user_name=user_name,
            )

        if patterns["background_app"]:
            if self.parent is not None:
                self.parent.send_event("app_background", None)
            return self.pick_response("background_app")

        if patterns["exit_self"]:
            if self.parent is not None:
                self.parent.send_event("exit", None)
            return self.pick_response("exit_self")

        if patterns["hide_input_window"]:
            if self.parent is not None:
                self.parent.send_event("app_hide_quick_input", None)
            return self.pick_response("hide_input_window")

        if patterns["move_app"]:
            if self.parent is not None:
                self.parent.send_event("app_move", patterns["move_app_target"])
            monitor_text = patterns["move_app_target"].get(
                "monitor_text",
                f"monitor {patterns['move_app_target'].get('monitor', 1)}",
            )
            if patterns["move_app_target"]["position"] == "current":
                return self.pick_response("move_app_monitor_only_success", monitor_text=monitor_text)
            return self.pick_response(
                "move_app_success",
                position=patterns["move_app_target"]["position"].replace("_", " "),
                monitor_text=monitor_text,
            )

        if patterns["scale_app"]:
            if self.parent is not None:
                self.parent.send_event("app_scale", patterns["scale_app_target"])
            return self.pick_response(
                "scale_app_success",
                scale_value=patterns["scale_app_target"]["value"],
            )

        if patterns["window_showcase"]:
            action = patterns["window_showcase_action"] or {}
            if self.parent is not None:
                if action.get("action") == "close":
                    self.parent.send_event("app_hide_window_showcase", None)
                elif action.get("action") == "rotate":
                    self.parent.send_event("app_rotate_window_showcase", {"step": action.get("step", 1)})
                else:
                    self.parent.send_event("app_show_window_showcase", None)

            if action.get("action") == "close":
                return self.pick_response("window_showcase_close")
            if action.get("action") == "rotate":
                direction = "left" if int(action.get("step", 1)) < 0 else "right"
                return self.pick_response("window_showcase_rotate", direction=direction)
            return self.pick_response("window_showcase_open")

        if patterns["farewell"]:
            if user_name:
                return self.pick_response("farewell_known", user_name=user_name)
            return self.pick_response("farewell_unknown")

        if patterns["thanks"]:
            return self.pick_response("thanks")

        if patterns["apology"]:
            return self.pick_response("apology")

        if patterns["compliment"]:
            return self.pick_response("compliment")

        if patterns["insult"]:
            return self.pick_response("insult")

        if patterns["asks_time"]:
            return self.pick_response("asks_time", current_time=self.get_current_time_text())

        if patterns["asks_weather"]:
            if self.web_assistant:
                weather_text = self.web_assistant.get_weather_brief()
                if weather_text:
                    return self.pick_response("asks_weather", weather_text=weather_text)
            return self.pick_response("asks_weather_unavailable")

        if patterns["asks_date"]:
            return self.pick_response("asks_date", current_date=self.get_current_date_text())

        if patterns["asks_news"]:
            if self.web_assistant:
                headlines = self.web_assistant.get_top_news_headlines(limit=3)
                if headlines:
                    return self.pick_response("asks_news", headlines="; ".join(headlines[:3]))
            return self.pick_response("asks_news_unavailable")

        if patterns["asks_capabilities"]:
            return self.pick_response("asks_capabilities")

        if patterns["dev_project_action"]:
            return self.handle_dev_project_action(patterns["dev_project_spec"])

        if patterns["dev_workspace_action"]:
            if self.parent is not None:
                self.parent.send_event("app_start_dev_workspace", patterns["dev_workspace_target"])
            return self.pick_response("dev_workspace_start")

        if patterns["dev_workspace_exit_action"]:
            if self.parent is not None:
                self.parent.send_event("app_stop_dev_workspace", None)
            return self.pick_response("dev_workspace_stop")

        if patterns["thoughtful_workspace_action"]:
            if self.parent is not None:
                self.parent.send_event("app_start_thoughtful_workspace", None)
            return self.pick_response("thoughtful_workspace_start")

        if patterns["web_action"]:
            return self.handle_web_action(
                patterns["web_mode"],
                patterns["web_query"],
                patterns["web_browser_alias"],
                text,
            )

        if patterns["subapp_action"]:
            return self.handle_launch_subapp(
                patterns["subapp_host_alias"],
                patterns["subapp_alias"],
            )

        if patterns["spotify_action"]:
            return self.handle_spotify_action(
                patterns["spotify_mode"],
                patterns["spotify_query"],
                patterns["spotify_spoken_query"],
            )

        if patterns["media_action"]:
            return self.handle_media_action(
                patterns["media_service"],
                patterns["media_query"],
                patterns["media_browser_alias"],
            )

        if patterns["launch_app"]:
            return self.handle_launch_app(patterns["app_alias"])

        if patterns["close_app"]:
            return self.handle_close_app(patterns["app_alias"])

        if patterns["asks_last_topic"]:
            if last_topic:
                return self.pick_response("asks_last_topic_known", last_topic=last_topic)
            return self.pick_response("asks_last_topic_unknown")

        if patterns["asks_previous_message"]:
            if previous_user_message:
                return self.pick_response("asks_previous_message_known", previous_message=previous_user_message)
            return self.pick_response("asks_previous_message_unknown")

        if patterns["asks_preferences"]:
            if preferences:
                return self.pick_response("asks_preferences_known", preferences=", ".join(preferences))
            return self.pick_response("asks_preferences_unknown")

        if patterns["asks_specific_preference"]:
            if patterns["preference_query_value"] in preferences:
                return self.pick_response("asks_specific_preference_known", preference_value=patterns["preference_query_value"])
            return self.pick_response("asks_specific_preference_unknown", preference_value=patterns["preference_query_value"])

        if patterns["sets_preference"]:
            return self.pick_response("sets_preference", preference_value=patterns["preference_value"])

        if patterns["removes_preference"]:
            return self.pick_response("removes_preference", preference_value=patterns["preference_value"])

        if patterns["sets_fact"]:
            return self.pick_response("sets_fact", fact_value=patterns["fact_value"])

        if patterns["asks_facts"]:
            if known_facts:
                return self.pick_response("asks_facts_known", facts="; ".join(known_facts[:3]))
            return self.pick_response("asks_facts_unknown")

        if patterns["asks_specific_fact"]:
            if patterns["fact_query_value"] in known_facts:
                return self.pick_response("asks_specific_fact_known", fact_value=patterns["fact_query_value"])
            return self.pick_response("asks_specific_fact_unknown", fact_value=patterns["fact_query_value"])

        if patterns["asks_follow_up"]:
            return self._topic_follow_up(last_topic, preferences, known_facts, user_name)

        if patterns["asks_unknown"]:
            learned_summary = self.auto_learn_answer(text)
            if learned_summary:
                return learned_summary
            return self.handle_web_action("text", text, source_text=text)

        return self._build_personal_fallback(user_name, preferences, known_facts)

    def handle_launch_app(self, app_alias):
        if not self.app_launcher:
            return self.pick_response("launch_app_unavailable")

        app_key = self.app_launcher.resolve_alias(app_alias)
        if not app_key:
            if not hasattr(self.app_launcher, "launch_any"):
                return self.pick_response("launch_app_unknown", app_alias=app_alias)

            success, reason = self.app_launcher.launch_any(app_alias)
            if success:
                return self.pick_response("launch_app_success", app_name=app_alias)
            return self.pick_response("launch_app_unknown", app_alias=app_alias)

        success, reason = self.app_launcher.launch(app_key)
        display_name = self.app_launcher.get_display_name(app_key)

        if success:
            return self.pick_response("launch_app_success", app_name=display_name)

        if reason == "missing_command":
            return self.pick_response("launch_app_missing_command", app_name=display_name)

        return self.pick_response("launch_app_failed", app_name=display_name)

    def handle_launch_subapp(self, host_alias, subapp_alias):
        if not self.app_launcher:
            return self.pick_response("launch_app_unavailable")

        host_key = self.app_launcher.resolve_alias(host_alias)
        if not host_key:
            return self.pick_response("launch_app_unknown", app_alias=host_alias)

        success, reason = self.app_launcher.launch_subapp(host_key, subapp_alias)
        host_name = self.app_launcher.get_display_name(host_key)
        subapp_key = self.app_launcher.resolve_subapp_alias(host_key, subapp_alias)
        subapp_name = self.app_launcher.get_subapp_display_name(host_key, subapp_key) if subapp_key else subapp_alias

        if success:
            return self.pick_response("launch_subapp_success", subapp_name=subapp_name, app_name=host_name)

        if reason == "unknown_subapp":
            return self.pick_response("launch_subapp_unknown", subapp_alias=subapp_alias, app_name=host_name)

        if reason == "missing_target":
            return self.pick_response("launch_subapp_missing_target", subapp_name=subapp_name, app_name=host_name)

        if reason == "missing_command":
            return self.pick_response("launch_app_missing_command", app_name=host_name)

        return self.pick_response("launch_subapp_failed", subapp_name=subapp_name, app_name=host_name)

    def handle_close_app(self, app_alias):
        if not self.app_launcher:
            return self.pick_response("close_app_unavailable")

        app_key = self.app_launcher.resolve_alias(app_alias)
        if not app_key:
            return self.pick_response("close_app_unknown", app_alias=app_alias)

        success, reason = self.app_launcher.close(app_key)
        display_name = self.app_launcher.get_display_name(app_key)

        if success:
            return self.pick_response("close_app_success", app_name=display_name)

        if reason == "not_running":
            return self.pick_response("close_app_not_running", app_name=display_name)

        return self.pick_response("close_app_failed", app_name=display_name)

    def handle_dev_project_action(self, project_spec):
        if not self.dev_assistant:
            return self.pick_response("dev_project_unavailable")

        result = self.dev_assistant.create_project(project_spec, self.app_launcher)
        if not result["success"]:
            if result["reason"] == "exists":
                return self.pick_response("dev_project_exists", project_name=result["project_name"])
            return self.pick_response("dev_project_failed", project_name=project_spec["project_name"])

        if result["requested_commit"] and not result["commit_created"]:
            if result["requested_editor"] and result["editor_opened"]:
                return self.pick_response(
                    "dev_project_commit_failed_opened",
                    stack=result["stack"],
                    project_name=result["project_name"],
                )
            return self.pick_response(
                "dev_project_commit_failed",
                stack=result["stack"],
                project_name=result["project_name"],
            )

        if result["requested_editor"] and result["editor_opened"]:
            if result["requested_commit"] and result["commit_created"]:
                return self.pick_response(
                    "dev_project_success_commit_opened",
                    stack=result["stack"],
                    project_name=result["project_name"],
                )
            return self.pick_response(
                "dev_project_success_opened",
                stack=result["stack"],
                project_name=result["project_name"],
            )

        if result["requested_commit"] and result["commit_created"]:
            return self.pick_response(
                "dev_project_success_commit",
                stack=result["stack"],
                project_name=result["project_name"],
            )

        return self.pick_response(
            "dev_project_success",
            stack=result["stack"],
            project_name=result["project_name"],
        )

    def handle_spotify_action(self, spotify_mode, spotify_query=None, spoken_query=None):
        if not self.spotify_assistant or not self.app_launcher:
            return self.pick_response("launch_app_unavailable")

        if spotify_mode == "app":
            if self.spotify_assistant.open_app(self.app_launcher):
                return self.pick_response("launch_app_success", app_name="Spotify")
            return self.pick_response("launch_app_failed", app_name="Spotify")

        if self.spotify_assistant.open_search(self.app_launcher, spotify_query):
            if spotify_mode == "playlist":
                return self.pick_response("spotify_playlist_success", query=spoken_query)
            return self.pick_response("spotify_track_success", query=spoken_query)

        return self.pick_response("launch_app_failed", app_name="Spotify")

    def handle_media_action(self, media_service, media_query, browser_alias=None):
        if not self.web_assistant:
            return self.pick_response("web_unavailable")

        if media_service == "youtube_music":
            target = self.web_assistant.build_youtube_music_search_url(media_query)
            if browser_alias and self.app_launcher:
                app_key = self.app_launcher.resolve_alias(browser_alias)
                if app_key:
                    success, _ = self.app_launcher.launch_with_target(app_key, target)
                    if success:
                        return self.pick_response("media_service_success", query=media_query, service_name="YouTube Music")
            self.web_assistant.open_url(target)
            return self.pick_response("media_service_success", query=media_query, service_name="YouTube Music")

        return self.pick_response("web_unavailable")

    def open_web_in_app(self, web_mode, web_query, browser_alias):
        if not self.app_launcher or not self.web_assistant:
            return False

        app_key = self.app_launcher.resolve_alias(browser_alias)
        if not app_key:
            return False

        if web_mode == "site":
            target = self.web_assistant.build_site_url(web_query)
        elif web_mode == "image":
            target = self.web_assistant.build_image_search_url(web_query)
        elif web_mode == "video":
            target = self.web_assistant.build_video_search_url(web_query)
        else:
            target = self.web_assistant.build_web_search_url(web_query)

        success, _ = self.app_launcher.launch_with_target(app_key, target)
        return success

    def handle_web_action(self, web_mode, web_query, browser_alias=None, source_text=None):
        if not self.web_assistant:
            return self.pick_response("web_unavailable")

        if web_mode == "site":
            if browser_alias and self.open_web_in_app(web_mode, web_query, browser_alias):
                return self.pick_response("open_site_success", site_target=web_query)
            self.web_assistant.open_site(web_query)
            return self.pick_response("open_site_success", site_target=web_query)

        if web_mode == "image":
            if browser_alias and self.open_web_in_app(web_mode, web_query, browser_alias):
                return self.pick_response("web_image_success", query=web_query)
            self.web_assistant.open_image_search(web_query)
            return self.pick_response("web_image_success", query=web_query)

        if web_mode == "video":
            if browser_alias and self.open_web_in_app(web_mode, web_query, browser_alias):
                return self.pick_response("web_video_success", query=web_query)
            self.web_assistant.open_video_search(web_query)
            return self.pick_response("web_video_success", query=web_query)

        summary = self.web_assistant.get_text_summary(web_query)
        learned_summary = self.store_learned_answer(web_query, summary)
        if learned_summary and source_text and source_text.strip().lower() != web_query.strip().lower():
            self.store_learned_answer(source_text, summary)
        if learned_summary:
            return learned_summary

        if browser_alias and self.open_web_in_app(web_mode, web_query, browser_alias):
            return self.pick_response("web_text_fallback", query=web_query)

        self.web_assistant.open_web_search(web_query)
        return self.pick_response("web_text_fallback", query=web_query)

    def apply_memory_updates(self, patterns, original_text):
        if not self.memory:
            return

        if patterns["says_name"]:
            self.memory.set_user_name(patterns["user_name"])

        if patterns["sets_preference"] and patterns["preference_value"]:
            self.memory.add_preference(patterns["preference_value"])

        if patterns["removes_preference"] and patterns["preference_value"]:
            self.memory.remove_preference(patterns["preference_value"])

        if patterns["sets_fact"] and patterns["fact_value"]:
            self.memory.add_known_fact(patterns["fact_value"])

        if patterns["greets"]:
            self.memory.set_mood("friendly")

        if patterns["thanks"]:
            self.memory.set_mood("helpful")

        if patterns["compliment"]:
            self.memory.set_mood("proud")

        if patterns["shares_positive_feeling"]:
            self.memory.set_mood("excited")

        if patterns["shares_negative_feeling"] or patterns["asks_encouragement"]:
            self.memory.set_mood("supportive")

        if patterns["insult"]:
            self.memory.set_mood("calm")

        if patterns["apology"]:
            self.memory.set_mood("gentle")

        if patterns["farewell"]:
            self.memory.set_mood("calm")

        if not patterns["cancel_learning"] and not patterns["asks_unknown"]:
            self.memory.clear_pending_learning()

        if patterns["says_name"] or patterns["asks_memory"] or patterns["asks_user_name"]:
            self.memory.set_last_topic("name")
        elif patterns["asks_name"] or patterns["asks_creator"] or patterns["asks_age"] or patterns["asks_origin"] or patterns["asks_language"] or patterns["asks_humanity"]:
            self.memory.set_last_topic("identity")
        elif patterns["asks_activity"]:
            self.memory.set_last_topic("conversation")
        elif patterns["sets_preference"] or patterns["removes_preference"] or patterns["asks_preferences"] or patterns["asks_specific_preference"]:
            self.memory.set_last_topic("preferences")
        elif patterns["sets_fact"] or patterns["asks_facts"] or patterns["asks_specific_fact"]:
            self.memory.set_last_topic("facts")
        elif patterns["asks_relationship"] or patterns["asks_trust"]:
            self.memory.set_last_topic("relationship")
        elif (
            patterns["asks_lonely"]
            or patterns["asks_busy"]
            or patterns["asks_story"]
            or patterns["asks_joke"]
            or patterns["asks_random_thought"]
            or patterns["asks_music_taste"]
        ):
            self.memory.set_last_topic("fun")
        elif patterns["asks_advice"] or patterns["asks_focus_help"] or patterns["asks_overthinking_help"]:
            self.memory.set_last_topic("support")
        elif patterns["asks_encouragement"] or patterns["shares_positive_feeling"] or patterns["shares_negative_feeling"]:
            self.memory.set_last_topic("emotion")
        elif patterns["asks_time"] or patterns["asks_date"] or patterns["asks_weather"] or patterns["asks_news"]:
            self.memory.set_last_topic("time")
        elif patterns["dev_project_action"]:
            self.memory.set_last_topic("dev")
        elif patterns["launch_app"]:
            self.memory.set_last_topic("apps")
        elif patterns["close_app"]:
            self.memory.set_last_topic("apps")
        elif patterns["spotify_action"]:
            self.memory.set_last_topic("spotify")
        elif patterns["media_action"]:
            self.memory.set_last_topic("media")
        elif patterns["background_app"]:
            self.memory.set_last_topic("app")
        elif patterns["move_app"]:
            self.memory.set_last_topic("app")
        elif patterns["scale_app"]:
            self.memory.set_last_topic("app")
        elif patterns["web_action"]:
            self.memory.set_last_topic("web")
        elif patterns["cancel_learning"]:
            pass
        elif patterns["asks_last_topic"] or patterns["asks_previous_message"] or patterns["asks_follow_up"]:
            pass
        else:
            self.memory.set_last_topic("conversation")

    def handle_input(self, my_input):
        my_input = my_input.strip()

        if not my_input:
            response = self.pick_response("input_empty")
            if self.parent is not None:
                self.parent.send_event("response_text", response)
            return response

        if self.parent is not None:
            self.parent.send_event("input_text", my_input)

        if my_input == "print":
            print(vocabulary_manager.get_text())
            response = self.pick_response("print_command_done")
            if self.parent is not None:
                self.parent.send_event("response_text", response)
            return response

        data_array = self.tokenize(my_input)
        particle_types = []

        for data in data_array:
            if vocabulary_manager.has_word(data):
                particle_types.append("vocab")
            else:
                particle_types.append("input")
                vocabulary_manager.write_text(data, self.generate_weights())

        encoded_input = self.encode_text(my_input)

        if self.DEBUG_MODE:
            print(f"encoded[:8] = {encoded_input[:8]}")

        intent = self.detect_intent(data_array)
        patterns = self.detect_patterns(my_input.lower())

        if self.memory:
            self.memory.add_message("user", my_input)

        self.apply_memory_updates(patterns, my_input)

        response = self.generate_response(my_input, patterns)

        if self.memory:
            self.memory.add_message("assistant", response)

        if self.DEBUG_MODE:
            print("intent:", intent)
            print("response:", response)

        if self.parent is not None:
            self.parent.send_event("set_particles", particle_types)
            self.parent.send_event("intent", intent)
            self.parent.send_event("response_text", response)

        return response

    def detect_intent(self, tokens):
        if any(t in tokens for t in ["oi", "ola", "hello", "hey", "hi"]):
            return "greeting"

        if any(t in tokens for t in ["bye", "goodbye", "cya", "later", "tchau", "adeus", "falou"]):
            return "farewell"

        if any(t in tokens for t in ["thanks", "thank", "obrigado", "obrigada", "valeu"]):
            return "gratitude"

        if "how" in tokens and "you" in tokens:
            return "status_question"

        if "como" in tokens and "voce" in tokens:
            return "status_question"

        if "joke" in tokens or "piada" in tokens:
            return "joke"

        if "friend" in tokens or "amigos" in tokens or "amizade" in tokens:
            return "relationship"

        if "happy" in tokens or "feliz" in tokens or "excited" in tokens or "animado" in tokens:
            return "positive_emotion"

        if "sad" in tokens or "triste" in tokens or "tired" in tokens or "cansado" in tokens:
            return "negative_emotion"

        if "time" in tokens or "hora" in tokens or "horas" in tokens:
            return "time_question"

        if "date" in tokens or "today" in tokens or "data" in tokens or "hoje" in tokens:
            return "date_question"

        if "sorry" in tokens or "desculpa" in tokens:
            return "apology"

        if "awesome" in tokens or "smart" in tokens or "incrivel" in tokens or "inteligente" in tokens:
            return "compliment"

        if "stupid" in tokens or "dumb" in tokens or "burra" in tokens or "idiota" in tokens:
            return "insult"

        if ("remember" in tokens and "like" in tokens) or ("lembra" in tokens and "gosto" in tokens):
            return "preference_store"

        if ("remember" in tokens and "that" in tokens) or ("lembra" in tokens and "que" in tokens):
            return "fact_store"

        return "unknown"

    @staticmethod
    def extract_name(text_lower):
        blocked_names = {
            "happy",
            "sad",
            "tired",
            "stressed",
            "anxious",
            "lonely",
            "frustrated",
            "excited",
            "proud",
            "fine",
            "good",
            "okay",
            "ok",
            "ready",
            "real",
            "human",
            "feliz",
            "triste",
            "cansado",
            "ansioso",
            "sozinho",
            "bem",
            "pronto",
            "humano",
        }
        match = re.search(r"\b(?:my name is|i am|i'm|meu nome e|me chamo|eu sou|pode me chamar de)\s+([a-zA-Z][a-zA-Z'-]*)", text_lower)
        if match:
            candidate = match.group(1).strip(".,!?")
            if candidate.lower() in blocked_names:
                return None
            return candidate
        return None

    @staticmethod
    def extract_preference(text_lower):
        patterns = [
            r"\bi like\s+(.+)",
            r"\bi love\s+(.+)",
            r"\bmy favorite\s+\w+\s+is\s+(.+)",
            r"\beu gosto de\s+(.+)",
            r"\beu amo\s+(.+)",
            r"\beu adoro\s+(.+)",
            r"\beu curto\s+(.+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                value = match.group(1).strip(" .,!?\t")
                if value:
                    return value
        return None

    @staticmethod
    def extract_removed_preference(text_lower):
        patterns = [
            r"\bi don't like\s+(.+)",
            r"\bi do not like\s+(.+)",
            r"\bforget that i like\s+(.+)",
            r"\beu nao gosto de\s+(.+)",
            r"\beu não gosto de\s+(.+)",
            r"\bnao curto\s+(.+)",
            r"\bnão curto\s+(.+)",
            r"\besquece que eu gosto de\s+(.+)"
        ]

        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                value = match.group(1).strip(" .,!?\t")
                if value:
                    return value
        return None

    @staticmethod
    def extract_fact(text_lower):
        patterns = [
            r"\bremember that\s+(.+)",
            r"\bkeep in mind that\s+(.+)",
            r"\bthe fact is\s+(.+)",
            r"\blembra que\s+(.+)",
            r"\blembre que\s+(.+)",
            r"\bquero que voce saiba que\s+(.+)",
            r"\bquero que você saiba que\s+(.+)"
        ]

        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                value = match.group(1).strip(" .,!?\t")
                if value:
                    return value
        return None

    @staticmethod
    def extract_preference_query(text_lower):
        patterns = [
            r"\bdo i like\s+(.+)",
            r"\bis\s+(.+)\s+my favorite",
            r"\bdo you remember that i like\s+(.+)",
            r"\bvoce lembra que eu gosto de\s+(.+)",
            r"\bvocê lembra que eu gosto de\s+(.+)",
            r"\beu gosto de\s+(.+)\??$"
        ]

        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                value = match.group(1).strip(" .,!?\t").lower()
                if value:
                    return value
        return None

    @staticmethod
    def extract_fact_query(text_lower):
        patterns = [
            r"\bdo you remember that\s+(.+)",
            r"\bdo you know that\s+(.+)",
            r"\bvoce lembra que\s+(.+)",
            r"\bvocê lembra que\s+(.+)",
            r"\bvoce sabe que\s+(.+)",
            r"\bvocê sabe que\s+(.+)"
        ]

        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                value = match.group(1).strip(" .,!?\t")
                if value:
                    return value
        return None

    def generate_weights(self):
        return [random.uniform(-1, 1) for _ in range(self.weights_amount)]

    def encode_text(self, text):
        tokens = self.tokenize(text)

        result = [0.0] * self.weights_amount
        count = 0

        for token in tokens:
            vector = vocabulary_manager.get_word_vector(token)

            if vector is None:
                continue

            for i in range(self.weights_amount):
                result[i] += vector[i]

            count += 1

        if count > 0:
            for i in range(self.weights_amount):
                result[i] /= count

        return result

    def detect_patterns(self, text_lower):
        text_lower = self.normalize_text(text_lower)
        extracted_name = self.extract_name(text_lower)
        preference_value = self.extract_preference(text_lower)
        removed_preference_value = self.extract_removed_preference(text_lower)
        fact_value = self.extract_fact(text_lower)
        preference_query_value = self.extract_preference_query(text_lower)
        fact_query_value = self.extract_fact_query(text_lower)
        tokens = self.tokenize(text_lower)
        token_set = set(tokens)

        patterns = {
            "asks_name": False,
            "says_name": False,
            "user_name": None,
            "asks_memory": False,
            "asks_humanity": False,
            "asks_activity": False,
            "asks_user_name": False,
            "asks_creator": False,
            "asks_age": False,
            "asks_origin": False,
            "asks_language": False,
            "greets": False,
            "farewell": False,
            "thanks": False,
            "apology": False,
            "compliment": False,
            "insult": False,
            "asks_relationship": False,
            "asks_trust": False,
            "asks_lonely": False,
            "asks_busy": False,
            "asks_story": False,
            "asks_advice": False,
            "asks_focus_help": False,
            "asks_overthinking_help": False,
            "asks_random_thought": False,
            "asks_music_taste": False,
            "asks_weather": False,
            "asks_news": False,
            "asks_joke": False,
            "asks_encouragement": False,
            "shares_positive_feeling": False,
            "shares_negative_feeling": False,
            "background_app": False,
            "exit_self": False,
            "hide_input_window": False,
            "move_app": False,
            "move_app_target": None,
            "scale_app": False,
            "scale_app_target": None,
            "dev_workspace_action": False,
            "dev_workspace_target": None,
            "dev_workspace_exit_action": False,
            "thoughtful_workspace_action": False,
            "window_showcase": False,
            "window_showcase_action": None,
            "asks_status": False,
            "asks_time": False,
            "asks_date": False,
            "asks_capabilities": False,
            "launch_app": False,
            "close_app": False,
            "app_alias": None,
            "subapp_action": False,
            "subapp_host_alias": None,
            "subapp_alias": None,
            "dev_project_action": False,
            "dev_project_spec": None,
            "spotify_action": False,
            "spotify_mode": None,
            "spotify_query": None,
            "spotify_spoken_query": None,
            "media_action": False,
            "media_service": None,
            "media_query": None,
            "media_browser_alias": None,
            "web_action": False,
            "web_mode": None,
            "web_query": None,
            "web_browser_alias": None,
            "asks_last_topic": False,
            "asks_previous_message": False,
            "asks_follow_up": False,
            "asks_unknown": False,
            "cancel_learning": False,
            "sets_preference": False,
            "asks_specific_preference": False,
            "removes_preference": False,
            "preference_value": None,
            "preference_query_value": None,
            "sets_fact": False,
            "asks_specific_fact": False,
            "fact_value": None,
            "fact_query_value": None,
            "asks_preferences": False,
            "asks_facts": False
        }

        if "who are you" in text_lower or "your name" in text_lower:
            patterns["asks_name"] = True

        if extracted_name:
            patterns["says_name"] = True
            patterns["user_name"] = extracted_name

        if token_set.intersection({"hello", "hi", "hey", "oi", "ola", "olá", "eae"}):
            patterns["greets"] = True

        if "do you remember me" in text_lower or "remember my name" in text_lower:
            patterns["asks_memory"] = True

        if any(
            phrase in text_lower
            for phrase in [
                "are you human",
                "are you real",
                "are you alive",
                "are you a real person",
                "are you just a bot",
                "voce e humana",
                "você é humana",
                "voce e real",
                "você é real",
            ]
        ):
            patterns["asks_humanity"] = True

        if any(
            phrase in text_lower
            for phrase in [
                "what are you doing",
                "what are you up to",
                "what are you doing now",
                "wyd",
                "o que voce ta fazendo",
                "o que você ta fazendo",
                "o que voce esta fazendo",
                "o que você está fazendo",
            ]
        ):
            patterns["asks_activity"] = True

        if any(phrase in text_lower for phrase in ["what is my name", "who am i"]):
            patterns["asks_user_name"] = True

        if any(phrase in text_lower for phrase in ["who made you", "who created you", "who built you"]):
            patterns["asks_creator"] = True

        if any(phrase in text_lower for phrase in ["how old are you", "what is your age", "what's your age"]):
            patterns["asks_age"] = True

        if any(phrase in text_lower for phrase in ["where are you from", "where do you live", "where were you made"]):
            patterns["asks_origin"] = True

        if any(
            phrase in text_lower
            for phrase in [
                "what language do you speak",
                "which language do you speak",
                "do you speak portuguese",
                "do you speak english",
                "what languages do you know",
            ]
        ):
            patterns["asks_language"] = True

        if any(phrase in text_lower for phrase in ["how are you", "how do you feel"]) or self.parse_natural_status_request(text_lower):
            patterns["asks_status"] = True

        if any(
            phrase in text_lower
            for phrase in [
                "are we friends",
                "are you my friend",
                "do you like me",
                "you like me",
                "do you care about me",
                "somos amigos",
                "você gosta de mim",
                "voce gosta de mim",
                "você se importa comigo",
                "voce se importa comigo",
            ]
        ):
            patterns["asks_relationship"] = True

        if any(
            phrase in text_lower
            for phrase in [
                "can i trust you",
                "should i trust you",
                "are you trustworthy",
                "posso confiar em voce",
                "posso confiar em você",
                "da pra confiar em voce",
                "dá pra confiar em você",
            ]
        ):
            patterns["asks_trust"] = True

        if any(
            phrase in text_lower
            for phrase in [
                "are you lonely",
                "do you get lonely",
                "you feel lonely",
                "voce se sente sozinha",
                "você se sente sozinha",
                "voce fica sozinha",
                "você fica sozinha",
            ]
        ):
            patterns["asks_lonely"] = True

        if any(
            phrase in text_lower
            for phrase in [
                "are you busy",
                "you busy",
                "are you occupied",
                "voce ta ocupada",
                "você ta ocupada",
                "voce esta ocupada",
                "você está ocupada",
            ]
        ):
            patterns["asks_busy"] = True

        if any(
            phrase in text_lower
            for phrase in [
                "tell me a story",
                "tell me something",
                "say something interesting",
                "me conta uma historia",
                "me conta uma história",
                "conta uma historia",
                "conta uma história",
                "fala alguma coisa",
            ]
        ):
            patterns["asks_story"] = True

        if any(
            phrase in text_lower
            for phrase in [
                "give me advice",
                "what should i do",
                "what do you think i should do",
                "i need advice",
                "me da um conselho",
                "me dê um conselho",
                "o que eu devo fazer",
            ]
        ):
            patterns["asks_advice"] = True

        if any(
            phrase in text_lower
            for phrase in [
                "help me focus",
                "i need to focus",
                "i need focus",
                "how do i focus",
                "preciso focar",
                "quero focar",
                "me ajuda a focar",
                "como eu foco",
            ]
        ):
            patterns["asks_focus_help"] = True

        if any(
            phrase in text_lower
            for phrase in [
                "i'm overthinking",
                "im overthinking",
                "i am overthinking",
                "i can't stop thinking",
                "i cant stop thinking",
                "thinking too much",
                "estou pensando demais",
                "to pensando demais",
                "tô pensando demais",
                "nao paro de pensar",
                "não paro de pensar",
            ]
        ):
            patterns["asks_overthinking_help"] = True

        if any(
            phrase in text_lower
            for phrase in [
                "tell me a random thought",
                "say something deep",
                "tell me something deep",
                "tell me something interesting",
                "me fala algo aleatorio",
                "me fala algo aleatório",
                "fala algo profundo",
                "me conta um pensamento",
            ]
        ):
            patterns["asks_random_thought"] = True

        if any(
            phrase in text_lower
            for phrase in [
                "do you like music",
                "what music do you like",
                "what kind of music do you like",
                "what do you listen to",
                "voce gosta de musica",
                "você gosta de música",
                "que musica voce gosta",
                "que música você gosta",
            ]
        ):
            patterns["asks_music_taste"] = True

        if any(
            phrase in text_lower
            for phrase in [
                "tell me a joke",
                "say a joke",
                "make me laugh",
                "joke for me",
                "me conta uma piada",
                "conta uma piada",
            ]
        ):
            patterns["asks_joke"] = True

        if any(
            phrase in text_lower
            for phrase in [
                "motivate me",
                "encourage me",
                "say something nice",
                "i need motivation",
                "i need encouragement",
                "me anima",
                "me motiva",
            ]
        ):
            patterns["asks_encouragement"] = True

        if any(
            phrase in text_lower
            for phrase in [
                "i'm happy",
                "im happy",
                "i am happy",
                "i'm excited",
                "im excited",
                "i am excited",
                "i'm feeling good",
                "im feeling good",
                "i feel good",
                "i'm proud",
                "im proud",
                "i am proud",
                "to feliz",
                "estou feliz",
                "tô feliz",
                "to animado",
                "tô animado",
                "estou animado",
            ]
        ):
            patterns["shares_positive_feeling"] = True

        if any(
            phrase in text_lower
            for phrase in [
                "i'm sad",
                "im sad",
                "i am sad",
                "i'm tired",
                "im tired",
                "i am tired",
                "i'm stressed",
                "im stressed",
                "i am stressed",
                "i'm anxious",
                "im anxious",
                "i am anxious",
                "i'm lonely",
                "im lonely",
                "i am lonely",
                "i'm frustrated",
                "im frustrated",
                "i am frustrated",
                "to triste",
                "tô triste",
                "estou triste",
                "to cansado",
                "tô cansado",
                "estou cansado",
                "to estressado",
                "tô estressado",
                "estou estressado",
                "to ansioso",
                "tô ansioso",
                "estou ansioso",
            ]
        ):
            patterns["shares_negative_feeling"] = True

        if token_set.intersection({"bye", "goodbye", "later"}) or "see you" in text_lower:
            patterns["farewell"] = True

        if "thanks" in token_set or "thank you" in text_lower:
            patterns["thanks"] = True

        if any(phrase in text_lower for phrase in ["sorry", "i'm sorry", "my bad", "oops sorry"]):
            patterns["apology"] = True

        if any(
            phrase in text_lower
            for phrase in [
                "good job",
                "well done",
                "you're awesome",
                "you are awesome",
                "you're smart",
                "you are smart",
                "i love you",
                "you're cute",
                "you are cute",
            ]
        ):
            patterns["compliment"] = True

        if any(
            phrase in text_lower
            for phrase in [
                "you're stupid",
                "you are stupid",
                "you're dumb",
                "you are dumb",
                "you're useless",
                "you are useless",
                "idiot",
            ]
        ):
            patterns["insult"] = True

        if any(phrase in text_lower for phrase in ["what time is it", "tell me the time", "current time", "que horas são", "que horas sao", "me fala as horas", "me diz as horas", "qual a hora", "qual hora e", "qual hora é"]):
            patterns["asks_time"] = True

        if any(
            phrase in text_lower
            for phrase in [
                "what's the weather",
                "what is the weather",
                "how's the weather",
                "weather today",
                "como esta o tempo",
                "como está o tempo",
                "qual o clima hoje",
                "como ta o tempo",
                "como tá o tempo",
                "vai chover hoje",
                "me fala o clima",
            ]
        ):
            patterns["asks_weather"] = True

        if any(
            phrase in text_lower
            for phrase in [
                "what day is it",
                "what is today's date",
                "what's today's date",
                "what is the date today",
                "today's date",
                "qual a data de hoje",
                "que dia e hoje",
                "que dia é hoje",
                "me fala a data de hoje",
            ]
        ):
            patterns["asks_date"] = True

        if any(
            phrase in text_lower
            for phrase in [
                "what are the news",
                "what's the news",
                "news today",
                "today's news",
                "headlines today",
                "noticias de hoje",
                "notícias de hoje",
                "me fale as noticias",
                "me fale as notícias",
                "quais sao as noticias",
                "quais são as notícias",
                "me mostra as noticias de hoje",
                "me mostra as notícias de hoje",
            ]
        ):
            patterns["asks_news"] = True

        if any(
            phrase in text_lower
            for phrase in [
                "bye maya",
                "go to background",
                "run in background",
                "hide yourself",
                "hide maya",
                "minimize yourself",
                "minimize the window",
                "go to the background",
                "vai pro segundo plano",
                "vai para o segundo plano",
                "desocupa a tela",
                "fica em segundo plano",
            ]
        ):
            patterns["background_app"] = True

        if any(
            phrase in text_lower
            for phrase in [
                "close yourself",
                "quit yourself",
                "exit yourself",
                "kill yourself",
                "kill your self",
                "close your self",
                "quit your self",
                "maya close yourself",
                "maya quit yourself",
                "maya exit",
                "maya quit",
                "feche você",
                "fecha você",
                "se fecha",
                "encerra a maya",
                "fechar maya",
            ]
        ):
            patterns["exit_self"] = True

        if any(
            phrase in text_lower
            for phrase in [
                "close the input",
                "close input",
                "hide input",
                "hide the input",
                "close the mini window",
                "close the input window",
                "hide the input window",
                "feche a janela",
                "fecha a janela",
                "feche o input",
                "fecha o input",
                "esconde o input",
                "esconde a janela de input",
            ]
        ):
            patterns["hide_input_window"] = True

        move_target = self.parse_window_move_request(text_lower)
        if move_target:
            patterns["move_app"] = True
            patterns["move_app_target"] = move_target

        scale_target = self.parse_scale_request(text_lower)
        if scale_target:
            patterns["scale_app"] = True
            patterns["scale_app_target"] = scale_target

        dev_workspace_target = self.parse_dev_workspace_request(text_lower)
        if dev_workspace_target:
            patterns["dev_workspace_action"] = True
            patterns["dev_workspace_target"] = dev_workspace_target
        elif self.parse_dev_workspace_exit_request(text_lower):
            patterns["dev_workspace_exit_action"] = True
        elif self.parse_thoughtful_workspace_request(text_lower):
            patterns["thoughtful_workspace_action"] = True

        showcase_target = self.parse_window_showcase_request(text_lower)
        if showcase_target:
            patterns["window_showcase"] = True
            patterns["window_showcase_action"] = showcase_target

        if any(phrase in text_lower for phrase in ["what can you do", "help me", "your capabilities", "o que você pode fazer", "o que voce pode fazer", "me ajuda"]) or self.parse_natural_capabilities_request(text_lower):
            patterns["asks_capabilities"] = True

        if self.dev_assistant:
            dev_project_spec = self.dev_assistant.parse_request(text_lower)
            if dev_project_spec:
                patterns["dev_project_action"] = True
                patterns["dev_project_spec"] = dev_project_spec

        hosted_app = self.parse_hosted_app_action(text_lower)
        if hosted_app:
            if hosted_app["kind"] == "subapp":
                patterns["subapp_action"] = True
                patterns["subapp_host_alias"] = hosted_app["host_alias"]
                patterns["subapp_alias"] = hosted_app["subapp_alias"]
            elif hosted_app["kind"] == "web":
                patterns["web_action"] = True
                patterns["web_mode"] = hosted_app["mode"]
                patterns["web_query"] = hosted_app["query"]
                patterns["web_browser_alias"] = hosted_app["browser_alias"]

        natural_media = self.parse_natural_media_action(text_lower)
        if natural_media:
            if natural_media["kind"] == "spotify":
                patterns["spotify_action"] = True
                patterns["spotify_mode"] = natural_media["mode"]
                patterns["spotify_query"] = natural_media["query"]
                patterns["spotify_spoken_query"] = natural_media["spoken_query"]
            elif natural_media["kind"] == "media":
                patterns["media_action"] = True
                patterns["media_query"] = natural_media["query"]
                patterns["media_service"] = natural_media["service"]
                patterns["media_browser_alias"] = natural_media["browser_alias"]
            elif natural_media["kind"] == "web":
                patterns["web_action"] = True
                patterns["web_mode"] = natural_media["mode"]
                patterns["web_query"] = natural_media["query"]
                patterns["web_browser_alias"] = natural_media["browser_alias"]

        natural_site = self.parse_natural_site_action(text_lower)
        if natural_site and not patterns["web_action"] and not patterns["spotify_action"] and not patterns["media_action"]:
            patterns["web_action"] = True
            patterns["web_mode"] = natural_site["mode"]
            patterns["web_query"] = natural_site["query"]
            patterns["web_browser_alias"] = natural_site["browser_alias"]

        site_match = re.search(
            r"\b(?:open|go to|visit|abre|abrir|acessa|acessar|visita|visitar)\s+(?:site|website|site da|pagina|página)\s+([a-zA-Z0-9.-]+\.[a-z]{2,}(?:/[^\s]+)?)$",
            text_lower
        )
        if site_match and not patterns["web_action"]:
            patterns["web_action"] = True
            patterns["web_mode"] = "site"
            patterns["web_query"] = site_match.group(1).strip()
            patterns["launch_app"] = False
            patterns["app_alias"] = None

        image_match = re.search(
            r"\b(?:search|find|show me|look up|procura|pesquisa|mostra|abre)\s+(?:images|image|pictures|pics|photos|imagens|imagem|fotos|foto)\s+(?:of|for|de)?\s+(.+)$",
            text_lower
        )
        if image_match and not patterns["web_action"]:
            patterns["web_action"] = True
            patterns["web_mode"] = "image"
            patterns["web_query"] = image_match.group(1).strip()

        video_match = re.search(
            r"\b(?:search|find|show me|look up|procura|pesquisa|mostra|abre)\s+(?:videos|video|vídeos|vídeo)\s+(?:of|for|about|de|sobre)?\s+(.+)$",
            text_lower
        )
        if video_match and not patterns["web_action"]:
            patterns["web_action"] = True
            patterns["web_mode"] = "video"
            patterns["web_query"] = video_match.group(1).strip()

        targeted_video_match = re.search(
            r"\b(?:open|search|find|show me|look up|abre|procura|pesquisa|mostra)\s+(?:a\s+|um\s+|uma\s+)?(.+?)\s+video(?:s)?\s+(?:in|on|using|no|na|em)\s+([a-zA-Z0-9 .+-]+)$",
            text_lower
        )
        if targeted_video_match and not patterns["web_action"]:
            patterns["web_action"] = True
            patterns["web_mode"] = "video"
            patterns["web_query"] = targeted_video_match.group(1).strip()
            patterns["web_browser_alias"] = targeted_video_match.group(2).strip()
            patterns["launch_app"] = False
            patterns["app_alias"] = None

        launch_match = re.search(
            r"\b(?:open|launch|start|run|abre|abrir|inicia|iniciar|roda|rodar)\s+([a-zA-Z0-9 .+-]+?)(?:\s+(?:for me|please|pra mim|por favor))?$",
            text_lower
        )
        if launch_match and not patterns["web_action"] and not patterns["spotify_action"] and not patterns["media_action"] and not patterns["dev_project_action"] and not patterns["subapp_action"]:
            patterns["launch_app"] = True
            patterns["app_alias"] = launch_match.group(1).strip()

        close_match = re.search(
            r"\b(?:close|quit|exit|stop|fecha|fechar|encerra|encerrar)\s+([a-zA-Z0-9 .+-]+?)(?:\s+(?:for me|please|pra mim|por favor))?$",
            text_lower
        )
        if close_match and not patterns["exit_self"] and not patterns["web_action"] and not patterns["spotify_action"] and not patterns["media_action"] and not patterns["dev_project_action"]:
            patterns["close_app"] = True
            patterns["app_alias"] = close_match.group(1).strip()

        text_search_match = re.search(
            r"\b(?:search for|look up|google|search|procura|pesquisa|pesquise|busca|buscar)\s+(.+)$",
            text_lower
        )
        if text_search_match and not patterns["web_action"]:
            patterns["web_action"] = True
            patterns["web_mode"] = "text"
            patterns["web_query"] = text_search_match.group(1).strip()

        if any(phrase in text_lower for phrase in ["what were we talking about", "what is the topic", "what were we discussing"]):
            patterns["asks_last_topic"] = True

        if any(phrase in text_lower for phrase in ["what did i just say", "what was my last message", "what did i say before"]):
            patterns["asks_previous_message"] = True

        if any(phrase in text_lower for phrase in ["what else", "anything else", "tell me more", "what more"]):
            patterns["asks_follow_up"] = True

        if any(phrase in text_lower for phrase in ["never mind", "cancel that", "forget it"]):
            patterns["cancel_learning"] = True

        if preference_value:
            patterns["sets_preference"] = True
            patterns["preference_value"] = preference_value

        if removed_preference_value:
            patterns["removes_preference"] = True
            patterns["preference_value"] = removed_preference_value

        if preference_query_value:
            patterns["asks_specific_preference"] = True
            patterns["preference_query_value"] = preference_query_value

        if fact_value and not fact_query_value:
            patterns["sets_fact"] = True
            patterns["fact_value"] = fact_value

        if fact_query_value:
            patterns["asks_specific_fact"] = True
            patterns["fact_query_value"] = fact_query_value

        if any(phrase in text_lower for phrase in ["what do i like", "what are my preferences", "what do you know i like"]):
            patterns["asks_preferences"] = True

        if any(phrase in text_lower for phrase in ["what do you remember", "what facts do you know", "what do you know about me"]):
            patterns["asks_facts"] = True

        is_question_like = (
            text_lower.endswith("?")
            or bool(re.match(r"^(what|why|how|when|where|who)\b", text_lower))
            or self.is_knowledge_request(text_lower)
        )

        if (
            not any([
                patterns["asks_name"],
                patterns["says_name"],
                patterns["asks_memory"],
                patterns["asks_humanity"],
                patterns["asks_activity"],
                patterns["asks_user_name"],
                patterns["asks_creator"],
                patterns["asks_age"],
                patterns["asks_origin"],
                patterns["asks_language"],
                patterns["greets"],
                patterns["farewell"],
                patterns["thanks"],
                patterns["apology"],
                patterns["compliment"],
                patterns["insult"],
                patterns["asks_relationship"],
                patterns["asks_joke"],
                patterns["asks_encouragement"],
                patterns["shares_positive_feeling"],
                patterns["shares_negative_feeling"],
                patterns["background_app"],
                patterns["exit_self"],
                patterns["hide_input_window"],
                patterns["move_app"],
                patterns["scale_app"],
                patterns["asks_status"],
                patterns["asks_time"],
                patterns["asks_date"],
                patterns["asks_capabilities"],
                patterns["dev_project_action"],
                patterns["launch_app"],
                patterns["subapp_action"],
                patterns["close_app"],
                patterns["spotify_action"],
                patterns["media_action"],
                patterns["web_action"],
                patterns["asks_last_topic"],
                patterns["asks_previous_message"],
                patterns["asks_follow_up"],
                patterns["sets_preference"],
                patterns["asks_specific_preference"],
                patterns["removes_preference"],
                patterns["sets_fact"],
                patterns["asks_specific_fact"],
                patterns["asks_preferences"],
                patterns["asks_facts"],
                patterns["cancel_learning"],
            ])
            and is_question_like
        ):
            patterns["asks_unknown"] = True

        return patterns

    @staticmethod
    def tokenize(value):
        return re.findall(r"\b[a-z0-9']+\b", Process.normalize_text(value))
