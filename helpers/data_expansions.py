"""Versioned, reloadable data packs. Pack text is never executable."""
import json
import re
import time
import unicodedata
from pathlib import Path
from urllib.parse import urlparse

from helpers.config import get_resource_path, get_runtime_path
from helpers.diagnostics import report_error

CONTAINER_PATTERN = re.compile(r"^DataExpansion(\d+)\.(myde|json)$", re.IGNORECASE)
FORMAT_NAME = "maya-data-expansion"
FORMAT_VERSION = 1


def normalize_question(text):
    value = ''.join(c for c in unicodedata.normalize('NFKD', text.lower()) if not unicodedata.combining(c))
    return ' '.join(re.sub(r'[^\w\s+#]', ' ', value).split())


class DataExpansionLoader:
    def __init__(self, directory=None, refresh_interval=1.0):
        self.directory = Path(directory) if directory else get_runtime_path("data/expansions")
        self.refresh_interval = max(0.0, float(refresh_interval))
        self.command_aliases = {}
        self.responses = {}
        self.knowledge = {}
        self.loaded_files = []
        self.errors = []
        self._fingerprint = None
        self._last_check = 0.0

    def _container_paths(self):
        if not self.directory.exists():
            return []
        numbered = []
        for path in self.directory.iterdir():
            match = CONTAINER_PATTERN.match(path.name)
            if match and path.is_file():
                numbered.append((int(match.group(1)), path.name.lower(), path))
        return [item[2] for item in sorted(numbered)]

    def _current_fingerprint(self, paths):
        result = []
        for path in paths:
            stat = path.stat()
            result.append((str(path.resolve()), stat.st_mtime_ns, stat.st_size))
        return tuple(result)

    @staticmethod
    def _merge(target, additions):
        if not isinstance(additions, dict):
            raise ValueError("command/response sections must be objects")
        for key, values in additions.items():
            if not isinstance(key, str) or not isinstance(values, list):
                raise ValueError("each command/response must contain a list")
            bucket = target.setdefault(key, [])
            for value in values:
                if not isinstance(value, str):
                    raise ValueError("command/response values must be strings")
                value = value.strip()
                if value and value not in bucket:
                    bucket.append(value)

    @staticmethod
    def _knowledge_entries(payload, path):
        entries = payload.get('knowledge', [])
        if not isinstance(entries, list):
            raise ValueError('knowledge must be a list')
        result = {}
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError('knowledge entries must be objects')
            questions, answer, sources = entry.get('questions'), entry.get('answer'), entry.get('sources')
            if not isinstance(questions, list) or not questions or not all(isinstance(q, str) and normalize_question(q) for q in questions):
                raise ValueError('knowledge questions must be nonempty strings')
            if not isinstance(answer, str) or not answer.strip():
                raise ValueError('knowledge answer must be a nonempty string')
            if not isinstance(sources, list) or not sources:
                raise ValueError('knowledge entries require sources')
            for source in sources:
                if not isinstance(source, dict) or not isinstance(source.get('title'), str) or not source['title'].strip():
                    raise ValueError('source title is required')
                url = source.get('url')
                if not isinstance(url, str) or urlparse(url).scheme != 'https' or not urlparse(url).hostname:
                    raise ValueError('sources require HTTPS URLs')
            record = dict(answer=answer.strip(), question=questions[0], sources=sources,
                          source='container', container=path.name, status='curated_reference',
                          pack=payload.get('name', path.stem))
            for question in questions:
                key = normalize_question(question)
                if key in result and result[key] != record:
                    raise ValueError(f'duplicate knowledge question: {question}')
                result[key] = record
        return result

    def get_record(self, question):
        self.refresh()
        return self.knowledge.get(normalize_question(question))

    def refresh(self, force=False):
        now = time.monotonic()
        if not force and now - self._last_check < self.refresh_interval:
            return False
        self._last_check = now
        try:
            paths = self._container_paths()
            fingerprint = self._current_fingerprint(paths)
        except OSError as error:
            # A download/editor can replace a file between discovery and stat.
            self.errors = [f'discovery: {error}']
            report_error("container_reload", error, operation="containers.discover", notify=False)
            return False
        if not force and fingerprint == self._fingerprint:
            return False

        commands, responses, knowledge, loaded_files, errors = {}, {}, {}, [], []
        for path in paths:
            try:
                payload = json.loads(path.read_text(encoding='utf-8'))
                if not isinstance(payload, dict):
                    raise ValueError('container root must be an object')
                if path.suffix.lower() == '.myde':
                    if payload.get('format') != FORMAT_NAME:
                        raise ValueError(f'format must be {FORMAT_NAME!r}')
                    if payload.get('format_version') != FORMAT_VERSION:
                        raise ValueError(f"unsupported format_version: {payload.get('format_version')!r}")
                # Validate the entire container before publishing any part of it.
                pack_commands, pack_responses = {}, {}
                self._merge(pack_commands, payload.get('commands', {}))
                self._merge(pack_responses, payload.get('responses', {}))
                pack_knowledge = self._knowledge_entries(payload, path)
                if any(key in knowledge for key in pack_knowledge):
                    raise ValueError('knowledge question conflicts with an earlier pack')
                self._merge(commands, pack_commands)
                self._merge(responses, pack_responses)
                knowledge.update(pack_knowledge)
                loaded_files.append(path.name)
            except (OSError, ValueError, TypeError, UnicodeError) as error:
                errors.append(f'{path.name}: {error}')
                report_error("container_invalid", error, operation="containers.load", context={"container":path.name}, notify=False)
        self.command_aliases, self.responses, self.knowledge = commands, responses, knowledge
        self.loaded_files, self.errors = loaded_files, errors
        self._fingerprint = fingerprint
        return True


def load_legacy_expansions():
    commands, responses = {}, {}
    for relative_path, target in (("data/command_aliases.json", commands), ("data/response_expansions.json", responses)):
        path = get_resource_path(relative_path)
        if not path.exists():
            continue
        try:
            additions = {}
            DataExpansionLoader._merge(additions, json.loads(path.read_text(encoding='utf-8')))
            DataExpansionLoader._merge(target, additions)
        except (OSError, ValueError, TypeError, UnicodeError) as diagnostic_error:
            report_error("container_invalid", diagnostic_error, operation="data_expansions.load_legacy_expansions", notify=False)
            pass
    return commands, responses
