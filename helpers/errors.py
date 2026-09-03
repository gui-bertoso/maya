from dataclasses import dataclass


@dataclass(frozen=True)
class ErrorDefinition:
    code: str
    title: str
    action: str


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


def error_code(key):
    return ERRORS.get(key, ERRORS["unexpected"])


def classify_exception(error, context=""):
    context = (context or "").lower()
    if isinstance(error, PermissionError) and ("config" in context or ".env" in str(error).lower()):
        return ERRORS["config_permission"]
    if "qt" in str(error).lower() or "renderer" in context:
        return ERRORS["ui_init"]
    return ERRORS["unexpected"]


def format_error(key, detail=None):
    definition = error_code(key)
    suffix = f": {detail}" if detail else ""
    return f"[{definition.code}] {definition.title}{suffix}"
