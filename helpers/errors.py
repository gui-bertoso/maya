from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorDefinition:
    code: str
    title: str
    action: str
    category: str = "general"
    severity: str = "error"
    retryable: bool = False
    title_en: str = ""
    action_en: str = ""
    possible_causes: tuple[str, ...] = ()


ERRORS = {
    "unexpected": ErrorDefinition("MAY-0001", "Erro interno inesperado", "Consulte o traceback no log."),
    "config_permission": ErrorDefinition("MAY-0101", "Sem acesso à configuração", "Feche instâncias duplicadas e verifique a pasta de dados da Maya."),
    "config_layout": ErrorDefinition("MAY-0102", "Estrutura de dados inválida", "Restaure ou recrie os arquivos locais da Maya."),
    "config_value": ErrorDefinition("MAY-0103", "Configuração inválida", "Corrija o valor indicado nas configurações."),
    "single_instance": ErrorDefinition("MAY-0201", "Falha na trava de instância", "Reinicie a Maya; se persistir, encerre as instâncias antigas."),
    "hotkey": ErrorDefinition("MAY-0202", "Atalho global indisponível", "Confira permissões de teclado e o pynput."),
    "microphone_dependency": ErrorDefinition("MAY-0301", "Dependência de áudio indisponível", "Reinstale as dependências de voz."),
    "microphone_device": ErrorDefinition("MAY-0302", "Microfone não encontrado", "Selecione ou conecte um dispositivo de entrada."),
    "voice_model": ErrorDefinition("MAY-0303", "Modelo de reconhecimento indisponível", "Confira VOSK_MODEL_PATH e os arquivos do modelo."),
    "voice_runtime": ErrorDefinition("MAY-0304", "Falha no reconhecimento de voz", "Confira o microfone e o log de áudio."),
    "noise_suppression": ErrorDefinition("MAY-0305", "Falha no tratamento de ruído", "Revise os parâmetros do supressor de ruído."),
    "tts_init": ErrorDefinition("MAY-0401", "Voz não inicializada", "Confira o mecanismo de voz configurado."),
    "tts_runtime": ErrorDefinition("MAY-0402", "Falha ao falar", "Tente outro mecanismo de voz e consulte o log."),
    "ui_init": ErrorDefinition("MAY-0501", "Interface não inicializada", "Confira PySide6, Qt e as DLLs do pacote."),
    "ui_runtime": ErrorDefinition("MAY-0502", "Falha na interface", "Reabra a Maya e consulte o log."),
    "input_pipeline": ErrorDefinition("MAY-0601", "Falha ao processar entrada", "Repita o comando e consulte o log."),
    "memory_storage": ErrorDefinition("MAY-0701", "Memória local indisponível", "Confira acesso à pasta data."),
    "routine_storage": ErrorDefinition("MAY-0702", "Rotina local indisponível", "Confira data/routine.json e suas permissões."),
    "app_launch": ErrorDefinition("MAY-0801", "Aplicativo não pôde ser aberto", "Confira o caminho e as permissões do aplicativo."),
    "web_request": ErrorDefinition("MAY-0901", "Serviço web indisponível", "Confira a conexão e tente novamente."),
    "installer": ErrorDefinition("MAY-1001", "Falha no instalador", "Consulte o log do instalador."),
    "app_control": ErrorDefinition("MAY-1002", "Executável bloqueado pelo Windows", "Assine o executável ou libere-o pela política de segurança."),
}


