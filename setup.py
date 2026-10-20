import os
import json
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import urllib.request
import zipfile
from pathlib import Path

REPO_OWNER = "gui-bertoso"
REPO_NAME = "maya"
REPO_BRANCH = "main"
APP_NAME = "Maya"
PYTHON_VERSION = "3.11"

BUILD_REVISION_FILE = ".maya_build_revision"
SOURCE_REVISION_FILE = ".maya_source_revision"

GITHUB_API_COMMIT_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/commits/{REPO_BRANCH}"
GITHUB_API_COMPARE_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/compare/{{base}}...{{head}}"
GITHUB_API_COMMITS_URL = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/commits?sha={REPO_BRANCH}&per_page={{limit}}"
GITHUB_ARCHIVE_URL = f"https://github.com/{REPO_OWNER}/{REPO_NAME}/archive/refs/heads/{REPO_BRANCH}.zip"

PRESERVED_PATHS = {".venv", "dist", SOURCE_REVISION_FILE}


def is_windows():
    return sys.platform.startswith("win")


def is_linux():
    return sys.platform.startswith("linux")


def has_gui_support():
    if is_windows():
        return True
    return bool(os.getenv("DISPLAY") or os.getenv("WAYLAND_DISPLAY"))


def windows_subprocess_kwargs():
    if not is_windows():
        return {}

    kwargs = {"creationflags": getattr(subprocess, "CREATE_NO_WINDOW", 0)}
    startupinfo_cls = getattr(subprocess, "STARTUPINFO", None)
    startf_use_showwindow = getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
    sw_hide = getattr(subprocess, "SW_HIDE", 0)

    if startupinfo_cls is not None:
        startupinfo = startupinfo_cls()
        startupinfo.dwFlags |= startf_use_showwindow
        startupinfo.wShowWindow = sw_hide
        kwargs["startupinfo"] = startupinfo

    return kwargs


class Reporter:
    def info(self, message):
        print(message)

    def detail(self, message):
        print(message)

    def error(self, message):
        print(message, file=sys.stderr)

    def release_notes(self, title, items):
        if title:
            print(title)
        for item in items or ():
            print(f"- {item}")

    def close_success(self):
        return

    def close_error(self):
        return

