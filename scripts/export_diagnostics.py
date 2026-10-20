"""Export only sanitized structured error events and static catalogs; never raw logs or user data."""
import argparse
import json
import re
import sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from helpers.config import get_runtime_path
from helpers.diagnostics import safe_context
from helpers.errors import error_code, ERRORS
from scripts.audit_errors import build_catalog


def read_events(path,limit=200):
    events=[];malformed=0
    for file in [Path(str(path)+f'.{n}') for n in (3,2,1)]+[Path(path)]:
        if not file.exists():continue
        # Reporter caps these files at one MiB; do not ingest arbitrary huge files.
        if file.stat().st_size>2*1024*1024:
            malformed+=1;continue
        for line in file.read_text(encoding='utf-8',errors='replace').splitlines():
            try:
                event=json.loads(line)
                if event.get('schema')!='maya.error.event.v1':raise ValueError('unknown schema')
                definition=error_code(event.get('code','unexpected'))
                keys=('schema','event_id','timestamp','code','key','category','severity','retryable','operation',
                      'correlation_id','fingerprint')
                clean={key:event.get(key) for key in keys}
                # Reconstruct free-form messages from the trusted registry.
                clean['key']=next(key for key,value in ERRORS.items() if value.code==definition.code)
                clean['timestamp']=datetime.fromisoformat(str(clean['timestamp'])).isoformat()
                clean.update(code=definition.code,category=definition.category,severity=definition.severity,
                             retryable=definition.retryable,message=definition.title_en,action=definition.action_en)
                operation=str(clean.get('operation','unknown'))
                clean['operation']=re.sub(r'[^A-Za-z0-9_.:-]','_',operation)[:100]
                for key in ('event_id','correlation_id','fingerprint'):
                    value=str(clean.get(key,''))
                    clean[key]=value if re.fullmatch(r'[a-f0-9]{16,32}',value) else None
                exception=event.get('exception')
                clean['exception']=None
                if isinstance(exception,dict):
                    name=exception.get('type','Exception')
                    clean['exception']={'type':name if isinstance(name,str) and re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,79}',name) else 'Exception'}
                    for key in ('errno','returncode'):
                        if isinstance(exception.get(key),int):clean['exception'][key]=exception[key]
                clean['context']=safe_context(event.get('context',{}))
                events.append(clean)
            except (ValueError,TypeError,AttributeError):malformed+=1
    return events[-limit:],malformed


def export_report(path,output):
    events,malformed=read_events(path)
    payload=dict(schema='maya.diagnostic.bundle.v1',created_at=datetime.now(timezone.utc).isoformat(),
                 privacy='Only structured error events and static definitions. No .env, memory, audio, transcript or raw session log.',
                 malformed_event_lines=malformed,catalog=build_catalog(),events=events)
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(payload,indent=2,ensure_ascii=False)+'\n')
    return payload


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();report=export_report(get_runtime_path('logs/errors.jsonl'),args.output)
    print(f'Exported {len(report["events"])} sanitized error events.')


if __name__=='__main__':main()