# Existing codes are permanent; new definitions never reuse or renumber them.
ERRORS.update({
    "config_write": ErrorDefinition("MAY-0104", "Falha ao salvar configuração", "Confira espaço e permissões; o arquivo anterior foi preservado."),
    "config_apply": ErrorDefinition("MAY-0105", "Configuração não aplicada completamente", "Confira os serviços afetados antes de tentar novamente."),
    "voice_timeout": ErrorDefinition("MAY-0306", "Reconhecimento excedeu o tempo limite", "Tente uma frase curta e confira o servidor de voz."),
    "voice_server": ErrorDefinition("MAY-0307", "Servidor local de voz indisponível", "Confira o binário, modelo e backend selecionados."),
    "voice_backpressure": ErrorDefinition("MAY-0308", "Fila de transcrição cheia", "Espere a transcrição atual e repita a frase."),
    "tts_fallback": ErrorDefinition("MAY-0403", "Voz alternativa acionada", "Confira o motor preferido; a fala pode continuar com outro motor."),
    "ui_screen": ErrorDefinition("MAY-0503", "Monitor indisponível", "Confira o layout dos monitores e a posição da janela."),
    "ui_position": ErrorDefinition("MAY-0504", "Janela não pôde ser posicionada", "Confira o backend gráfico e as permissões do compositor."),
    "input_busy": ErrorDefinition("MAY-0602", "Fila de comandos cheia ou encerrada", "Aguarde e envie novamente; o texto deve ser preservado."),
    "dev_command": ErrorDefinition("MAY-0604", "Ferramenta de desenvolvimento falhou", "Confira o Git, permissões e a pasta do projeto."),
    "parser": ErrorDefinition("MAY-0603", "Falha ao interpretar comando", "Use uma frase explícita e confira o catálogo de comandos."),
    "knowledge_invalid": ErrorDefinition("MAY-0703", "Registro de conhecimento inválido", "Revise o formato sem apagar a base pessoal."),
    "container_invalid": ErrorDefinition("MAY-0704", "Container de dados inválido", "Corrija o pacote indicado; os outros pacotes continuam disponíveis."),
    "container_reload": ErrorDefinition("MAY-0705", "Falha ao atualizar containers", "Confira acesso aos arquivos; o snapshot anterior foi mantido."),
    "knowledge_write": ErrorDefinition("MAY-0706", "Conhecimento não pôde ser salvo", "Confira espaço e permissões; a alteração em memória foi revertida."),
    "storage_corrupt": ErrorDefinition("MAY-0707", "Arquivo de dados ilegível", "Confira o backup antes de restaurar ou editar os dados."),
    "backup_failure": ErrorDefinition("MAY-0708", "Backup não pôde ser criado", "Confira espaço e acesso à pasta de backups."),
    "app_missing": ErrorDefinition("MAY-0802", "Aplicativo não encontrado", "Confira o executável ou launcher instalado."),
    "app_exit": ErrorDefinition("MAY-0803", "Aplicativo encerrou durante a abertura", "Confira o aplicativo diretamente e seus registros de inicialização."),
    "app_stale_lock": ErrorDefinition("MAY-0804", "Trava órfã do aplicativo", "Confirme que não há instância ativa antes de guardar as travas num backup."),
    "app_target": ErrorDefinition("MAY-0805", "Alvo da ação indisponível", "Confirme o aplicativo ou janela antes de repetir a ação."),
    "web_timeout": ErrorDefinition("MAY-0902", "Consulta web excedeu o tempo limite", "Confira a conexão e tente novamente."),
    "web_payload": ErrorDefinition("MAY-0903", "Resposta web inválida", "Tente outra fonte ou consulte a falha de formato registrada."),
    "diagnostics_write": ErrorDefinition("MAY-0002", "Registro de diagnóstico indisponível", "Confira acesso à pasta de logs; a operação original não deve ser interrompida."),
})

_CATEGORIES = {"00": "general", "01": "configuration", "02": "activation", "03": "speech_input",
               "04": "speech_output", "05": "interface", "06": "commands", "07": "persistence",
               "08": "applications", "09": "network", "10": "installation"}
_ENGLISH = {
    "unexpected": ("Unexpected internal error", "Check the diagnostic code and operation."),
    "config_value": ("Invalid setting", "Correct the indicated setting."),
    "config_write": ("Could not save settings", "Check disk space and permissions; the previous file was preserved."),
    "config_apply": ("Settings were not fully applied", "Check the affected services before retrying."),
    "microphone_dependency": ("Audio dependency unavailable", "Check the installed audio dependencies."),
    "microphone_device": ("Microphone unavailable", "Select or connect an input device."),
    "voice_model": ("Speech model unavailable", "Check the selected model and its files."),
    "voice_runtime": ("Speech recognition failed", "Check the microphone and speech engine."),
    "voice_timeout": ("Speech recognition timed out", "Try a shorter phrase and check the local server."),
    "voice_server": ("Local speech server unavailable", "Check its binary, model and selected backend."),
    "voice_backpressure": ("Transcription queue full", "Wait for the current transcription and repeat."),
    "tts_init": ("Speech output could not start", "Check the selected voice engine."),
    "tts_runtime": ("Speech playback failed", "Try another voice engine and check diagnostics."),
    "tts_fallback": ("Alternative voice engine selected", "Check the preferred engine; speech may continue using a fallback."),
    "dev_command": ("Development tool failed", "Check Git, project permissions and its folder."),
    "input_pipeline": ("Command processing failed", "Retry the command and check its diagnostic code."),
    "input_busy": ("Command queue full or closed", "Wait and submit again; your draft should be preserved."),
    "container_invalid": ("Invalid data container", "Fix the indicated pack; other packs remain available."),
    "container_reload": ("Could not reload data packs", "Check file access; the previous snapshot was kept."),
    "storage_corrupt": ("Unreadable data file", "Check the backup before restoring or editing data."),
    "memory_storage": ("Could not save local memory", "Check disk space and data folder permissions."),
    "knowledge_write": ("Could not save knowledge", "Check disk space and permissions; the in-memory change was rolled back."),
    "app_launch": ("Application could not be opened", "Check its launcher and permissions."),
    "app_missing": ("Application not found", "Check the installed executable or desktop launcher."),
    "app_exit": ("Application exited during startup", "Open it directly and check its startup diagnostics."),
    "app_stale_lock": ("Stale application lock", "Verify no active instance exists before backing up stale locks."),
    "web_request": ("Web service unavailable", "Check the connection and try again."),
    "web_timeout": ("Web request timed out", "Check the connection and try again."),
}
_ENGLISH.update({
    "config_permission": ("Settings access denied", "Check data folder permissions and duplicate instances."),
    "config_layout": ("Invalid local data layout", "Inspect local data and its backup before restoring files."),
    "single_instance": ("Instance lock failed", "Check for an existing Maya process before restarting."),
    "hotkey": ("Global shortcut unavailable", "Check keyboard permissions and the session backend."),
    "noise_suppression": ("Audio noise processing failed", "Check noise suppression settings."),
    "ui_init": ("Interface could not start", "Check PySide6 and the selected Qt backend."),
    "ui_runtime": ("Interface operation failed", "Reopen Maya and check the affected operation."),
    "ui_screen": ("Monitor unavailable", "Check the screen layout and window position."),
    "ui_position": ("Could not position the window", "Check the compositor and selected display backend."),
    "parser": ("Could not interpret the command", "Use an explicit phrase and check supported commands."),
    "knowledge_invalid": ("Invalid knowledge record", "Check its format without deleting personal knowledge."),
    "routine_storage": ("Routine data unavailable", "Check routine file access and its backup."),
    "backup_failure": ("Could not create a backup", "Check disk space and backup folder permissions."),
    "app_target": ("Application or window target unavailable", "Confirm the target before retrying."),
    "web_payload": ("Invalid web response", "Try another source and check response-format diagnostics."),
    "installer": ("Installer failed", "Check the installer report."),
    "app_control": ("Windows blocked the executable", "Check executable signing and system application policy."),
    "diagnostics_write": ("Diagnostic log unavailable", "Check log folder access; the original operation should continue."),
})

