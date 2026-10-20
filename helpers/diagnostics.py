"""Bounded local error events. No audio, input text, .env values or exception messages."""
import hashlib
import json
import logging
import math
import os
import re
import sys
import threading
import time
import uuid
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path

from helpers.errors import ERRORS, error_code

CORRELATION_ID = ContextVar('maya_error_correlation', default=None)
_ALLOWED_CONTEXT = {'engine','backend','component','field','app','container','attempt','recovered',
                    'timeout_seconds','returncode','device_id','phase','operation_result'}
_SECRET = re.compile(r'(?i)(?:bearer\s+\S+|gh[pousr]_[A-Za-z0-9]+|github_pat_[A-Za-z0-9_]+|sk-[A-Za-z0-9-]{16,}|(?:password|token|secret|api_key)\s*[:=]\s*\S+)')


def safe_context(context):
    result = {}
    for key,value in (context if isinstance(context,dict) else {}).items():
        if key not in _ALLOWED_CONTEXT: continue
        if isinstance(value,(int,float,bool)) or value is None:
            if not isinstance(value,float) or math.isfinite(value):
                result[key] = value
        elif isinstance(value,str):
            result[key] = _SECRET.sub('[redacted]',value.replace(str(Path.home()),'~'))[:160]
    return result


class _PrivateRotatingHandler(RotatingFileHandler):
    def handleError(self,record):
        raise  # Report the write failure without dumping record data to stderr.

    def _open(self):
        fd = os.open(self.baseFilename, os.O_WRONLY|os.O_CREAT|os.O_APPEND, 0o600)
        return os.fdopen(fd,'a',encoding='utf-8')


class ErrorReporter:
    def __init__(self,path, max_bytes=1024*1024, backups=3, sink=None):
        self.path = Path(path)
        self.max_bytes,self.backups,self.sink = max_bytes,backups,sink
        self._lock = threading.RLock()
        self._logger = None
        self._last_notice = {}
        self.write_failures = 0
        self.last_write_failure = None

    def _get_logger(self):
        if self._logger is None:
            self.path.parent.mkdir(parents=True,exist_ok=True)
            logger=logging.Logger('maya.diagnostics.'+uuid.uuid4().hex)
            handler=_PrivateRotatingHandler(self.path,maxBytes=self.max_bytes,backupCount=self.backups,delay=True)
            handler.setFormatter(logging.Formatter('%(message)s'))
            logger.addHandler(handler);logger.propagate=False
            self._logger=logger
        return self._logger

    def report(self,key,error=None,operation='unknown',context=None,notify=True):
        definition=error_code(key)
        registered_key=next(k for k,v in ERRORS.items() if v.code==definition.code)
        operation=re.sub(r'[^A-Za-z0-9_.:-]','_',str(operation))[:100]
        language=os.getenv('LANGUAGE','en')
        portuguese=language.lower().startswith('pt')
        exception={'type':type(error).__name__} if isinstance(error,BaseException) else None
        if exception is not None:
            for name in ('errno','returncode'):
                value=getattr(error,name,None)
                if isinstance(value,int):exception[name]=value
            tb=error.__traceback__
            if tb:
                while tb.tb_next:tb=tb.tb_next
                exception['source']={'file':Path(tb.tb_frame.f_code.co_filename).name,'line':tb.tb_lineno}
        fingerprint=hashlib.sha256(f'{definition.code}|{operation}|{type(error).__name__}'.encode()).hexdigest()[:16]
        event=dict(schema='maya.error.event.v1',event_id=uuid.uuid4().hex,
                   timestamp=datetime.now(timezone.utc).isoformat(),code=definition.code,key=registered_key,
                   category=definition.category,severity=definition.severity,retryable=definition.retryable,
                   operation=operation,correlation_id=CORRELATION_ID.get() or uuid.uuid4().hex,
                   fingerprint=fingerprint,message=definition.title if portuguese else definition.title_en,
                   action=definition.action if portuguese else definition.action_en,
                   exception=exception,context=safe_context(context))
        sink=None
        with self._lock:
            try:
                # handle() avoids the logging module's stderr dump on write failure.
                logger=self._get_logger()
                record=logger.makeRecord(logger.name,logging.ERROR,'',0,json.dumps(event,ensure_ascii=False,allow_nan=False),(),None)
                for handler in logger.handlers:
                    handler.handle(record)
            except Exception as write_error:
                self.write_failures+=1
                self.last_write_failure={"code":"MAY-0002","type":type(write_error).__name__,"count":self.write_failures}
                if self.write_failures==1:
                    try:sys.stderr.write("[MAY-0002] Diagnostic log unavailable. Check log folder access.\n")
                    except Exception:pass
            now=time.monotonic()
            if notify and definition.severity in {'error','critical'}:
                last=self._last_notice.get(fingerprint,-float('inf'))
                if now-last>=3:
                    if len(self._last_notice)>512:self._last_notice.clear()
                    self._last_notice[fingerprint]=now;sink=self.sink
        if sink:
            try:sink(event)
            except Exception:pass  # A broken UI must not break error reporting.
        return event

    def close(self):
        with self._lock:
            if self._logger:
                for handler in self._logger.handlers:handler.close()
                self._logger=None


_REPORTER=None
_REPORTER_LOCK=threading.Lock()

def get_reporter():
    global _REPORTER
    with _REPORTER_LOCK:
        if _REPORTER is None:
            try:
                from helpers.config import get_runtime_path
                path=get_runtime_path('logs/errors.jsonl')
            except Exception:
                path=Path(__file__).resolve().parents[1]/'logs/errors.jsonl'
            _REPORTER=ErrorReporter(path)
        return _REPORTER


def report_error(key,error=None,*,operation='unknown',context=None,notify=True):
    return get_reporter().report(key,error,operation,context,notify)


@contextmanager
def error_scope(correlation_id=None):
    token=CORRELATION_ID.set(correlation_id or uuid.uuid4().hex)
    try:yield CORRELATION_ID.get()
    finally:CORRELATION_ID.reset(token)
