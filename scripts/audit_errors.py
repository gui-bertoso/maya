"""Read-only source inventory; classification is static triage, not runtime coverage."""
import argparse
import ast
import json
import hashlib
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from helpers.errors import ERRORS

AREAS={'core':'commands','input':'speech_input','output':'interface','helpers':'general','scripts':'installation'}
HINTS=[('whisper','voice_runtime'),('speaker','tts_runtime'),('voice','voice_runtime'),('clap','voice_runtime'),
       ('config','config_value'),('knowledge','knowledge_invalid'),('data_expansions','container_invalid'),
       ('backup','memory_storage'),('routine','routine_storage'),('memory','memory_storage'),
       ('web','web_request'),('research','web_request'),('launcher','app_launch'),('spotify','app_launch'),
       ('hotkey','hotkey'),('single_instance','single_instance'),('renderer','ui_runtime'),('setup','installer')]


def source_files(root):
    files=list(root.glob('*.py'))
    for folder in ('core','input','output','helpers','scripts'):
        files.extend((root/folder).rglob('*.py'))
    return sorted(files)


def call_name(node):
    if isinstance(node,ast.Name):return node.id
    if isinstance(node,ast.Attribute):return call_name(node.value)+'.'+node.attr
    return ''


def review_policy(path,function,exception):
    """Document known fallback boundaries; these labels are not bug verdicts."""
    if 'ImportError' in exception:return 'optional_dependency_guard'
    if exception=='queue.Full':return 'bounded_queue_policy'
    if path=='helpers/diagnostics.py' or (path=='app.py' and function=='_log_unhandled_exception'):
        return 'last_resort_failure_isolation'
    if path=='core/input_pipeline.py' and function.endswith('._run'):return 'delegated_error_callback'
    if path=='helpers/app_launcher.py' and function.endswith('._spawn') and 'TimeoutExpired' in exception:
        return 'startup_observation_window'
    if path=='helpers/app_launcher.py':return 'application_discovery_fallback'
    if path in ('helpers/window_showcase.py','helpers/dev_workspace.py'):
        return 'platform_or_window_probe'
    if path in ('helpers/web_assistant.py','helpers/research.py'):
        return 'network_fallback_boundary'
    if path=='helpers/spotify_assistant.py':return 'optional_bridge_or_playback_probe'
    if path=='helpers/version.py':return 'optional_version_probe'
    if path=='helpers/global_hotkey.py' and function.endswith('.stop'):return 'cleanup_best_effort'
    if path=='helpers/runtime_console.py':return 'optional_console_or_cleanup'
    if path=='output/renderer.py' and '_grab_window_preview' in function:return 'best_effort_preview'
    if path=='output/renderer.py' and function=='_apply_windows_overlay_style':return 'optional_platform_styling'
    if path=='output/speaker.py':return 'voice_fallback_or_cleanup'
    if path=='input/whisper_cpp.py' and function.endswith('.start'):return 'startup_health_polling'
    if path=='input/whisper_cpp.py' and function.endswith('.stop'):return 'process_stop_escalation'
    if path=='input/voice.py' and function.endswith('.stop'):return 'cleanup_best_effort'
    if path.startswith('scripts/'):return 'diagnostic_tool_input_handling'
    if path=='setup.py':return 'installer_bootstrap_review'
    return None