_WARNINGS = {"hotkey", "tts_fallback", "container_invalid", "container_reload", "storage_corrupt",
             "voice_backpressure", "input_busy", "knowledge_invalid", "diagnostics_write"}
_RETRYABLE = {"microphone_device", "voice_timeout", "voice_server", "voice_runtime", "input_busy",
              "voice_backpressure", "web_request", "web_timeout", "container_reload", "tts_runtime", "app_exit"}
_CAUSES = {
    "general": ("unclassified internal failure",),
    "configuration": ("invalid value", "insufficient file permissions", "storage unavailable"),
    "activation": ("unsupported session backend", "dependency unavailable", "existing process state"),
    "speech_input": ("missing model or dependency", "unavailable input device", "decoder or backend failure"),
    "speech_output": ("voice model unavailable", "audio output unavailable", "synthesis backend failure"),
    "interface": ("unsupported compositor operation", "screen layout changed", "Qt runtime failure"),
    "commands": ("capacity exhausted", "unsupported input", "handler failed"),
    "persistence": ("invalid file format", "permission denied", "storage or backup failure"),
    "applications": ("missing executable", "application failed during startup", "stale process state"),
    "network": ("network unavailable", "timeout", "remote response rejected"),
    "installation": ("blocked executable", "missing bundled resource", "installer failure"),
}
from dataclasses import replace
for _key, _definition in list(ERRORS.items()):
    _title, _action = _ENGLISH.get(_key, ("Operation failed: " + _key.replace('_', ' '),
                                         "Check the diagnostic code and the affected operation."))
    ERRORS[_key] = replace(_definition, category=_CATEGORIES[_definition.code[4:6]],
                          severity="warning" if _key in _WARNINGS else "error",
                          retryable=_key in _RETRYABLE, title_en=_title, action_en=_action,
                          possible_causes=_CAUSES[_CATEGORIES[_definition.code[4:6]]])


def error_code(key):
    if key in ERRORS:
        return ERRORS[key]
    return next((item for item in ERRORS.values() if item.code == key), ERRORS["unexpected"])


def classify_exception(error, context=""):
    context = (context or "").lower()
    if "config" in context or ".env" in str(error).lower():
        if isinstance(error, PermissionError): return ERRORS["config_permission"]
        if isinstance(error, (ValueError, TypeError)): return ERRORS["config_value"]
        return ERRORS["config_write"]
    if "whisper" in context or "voice" in context:
        return ERRORS["voice_timeout" if isinstance(error, TimeoutError) else "voice_runtime"]
    if "speaker" in context or "tts" in context: return ERRORS["tts_runtime"]
    if "renderer" in context or "qt" in context: return ERRORS["ui_init" if "startup" in context else "ui_runtime"]
    if "app.launch" in context: return ERRORS["app_missing" if isinstance(error, FileNotFoundError) else "app_launch"]
    if "web" in context: return ERRORS["web_timeout" if isinstance(error, TimeoutError) else "web_request"]
    if "container" in context: return ERRORS["container_invalid"]
    if "memory" in context or "storage" in context: return ERRORS["memory_storage"]
    return ERRORS["unexpected"]


def user_message(key, language="en"):
    definition = error_code(key)
    portuguese = str(language).lower().startswith('pt')
    title = definition.title if portuguese else definition.title_en
    action = definition.action if portuguese else definition.action_en
    return f"[{definition.code}] {title}. {action}"


def format_error(key, detail=None):
    definition = error_code(key)
    suffix = f": {detail}" if detail else ""
    return f"[{definition.code}] {definition.title}{suffix}"
