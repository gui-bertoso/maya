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


class Reporter:
    def info(self, message):
        print(message)

    def detail(self, message):
        print(message)

    def error(self, message):
        print(message, file=sys.stderr)

    def close_success(self):
        return

    def close_error(self):
        return

class SetupWindow(Reporter):
    def __init__(self):
        import tkinter as tk
        from tkinter import ttk

        self._tk = tk
        self._ttk = ttk

        self.root = tk.Tk()

        icon_path = Path(__file__).resolve().parent / "icon.ico"
        if icon_path.exists():
            try:
                self.root.iconbitmap(str(icon_path))
            except Exception:
                pass

        self.root.title("Maya Setup")
        self.root.geometry("760x460")
        self.root.minsize(640, 380)
        self.root.configure(bg="#f5efe4")
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(2, weight=1)

        self.title_label = tk.Label(
            self.root,
            text="Maya Setup",
            font=("Segoe UI", 22, "bold"),
            bg="#f5efe4",
            fg="#1f2933",
            anchor="w",
        )
        self.title_label.grid(row=0, column=0, sticky="ew", padx=22, pady=(18, 6))

        self.status_var = tk.StringVar(value="Preparing setup...")
        self.status_label = tk.Label(
            self.root,
            textvariable=self.status_var,
            font=("Segoe UI", 11),
            bg="#f5efe4",
            fg="#3d4852",
            anchor="w",
        )
        self.status_label.grid(row=1, column=0, sticky="ew", padx=22, pady=(0, 10))

        body = tk.Frame(self.root, bg="#f5efe4")
        body.grid(row=2, column=0, sticky="nsew", padx=22, pady=(0, 12))
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self.log_text = tk.Text(
            body,
            wrap="word",
            font=("Consolas", 10),
            bg="#fffdf8",
            fg="#1f2933",
            insertbackground="#1f2933",
            relief="flat",
            padx=14,
            pady=12,
        )
        self.log_text.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(body, orient="vertical", command=self.log_text.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=scrollbar.set, state="disabled")

        footer = tk.Frame(self.root, bg="#f5efe4")
        footer.grid(row=3, column=0, sticky="ew", padx=22, pady=(0, 18))
        footer.grid_columnconfigure(0, weight=1)

        self.progress = ttk.Progressbar(footer, mode="indeterminate")
        self.progress.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        self.progress.start(10)

        self.close_button = tk.Button(
            footer,
            text="Hide",
            command=self._on_close,
            font=("Segoe UI", 10, "bold"),
            bg="#d8c3a5",
            fg="#1f2933",
            activebackground="#c5ae8b",
            activeforeground="#111827",
            relief="flat",
            padx=18,
            pady=8,
        )
        self.close_button.grid(row=1, column=0, sticky="e")

        self._queue = queue.Queue()
        self._allow_close = False
        self._closed = False

    def start(self, worker):
        threading.Thread(target=worker, daemon=True).start()
        self.root.after(100, self._pump_queue)
        self.root.mainloop()

    def info(self, message):
        self._queue.put(("info", message))

    def detail(self, message):
        self._queue.put(("detail", message))

    def error(self, message):
        self._queue.put(("error", message))

    def close_success(self):
        self._queue.put(("close_success", "Maya started."))

    def close_error(self):
        self._queue.put(("close_error", "Setup failed."))

    def _pump_queue(self):
        while True:
            try:
                kind, message = self._queue.get_nowait()
            except queue.Empty:
                break
            self._handle_event(kind, message)

        if not self._closed:
            self.root.after(100, self._pump_queue)

    def _handle_event(self, kind, message):
        if kind == "info":
            self.status_var.set(message)
            self._append(message)
            return

        if kind == "detail":
            self._append(message)
            return

        if kind == "error":
            self.status_var.set(message)
            self._append(f"ERROR: {message}")
            self.progress.stop()
            self.close_button.configure(text="Close")
            self._allow_close = True
            return

        if kind == "close_success":
            self.status_var.set(message)
            self.progress.stop()
            self._allow_close = True
            self._closed = True
            self.root.after(600, self.root.destroy)
            return

        if kind == "close_error":
            self.status_var.set(message)
            self.progress.stop()
            self.close_button.configure(text="Close")
            self._allow_close = True

    def _append(self, message):
        self.log_text.configure(state="normal")
        self.log_text.insert("end", f"{message}\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _on_close(self):
        if self._allow_close:
            self._closed = True
            self.root.destroy()
        else:
            self.root.iconify()


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
    return subprocess.run(command, cwd=cwd, check=check)


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

        subprocess.Popen([str(executable)], cwd=project_dir, env=env)
        return

    python_bin = venv_python(project_dir)
    if not python_bin.exists():
        raise RuntimeError(f"Python environment not found after setup: {python_bin}")

    if reporter:
        reporter.info("Launching Maya...")

    subprocess.Popen([str(python_bin), "app.py"], cwd=project_dir, env=env)


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