class Inventory(ast.NodeVisitor):
    def __init__(self,path):self.path=path;self.stack=[];self.sites=[];self.unknown_codes=[];self.ordinals=Counter()
    def visit_ClassDef(self,node):
        self.stack.append(node.name);self.generic_visit(node);self.stack.pop()
    def visit_FunctionDef(self,node):
        self.stack.append(node.name);self.generic_visit(node);self.stack.pop()
    visit_AsyncFunctionDef=visit_FunctionDef
    def add(self,node,kind,**fields):
        key=next((key for hint,key in HINTS if hint in self.path),'unexpected')
        function='.'.join(self.stack) or '<module>'
        identity=f'{self.path}|{function}|{kind}'
        self.ordinals[identity]+=1
        site_id=hashlib.sha256(f'{identity}|{self.ordinals[identity]}'.encode()).hexdigest()[:16]
        self.sites.append(dict(site_id=site_id,file=self.path,line=node.lineno,function=function,
                               kind=kind,suggested_code=ERRORS[key].code,**fields))
    def visit_ExceptHandler(self,node):
        exception=ast.unparse(node.type) if node.type else 'bare except'
        descendants=[child for statement in node.body for child in ast.walk(statement)]
        reports=[child for child in descendants if isinstance(child,ast.Call) and call_name(child.func).endswith('report_error')]
        logs=any(isinstance(child,ast.Call) and (call_name(child.func)=='print' or call_name(child.func).startswith('logging.')) for child in descendants)
        raises=any(isinstance(child,ast.Raise) for child in descendants)
        broad=node.type is None or exception in ('Exception','BaseException')
        control=exception in ('queue.Empty','StopIteration','GeneratorExit')
        classification=('control_flow' if control else 'contains_standard_report' if reports else
                        'propagates' if raises else 'legacy_log' if logs else 'needs_review')
        if classification=='needs_review':
            classification=review_policy(self.path,'.'.join(self.stack),exception) or classification
        self.add(node,'exception_handler',exception=exception,broad_catch=broad,
                 classification=classification,contains_raise=raises,
                 risk_flags=['silent_broad_catch'] if broad and not reports and not logs and not raises else [])
        self.generic_visit(node)
    def visit_Raise(self,node):
        self.add(node,'raise',classification='propagates');self.generic_visit(node)
    def visit_Return(self,node):
        value=node.value
        false=isinstance(value,ast.Constant) and value.value is False
        tuple_false=isinstance(value,ast.Tuple) and value.elts and isinstance(value.elts[0],ast.Constant) and value.elts[0].value is False
        if false or tuple_false:
            reason=None
            if tuple_false and len(value.elts)>1 and isinstance(value.elts[1],ast.Constant):
                candidate=value.elts[1].value
                if isinstance(candidate,str) and candidate.replace('_','').isalnum():reason=candidate
            self.add(node,'failure_return',classification='result_contract_review',reason=reason)
        self.generic_visit(node)
    def visit_Assign(self,node):
        if any(isinstance(target,ast.Attribute) and target.attr=='last_error' for target in node.targets):
            if not (isinstance(node.value,ast.Constant) and node.value.value is None):
                self.add(node,'legacy_last_error',classification='legacy_state')
        self.generic_visit(node)
    def visit_Call(self,node):
        if call_name(node.func).endswith('report_error'):
            key=node.args[0].value if node.args and isinstance(node.args[0],ast.Constant) else '<dynamic>'
            operation=next((value.value.value for value in node.keywords if value.arg=='operation' and isinstance(value.value,ast.Constant)),None)
            registered=key in ERRORS or key in {v.code for v in ERRORS.values()} or key=='<dynamic>'
            if not registered:self.unknown_codes.append(dict(file=self.path,line=node.lineno,key=key))
            self.add(node,'standard_report',classification='standard_event',key=key,operation=operation)
        self.generic_visit(node)


def build_inventory(root=ROOT):
    sites=[];parse_errors=[];unknown=[];files=source_files(root)
    for file in files:
        relative=file.relative_to(root).as_posix()
        try:tree=ast.parse(file.read_text(encoding='utf-8'),filename=relative)
        except (SyntaxError,UnicodeError,OSError) as error:
            parse_errors.append(dict(file=relative,type=type(error).__name__));continue
        visitor=Inventory(relative);visitor.visit(tree);sites.extend(visitor.sites);unknown.extend(visitor.unknown_codes)
    sites.sort(key=lambda item:(item['file'],item['line'],item['kind']))
    return dict(schema='maya.error.map.v1',scope='First-party Python: root, core, input, output, helpers, scripts. Tests, vendored/native code, virtualenvs and runtime data excluded.',
                caveat='Static sites are a triage map, not confirmed bugs or proof that every failure emits an event. Suggested codes require semantic review.',
                runtime_coverage_measured=False,classification_basis='AST and documented named-boundary policies; not a bug verdict',
                files_scanned=len(files),summary=dict(Counter(site['kind'] for site in sites)),
                handler_classification=dict(Counter(site['classification'] for site in sites if site['kind']=='exception_handler')),
                parse_errors=parse_errors,unknown_literal_codes=unknown,sites=sites)


def build_catalog():
    return dict(schema='maya.error.catalog.v1',code_format='MAY-NNNN',
                issue_id_format='MAYA-NNN (separate bug tracker identity)',
                cause_policy='possible_causes are hypotheses; confirmed causes belong in bug evidence.',
                definitions=[dict(key=key,**asdict(value)) for key,value in sorted(ERRORS.items(),key=lambda pair:pair[1].code)])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'docs/error-map.json')
    parser.add_argument('--catalog',type=Path,default=ROOT/'data/error_catalog.json')
    args=parser.parse_args();inventory=build_inventory()
    schema_path=ROOT/'docs/schemas/error-event.schema.json'
    if schema_path.exists():
        schema=json.loads(schema_path.read_text())
        schema['properties']['code']['enum']=[value.code for value in ERRORS.values()]
        schema['properties']['key']['enum']=list(ERRORS)
        schema['properties']['category']['enum']=sorted({value.category for value in ERRORS.values()})
        schema_path.write_text(json.dumps(schema,indent=2)+'\n')
    for path,payload in ((args.output,inventory),(args.catalog,build_catalog())):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(payload,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({key:inventory[key] for key in ('files_scanned','summary','handler_classification','parse_errors','unknown_literal_codes')},indent=2))
    return bool(inventory['parse_errors'] or inventory['unknown_literal_codes'])


if __name__=='__main__':raise SystemExit(main())