class SetupWindow(Reporter):
    COLORS = {
        "background": "#181b1e", "surface": "#1d2226", "input": "#121517",
        "border": "#33383c", "text": "#edf0f1", "body": "#c9d0d3",
        "muted": "#929da3", "button": "#242a2e", "hover": "#30383d",
        "primary": "#3a4a50", "primary_hover": "#485c65", "focus": "#82999f",
        "green": "#90c3a4", "error": "#e49191",
    }
    STAGES = ("verificar instalação", "preparar arquivos", "configurar a maya", "abrir a maya")

    def __init__(self):
        import tkinter as tk
        from tkinter import ttk, font
        self._tk, self._ttk = tk, ttk
        self._queue = queue.Queue()
        self._allow_close = False
        self._closed = False
        self._state = "running"
        self._stage = 0
        self._angle = 0
        self._details_visible = False
        self.root = tk.Tk()
        c = self.COLORS
        self.root.title("maya · instalação")
        self.root.geometry("960x650")
        self.root.minsize(840, 590)
        self.root.configure(bg=c["background"])
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(2, weight=1)
        families = {name.casefold(): name for name in font.families(self.root)}
        self._font = next((families[name.casefold()] for name in
            ("Segoe UI", "Noto Sans", "DejaVu Sans", "Liberation Sans")
            if name.casefold() in families), "TkDefaultFont")
        self._mono = next((families[name.casefold()] for name in
            ("Cascadia Mono", "JetBrains Mono", "DejaVu Sans Mono", "Liberation Mono")
            if name.casefold() in families), "TkFixedFont")
        icon_path = Path(__file__).resolve().parent / "icon.png"
        if icon_path.exists():
            try:
                self._icon = tk.PhotoImage(file=str(icon_path))
                self.root.iconphoto(True, self._icon)
            except (tk.TclError, OSError):
                pass
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Maya.TButton", background=c["button"], foreground=c["body"],
                        bordercolor=c["border"], lightcolor=c["border"], darkcolor=c["border"],
                        relief="flat", padding=(16, 9), font=(self._font, 10))
        style.map("Maya.TButton", background=[("active", c["hover"]), ("pressed", c["input"])],
                  bordercolor=[("focus", c["focus"])])
        style.configure("Primary.Maya.TButton", background=c["primary"], foreground=c["text"])
        style.map("Primary.Maya.TButton", background=[("active", c["primary_hover"]), ("pressed", c["input"])])
        style.configure("Maya.Horizontal.TProgressbar", background=c["focus"], troughcolor=c["input"],
                        bordercolor=c["input"], lightcolor=c["focus"], darkcolor=c["focus"], thickness=5)
        style.configure("Maya.Vertical.TScrollbar", background="#4d585e", troughcolor=c["surface"],
                        bordercolor=c["surface"], arrowcolor=c["muted"], width=9)
        style.map("Maya.Vertical.TScrollbar", background=[("active", "#74838b")])

        header = tk.Frame(self.root, bg=c["background"])
        header.grid(row=0, column=0, sticky="ew", padx=28, pady=(25, 20))
        header.grid_columnconfigure(1, weight=1)
        self.ring = tk.Canvas(header, width=52, height=52, bg=c["background"], highlightthickness=0)
        self.ring.grid(row=0, column=0, rowspan=2, padx=(0, 14))
        self.ring.create_oval(8, 8, 44, 44, outline=c["border"], width=5)
        self._ring_arc = self.ring.create_arc(8, 8, 44, 44, start=30, extent=260, style="arc", outline=c["green"], width=5)
        self.ring.create_oval(23, 23, 29, 29, fill=c["text"], outline="")
        self.title_label = self._label(header, "maya", size=25, color=c["text"])
        self.title_label.grid(row=0, column=1, sticky="sw")
        self._label(header, "instalação e atualização", color=c["muted"]).grid(row=1, column=1, sticky="nw", pady=(2, 0))
        self.badge = self._label(header, "em andamento", color=c["green"], background=c["surface"], padx=12, pady=7)
        self.badge.grid(row=0, column=2, rowspan=2, sticky="e")

        status = tk.Frame(self.root, bg=c["background"])
        status.grid(row=1, column=0, sticky="ew", padx=28, pady=(0, 23))
        status.grid_columnconfigure(0, weight=1)
        self.status_var = tk.StringVar(value="preparando a maya")
        self.status_label = self._label(status, variable=self.status_var, size=19, color=c["text"], wraplength=860)
        self.status_label.grid(row=0, column=0, sticky="ew")
        self.subtitle_var = tk.StringVar(value="verificando o que precisa ser instalado neste computador.")
        self._label(status, variable=self.subtitle_var, color=c["muted"], wraplength=860).grid(row=1, column=0, sticky="ew", pady=(8, 16))
        self.progress = ttk.Progressbar(status, mode="indeterminate", style="Maya.Horizontal.TProgressbar")
        self.progress.grid(row=2, column=0, sticky="ew")
        self.progress.start(16)

        body = tk.Frame(self.root, bg=c["background"])
        body.grid(row=2, column=0, sticky="nsew", padx=28)
        body.grid_columnconfigure(0, weight=3, uniform="body")
        body.grid_columnconfigure(1, weight=2, uniform="body")
        body.grid_rowconfigure(0, weight=1)
        steps = tk.Frame(body, bg=c["background"])
        steps.grid(row=0, column=0, sticky="nsew", padx=(0, 26))
        self._label(steps, "instalação", color=c["body"], bold=True).pack(anchor="w", pady=(0, 12))
        self._step_widgets = []
        for index, title in enumerate(self.STAGES):
            row = tk.Frame(steps, bg=c["background"], highlightbackground=c["border"], highlightthickness=1)
            row.pack(fill="x", pady=(0, 8), ipady=8)
            number = self._label(row, f"{index+1:02}", color=c["muted"], padx=12)
            number.pack(side="left")
            name = self._label(row, title, color=c["muted"])
            name.pack(side="left", fill="x", expand=True)
            indicator = self._label(row, "", color=c["muted"], padx=12)
            indicator.pack(side="right")
            self._step_widgets.append((row, number, name, indicator))

        notes = tk.Frame(body, bg=c["surface"], highlightbackground=c["border"], highlightthickness=1)
        notes.grid(row=0, column=1, sticky="nsew", pady=(0, 8))
        notes.grid_columnconfigure(0, weight=1)
        notes.grid_rowconfigure(1, weight=1)
        self.changes_title = self._label(notes, "com a maya", color=c["body"], bold=True, background=c["surface"], wraplength=290)
        self.changes_title.grid(row=0, column=0, sticky="ew", padx=18, pady=(16, 12))
        self.changes_text = tk.Text(notes, wrap="word", font=(self._font, 10), bg=c["surface"],
                                    fg=c["body"], relief="flat", borderwidth=0, padx=0, pady=0,
                                    highlightthickness=0, selectbackground="#415d65", cursor="arrow", width=26, height=8)
        self.changes_text.grid(row=1, column=0, sticky="nsew", padx=(18, 8), pady=(0, 16))
        notes_scroll = ttk.Scrollbar(notes, orient="vertical", command=self.changes_text.yview, style="Maya.Vertical.TScrollbar")
        notes_scroll.grid(row=1, column=1, sticky="ns", pady=(0, 16), padx=(0, 6))
        self.changes_text.configure(yscrollcommand=notes_scroll.set, state="disabled")
        self._set_changes("com a maya", ["converse por voz ou texto.", "tenha a maya por perto numa interface flutuante.",
                                            "ajuste voz, aparência e comportamento nas configurações."])

        details = tk.Frame(self.root, bg=c["background"])
        details.grid(row=3, column=0, sticky="ew", padx=28, pady=(10, 0))
        details.grid_columnconfigure(0, weight=1)
        self.details_button = tk.Button(details, text="+ mostrar detalhes", command=self._toggle_details,
            bg=c["background"], fg=c["muted"], activebackground=c["background"], activeforeground=c["text"],
            font=(self._font, 10), relief="flat", borderwidth=0, cursor="hand2", anchor="w", padx=0, pady=5)
        self.details_button.grid(row=0, column=0, sticky="w")
        self.details_frame = tk.Frame(details, bg=c["input"], highlightbackground=c["border"], highlightthickness=1)
        self.details_frame.grid(row=1, column=0, sticky="ew", pady=(7, 0))
        self.details_frame.grid_columnconfigure(0, weight=1)
        self.log_text = tk.Text(self.details_frame, wrap="word", height=7, bg=c["input"], fg=c["muted"],
            font=(self._mono, 9), relief="flat", highlightthickness=0, padx=12, pady=10, selectbackground="#415d65")
        self.log_text.grid(row=0, column=0, sticky="ew")
        scroll = ttk.Scrollbar(self.details_frame, orient="vertical", command=self.log_text.yview, style="Maya.Vertical.TScrollbar")
        scroll.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scroll.set, state="disabled")
        self.details_frame.grid_remove()

        footer = tk.Frame(self.root, bg=c["background"], highlightbackground=c["border"], highlightthickness=0)
        footer.grid(row=4, column=0, sticky="ew", padx=28, pady=(18, 22))
        footer.grid_columnconfigure(0, weight=1)
        self.footer_var = tk.StringVar(value="você pode minimizar enquanto a maya é preparada.")
        self._label(footer, variable=self.footer_var, color=c["muted"], wraplength=620).grid(row=0, column=0, sticky="w", padx=(0, 16))
        self.close_button = ttk.Button(footer, text="minimizar", command=self._on_close, style="Primary.Maya.TButton")
        self.close_button.grid(row=0, column=1, sticky="e")
        self._update_steps()
        self.root.after(40, self._animate_ring)

    def _label(self, parent, text="", variable=None, size=10, color=None, background=None, bold=False, **kwargs):
        return self._tk.Label(parent, text=text, textvariable=variable, bg=background or self.COLORS["background"],
            fg=color or self.COLORS["body"], font=(self._font, size, "bold" if bold else "normal"),
            anchor="w", justify="left", borderwidth=0, **kwargs)

    @staticmethod
    def stage_for(message):
        text = str(message).lower()
        if any(word in text for word in ("launching", "iniciando", "atalhos criados")): return 3
        if any(word in text for word in ("runtime", "virtual environment", "building", "already built")): return 2
        if any(word in text for word in ("downloading", "up to date", "instalando")): return 1
        return 0

    def _animate_ring(self):
        if self._closed: return
        if self._state == "running":
            self._angle = (self._angle + 4) % 360
            self.ring.itemconfigure(self._ring_arc, start=self._angle)
            self.root.after(40, self._animate_ring)

    def _update_steps(self):
        c = self.COLORS
        for index, (row, number, name, indicator) in enumerate(self._step_widgets):
            completed = self._state == "success" or index < self._stage
            active = self._state == "running" and index == self._stage
            failed = self._state == "error" and index == self._stage
            color = c["error"] if failed else c["green"] if completed else c["text"] if active else c["muted"]
            row.configure(highlightbackground=c["focus"] if active else c["border"])
            number.configure(fg=color, text="✓" if completed else f"{index+1:02}")
            name.configure(fg=color)
            indicator.configure(text="parou aqui" if failed else "em curso" if active else "feito" if completed else "", fg=color)

    def _toggle_details(self):
        self._details_visible = not self._details_visible
        if self._details_visible:
            self.details_frame.grid()
            self.details_button.configure(text="− ocultar detalhes")
            if self.root.winfo_height() < 760:
                self.root.geometry(f"{self.root.winfo_width()}x760")
        else:
            self.details_frame.grid_remove()
            self.details_button.configure(text="+ mostrar detalhes")

    def start(self, worker):
        threading.Thread(target=worker, daemon=True).start()
        self.root.after(100, self._pump_queue)
        self.root.mainloop()

    def info(self, message): self._queue.put(("info", message))
    def detail(self, message): self._queue.put(("detail", message))
    def error(self, message): self._queue.put(("error", message))
    def release_notes(self, title, items): self._queue.put(("release_notes", {"title": title, "items": list(items or [])}))
    def close_success(self): self._queue.put(("close_success", ""))
    def close_error(self): self._queue.put(("close_error", ""))

    def _pump_queue(self):
        while not self._closed:
            try: kind, message = self._queue.get_nowait()
            except queue.Empty: break
            self._handle_event(kind, message)
        if not self._closed: self.root.after(100, self._pump_queue)

    def _handle_event(self, kind, message):
        c = self.COLORS
        if kind in ("info", "detail"):
            self._append(message)
            if kind == "info" and self._state == "running":
                self._stage = max(self._stage, self.stage_for(message))
                titles = ("verificando sua instalação", "preparando os arquivos", "configurando a maya", "quase lá")
                descriptions = ("conferindo o que já está disponível neste computador.",
                    "obtendo os arquivos necessários para esta instalação.",
                    "deixando tudo pronto para a maya funcionar.", "finalizando os últimos passos para abrir a maya.")
                self.status_var.set(titles[self._stage]);self.subtitle_var.set(descriptions[self._stage])
                self._update_steps()
            return
        if kind == "release_notes":
            payload = message or {};self._set_changes(payload.get("title") or "novidades", payload.get("items") or [])
            return
        if kind in ("error", "close_error"):
            self._state = "error";self._allow_close = True
            self._append(f"[MAY-1001] {message}" if message else "[MAY-1001] instalação interrompida")
            self.status_var.set("a instalação precisa de atenção")
            self.subtitle_var.set("[MAY-1001] não foi possível concluir. consulte os detalhes antes de tentar novamente.")
            self.badge.configure(text="precisa de atenção", fg=c["error"])
            self.progress.stop();self.progress.configure(mode="determinate", value=0)
            self.ring.itemconfigure(self._ring_arc, outline=c["error"])
            self.close_button.configure(text="fechar")
            self.footer_var.set("seus detalhes de instalação continuam disponíveis nesta janela.")
            self._update_steps()
            return
        if kind == "close_success" and self._state != "error":
            self._state = "success";self._allow_close = True
            self.status_var.set("a maya está pronta")
            self.subtitle_var.set("instalação concluída. você já pode usar a maya.")
            self.badge.configure(text="concluído", fg=c["green"])
            self.progress.stop();self.progress.configure(mode="determinate", value=100)
            self.ring.itemconfigure(self._ring_arc, extent=359, outline=c["green"])
            self.close_button.configure(text="fechar")
            self.footer_var.set("tudo pronto. esta janela já pode ser fechada.")
            self._update_steps()

    def _append(self, message):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{message}\n")
        # Bound long package-manager output without losing the current status.
        if int(self.log_text.index("end-1c").split(".")[0]) > 600:
            self.log_text.delete("1.0", "101.0")
        self.log_text.see("end");self.log_text.configure(state="disabled")

    def _set_changes(self, title, items=None):
        self.changes_title.configure(text=title)
        self.changes_text.configure(state="normal");self.changes_text.delete("1.0", "end")
        if items:
            for item in items: self.changes_text.insert("end", f"{item}\n\n")
        else:
            self.changes_text.insert("end", "nenhuma nota disponível para esta versão.")
        self.changes_text.configure(state="disabled")

    def _on_close(self):
        if self._allow_close:
            self._closed = True;self.root.destroy()
        else: self.root.iconify()

    def preview(self, state="running"):
        """Visual-only preview: never starts download, build or installation workers."""
        self._allow_close = True
        self.root.title("maya · prévia do instalador")
        self._handle_event("info", "Preparing Maya runtime...")
        self._set_changes("nesta atualização", ["reconhecimento local com whisper.cpp.",
            "respostas e controles mais consistentes.", "diagnósticos com códigos de erro."])
        if state == "success": self._handle_event("close_success", "")
        elif state == "error": self._handle_event("error", "exemplo visual de falha; nenhuma instalação foi executada.")
        self.root.mainloop()


