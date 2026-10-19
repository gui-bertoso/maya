import os
import re
import unicodedata
from datetime import datetime, timezone
from helpers.backup_manager import create_backup, safe_json_load
import json
import tempfile
import copy
from helpers.config import get_path

KNOWLEDGE_PATH = get_path('KNOWLEDGE_PATH', 'data/learned_knowledge.json')


class KnowledgeBase:
    def __init__(self, file_path=KNOWLEDGE_PATH):
        self.file_path = file_path
        self.data = {'version': 2, 'answers': {}, 'records': {}, 'skills': {}}
        self.load()

    @staticmethod
    def normalize_question(text):
        value = ''.join(c for c in unicodedata.normalize('NFKD', text.lower()) if not unicodedata.combining(c))
        value = re.sub(r'[^\w\s+#]', ' ', value)
        return ' '.join(value.split())

    def load(self):
        if not os.path.exists(self.file_path):
            return
        loaded = safe_json_load(self.file_path, {})
        if not isinstance(loaded, dict):
            return
        self.data.update(loaded)
        for name in ('answers', 'records', 'skills'):
            if not isinstance(self.data.get(name), dict):
                self.data[name] = {}
        self.data['answers'] = {self.normalize_question(k): v for k,v in self.data['answers'].items() if isinstance(v,str)}
        self.data['version'] = 2

    def save(self):
        from pathlib import Path
        path = Path(self.file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
                temporary = stream.name
                json.dump(self.data, stream, ensure_ascii=False, indent=2)
                stream.flush()
                os.fsync(stream.fileno())
            if path.exists():
                create_backup(path)
            os.replace(temporary, path)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)

    def get_record(self, question):
        key = self.normalize_question(question)
        record = self.data['records'].get(key)
        if record:
            return record
        answer = self.data['answers'].get(key)
        return {'answer': answer, 'source': 'legacy', 'sources': [], 'status': 'legacy'} if answer else None

    def get_answer(self, question):
        record = self.get_record(question)
        return record.get('answer') if record else None

    def teach_answer(self, question, answer, source='user', sources=None):
        before = copy.deepcopy(self.data)
        key = self.normalize_question(question)
        if not key or not answer.strip():
            return
        old = self.get_record(question)
        revisions = list((old or {}).get('revisions', []))
        if old and old.get('answer') != answer.strip():
            revisions.append({k:v for k,v in old.items() if k != 'revisions'})
        self.data['skills'].pop(key, None)
        self.data['records'][key] = {'question': question.strip(), 'answer': answer.strip(),
            'source': source, 'sources': list(sources or []),
            'status': 'user_taught' if source == 'user' else 'researched_unverified',
            'updated_at': datetime.now(timezone.utc).isoformat(), 'revisions': revisions[-10:]}
        self.data['answers'][key] = answer.strip()
        self._save_or_restore(before)

    def forget(self, question):
        before = copy.deepcopy(self.data)
        key = self.normalize_question(question)
        found = key in self.data['answers'] or key in self.data['records'] or key in self.data['skills']
        for field in ('answers','records','skills'):
            self.data[field].pop(key,None)
        if found:
            self._save_or_restore(before)
        return found

    def teach_skill(self, trigger, command):
        before = copy.deepcopy(self.data)
        key = self.normalize_question(trigger)
        self.data['records'].pop(key, None)
        self.data['answers'].pop(key, None)
        self.data['skills'][self.normalize_question(trigger)] = {'trigger': trigger, 'command': command,
            'source': 'user', 'updated_at': datetime.now(timezone.utc).isoformat()}
        self._save_or_restore(before)

    def _save_or_restore(self, before):
        try:
            self.save()
        except Exception:
            self.data = before
            raise

    def get_skill(self, trigger):
        return self.data['skills'].get(self.normalize_question(trigger))