def create_reporter():
    if not has_gui_support():
        return Reporter()
    try:
        return SetupWindow()
    except Exception:
        return Reporter()


def runtime_root():
    if getattr(sys, "frozen", False):
        if is_windows():
            base_dir = Path(os.getenv("APPDATA") or (Path.home() / "AppData" / "Roaming"))
        else:
            base_dir = Path(os.getenv("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
        return base_dir / "maya-bootstrap"
    return Path(__file__).resolve().parent


def repo_dir():
    root = runtime_root()
    if getattr(sys, "frozen", False):
        return root / "repo"
    return root


def bundled_app_payload():
    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    candidate = bundle_root / "payload" / f"{APP_NAME}.exe"
    return candidate if candidate.exists() else None


def local_install_dir():
    return Path(os.getenv("LOCALAPPDATA") or (Path.home() / "AppData" / "Local")) / "Programs" / APP_NAME


def create_windows_shortcuts(executable, reporter=None):
    escaped_target = str(executable).replace("'", "''")
    command = (
        "$s=New-Object -ComObject WScript.Shell;"
        "$d=[Environment]::GetFolderPath('Desktop');"
        "$m=Join-Path ([Environment]::GetFolderPath('Programs')) 'Maya';"
        "New-Item -ItemType Directory -Force -Path $m|Out-Null;"
        f"$a=$s.CreateShortcut((Join-Path $d 'Maya.lnk'));$a.TargetPath='{escaped_target}';$a.IconLocation='{escaped_target},0';$a.Save();"
        f"$b=$s.CreateShortcut((Join-Path $m 'Maya.lnk'));$b.TargetPath='{escaped_target}';$b.IconLocation='{escaped_target},0';$b.Save()"
    )
    run(["powershell", "-NoProfile", "-NonInteractive", "-Command", command], reporter=reporter)


def install_bundled_app(payload, reporter=None):
    install_dir = local_install_dir()
    target = install_dir / f"{APP_NAME}.exe"
    install_dir.mkdir(parents=True, exist_ok=True)
    if reporter:
        reporter.info("Instalando Maya 1.2.0...")
    if is_windows():
        subprocess.run(
            ["taskkill", "/IM", f"{APP_NAME}.exe", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            **windows_subprocess_kwargs(),
        )
    if target.exists():
        shutil.copy2(target, install_dir / "Maya.previous.exe")
    shutil.copy2(payload, target)
    (install_dir / "version.txt").write_text("1.2.0\n", encoding="utf-8")
    create_windows_shortcuts(target, reporter=reporter)
    if reporter:
        reporter.info("Atalhos criados. Iniciando a Maya...")
    subprocess.Popen([str(target)], cwd=install_dir, **windows_subprocess_kwargs())


def dist_executable(project_dir):
    if is_windows():
        return project_dir / "dist" / f"{APP_NAME}.exe"
    return project_dir / ".venv" / "bin" / "python"


def build_revision_path(project_dir):
    if is_windows():
        return project_dir / "dist" / BUILD_REVISION_FILE
    return project_dir / ".venv" / BUILD_REVISION_FILE


def source_revision_path(project_dir):
    return project_dir / SOURCE_REVISION_FILE


def run(command, cwd=None, check=True, reporter=None):
    command_text = "> " + " ".join(command)
    if reporter:
        reporter.detail(command_text)
    else:
        print(command_text)
    return subprocess.run(command, cwd=cwd, check=check, **windows_subprocess_kwargs())


def ensure_runtime_root(reporter=None):
    if reporter:
        reporter.detail(f"Using runtime root: {runtime_root()}")
    runtime_root().mkdir(parents=True, exist_ok=True)


def installed_revision(project_dir):
    path = build_revision_path(project_dir)
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def current_source_revision(project_dir):
    path = source_revision_path(project_dir)
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    if not getattr(sys, "frozen", False):
        return "local-dev"
    return ""


def read_json(url, reporter=None):
    if reporter:
        reporter.detail(f"Querying {url}")
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"{REPO_NAME}-bootstrap",
        },
    )
    with urllib.request.urlopen(request) as response:
        return json.load(response)


def download_file(url, target_path, reporter=None):
    if reporter:
        reporter.detail(f"Downloading {url}")
    request = urllib.request.Request(
        url,
        headers={"User-Agent": f"{REPO_NAME}-bootstrap"},
    )
    with urllib.request.urlopen(request) as response, open(target_path, "wb") as target_file:
        shutil.copyfileobj(response, target_file)


def remote_revision(reporter=None):
    payload = read_json(GITHUB_API_COMMIT_URL, reporter=reporter)
    return str(payload.get("sha") or "").strip()


def latest_remote_commits(limit=8, reporter=None):
    payload = read_json(GITHUB_API_COMMITS_URL.format(limit=max(1, limit)), reporter=reporter)
    items = []
    for entry in payload or []:
        sha = str(entry.get("sha") or "").strip()[:7]
        commit = entry.get("commit") or {}
        message = str(commit.get("message") or "").strip().splitlines()[0]
        if message:
            items.append(f"{sha} {message}" if sha else message)
    return items


def compare_remote_changes(base_revision, head_revision, reporter=None):
    if not base_revision or not head_revision or base_revision == head_revision:
        return []

    payload = read_json(
        GITHUB_API_COMPARE_URL.format(base=base_revision, head=head_revision),
        reporter=reporter,
    )
    items = []
    for entry in payload.get("commits") or []:
        sha = str(entry.get("sha") or "").strip()[:7]
        commit = entry.get("commit") or {}
        message = str(commit.get("message") or "").strip().splitlines()[0]
        if message:
            items.append(f"{sha} {message}" if sha else message)
    return items


def current_known_revision(project_dir):
    return current_source_revision(project_dir) or installed_revision(project_dir)


def update_release_notes(project_dir, remote_rev, reporter=None):
    local_rev = current_known_revision(project_dir)

    if local_rev and remote_rev and local_rev == remote_rev:
        if reporter:
            reporter.release_notes("What's New", ["You already have the latest version installed."])
        return

    try:
        if local_rev:
            items = compare_remote_changes(local_rev, remote_rev, reporter=reporter)
            if items:
                title = f"What's New Since {local_rev[:7]}"
                if reporter:
                    reporter.release_notes(title, items)
                return
        items = latest_remote_commits(reporter=reporter)
        title = "Latest Changes"
        if reporter:
            reporter.release_notes(title, items or ["Could not load recent changes."])
    except Exception as error:
        if reporter:
            reporter.release_notes("What's New", [f"Could not load update notes: {error}"])


def clear_project_dir(project_dir):
    project_dir.mkdir(parents=True, exist_ok=True)
    for child in project_dir.iterdir():
        if child.name in PRESERVED_PATHS:
            continue
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()


def extract_archive_into(zip_path, project_dir, reporter=None):
    with tempfile.TemporaryDirectory(prefix="maya-bootstrap-extract-") as temp_dir_raw:
        temp_dir = Path(temp_dir_raw)

        with zipfile.ZipFile(zip_path) as archive:
            if reporter:
                reporter.detail(f"Extracting archive to {project_dir}")
            archive.extractall(temp_dir)

        extracted_roots = [item for item in temp_dir.iterdir() if item.is_dir()]
        if len(extracted_roots) != 1:
            raise RuntimeError("Unexpected archive structure from GitHub.")

        extracted_root = extracted_roots[0]
        clear_project_dir(project_dir)

        for child in extracted_root.iterdir():
            shutil.move(str(child), str(project_dir / child.name))


def sync_repo_from_github(project_dir, reporter=None):
    ensure_runtime_root(reporter=reporter)
    project_dir.mkdir(parents=True, exist_ok=True)

    revision = remote_revision(reporter=reporter)
    update_release_notes(project_dir, revision, reporter=reporter)
    if revision and revision == current_source_revision(project_dir):
        if reporter:
            reporter.info("Maya source is already up to date.")
        return

    if reporter:
        reporter.info("Downloading the latest Maya source...")

    with tempfile.TemporaryDirectory(prefix="maya-bootstrap-download-") as temp_dir_raw:
        temp_dir = Path(temp_dir_raw)
        archive_path = temp_dir / "maya.zip"
        download_file(GITHUB_ARCHIVE_URL, archive_path, reporter=reporter)
        extract_archive_into(archive_path, project_dir, reporter=reporter)

    source_revision_path(project_dir).write_text(f"{revision}\n", encoding="utf-8")


def should_rebuild(project_dir):
    launch_target = dist_executable(project_dir)
    if not launch_target.exists():
        return True

    if not getattr(sys, "frozen", False):
        return False

    return installed_revision(project_dir) != current_source_revision(project_dir)


def find_python_launcher():
    candidates = [
        ["py", f"-{PYTHON_VERSION}"],
        [sys.executable],
        ["python"],
        ["python3"],
    ]

    for candidate in candidates:
        try:
            subprocess.run(
                [*candidate, "--version"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
                text=True,
                **windows_subprocess_kwargs(),
            )
            return candidate
        except Exception:
            continue

    raise RuntimeError("No Python launcher was found for the setup build.")


def venv_python(project_dir):
    scripts_dir = "Scripts" if is_windows() else "bin"
    python_name = "python.exe" if is_windows() else "python"
    return project_dir / ".venv" / scripts_dir / python_name


def ensure_venv(project_dir, reporter=None):
    python_bin = venv_python(project_dir)
    if python_bin.exists():
        return python_bin

    launcher = find_python_launcher()
    if reporter:
        reporter.info("Creating Maya virtual environment...")

    run([*launcher, "-m", "venv", ".venv"], cwd=project_dir, reporter=reporter)
    return python_bin


def rebuild(project_dir, reporter=None):
    if reporter:
        reporter.info("Preparing Maya runtime...")

    python_bin = ensure_venv(project_dir, reporter=reporter)

    run(
        [str(python_bin), "-m", "pip", "install", "--upgrade", "pip"],
        cwd=project_dir,
        reporter=reporter,
    )

    requirements_file = "requirements-windows.txt" if is_windows() else "requirements.txt"
    run(
        [str(python_bin), "-m", "pip", "install", "-r", requirements_file],
        cwd=project_dir,
        reporter=reporter,
    )

    if is_windows():
        if reporter:
            reporter.info("Building Maya.exe...")
        run(
            [str(python_bin), "-m", "PyInstaller", "--noconfirm", "--clean", "maya_windows.spec"],
            cwd=project_dir,
            reporter=reporter,
        )

    revision_file = build_revision_path(project_dir)
    revision_file.parent.mkdir(parents=True, exist_ok=True)
    revision_file.write_text(f"{current_source_revision(project_dir)}\n", encoding="utf-8")


def launch(project_dir, reporter=None):
    env = os.environ.copy()
    env["MAYA_SETUP_COMPLETED"] = "1"

    if is_windows():
        executable = dist_executable(project_dir)
        if not executable.exists():
            raise RuntimeError(f"Executable not found after build: {executable}")

        current_executable = None
        if getattr(sys, "frozen", False):
            try:
                current_executable = Path(sys.executable).resolve()
            except Exception:
                current_executable = None

        try:
            target_executable = executable.resolve()
        except Exception:
            target_executable = executable

        if current_executable and current_executable == target_executable:
            raise RuntimeError(
                "setup recursion detected: target executable is the current executable. "
                "check maya_windows.spec because it may be building the setup instead of the real app."
            )

        if reporter:
            reporter.info("Launching Maya...")

        subprocess.Popen([str(executable)], cwd=project_dir, env=env, **windows_subprocess_kwargs())
        return

    python_bin = venv_python(project_dir)
    if not python_bin.exists():
        raise RuntimeError(f"Python environment not found after setup: {python_bin}")

    if reporter:
        reporter.info("Launching Maya...")

    subprocess.Popen([str(python_bin), "app.py"], cwd=project_dir, env=env, **windows_subprocess_kwargs())


def sync_repo(project_dir, reporter=None):
    if getattr(sys, "frozen", False):
        sync_repo_from_github(project_dir, reporter=reporter)
        return

    message = "Running from local source tree, skipping remote sync."
    if reporter:
        reporter.info(message)
    else:
        print(message)


def run_bootstrap(reporter):
    if os.getenv("MAYA_SETUP_COMPLETED") == "1":
        if reporter:
            reporter.info("Setup already completed for this process.")
        return

    if not (is_windows() or is_linux()):
        raise SystemExit("This setup currently supports Windows and Linux.")

    payload = bundled_app_payload() if is_windows() else None
    if payload is not None:
        reporter.release_notes("Maya 1.2.0", [
            "Novo command center e interface renovada.",
            "Rotinas pessoais, XP, streak e lembretes.",
            "Instalacao local com atalhos do Windows.",
        ])
        install_bundled_app(payload, reporter=reporter)
        reporter.close_success()
        return

    project_dir = repo_dir()
    reporter.info(f"Using project directory: {project_dir}")

    sync_repo(project_dir, reporter=reporter)

    if should_rebuild(project_dir):
        rebuild(project_dir, reporter=reporter)
    else:
        reporter.info("Maya is already built for this source revision.")

    launch(project_dir, reporter=reporter)
    reporter.close_success()


def main():
    if "--preview" in sys.argv:
        index = sys.argv.index("--preview")
        state = sys.argv[index+1] if index+1 < len(sys.argv) else "running"
        if state not in ("running", "success", "error"):
            raise SystemExit("preview state must be running, success or error")
        SetupWindow().preview(state)
        return
    # The bootstrap can launch the application executable after installation.
    # If an incorrectly packaged/old build points that launch back to this
    # executable, refuse to create another setup window/process.
    if os.getenv("MAYA_SETUP_COMPLETED") == "1":
        return

    reporter = create_reporter()

    def worker():
        try:
            run_bootstrap(reporter)
        except Exception as error:
            reporter.error(str(error))
            reporter.close_error()

    if isinstance(reporter, SetupWindow):
        reporter.start(worker)
        return

    worker()


if __name__ == "__main__":
    main()
