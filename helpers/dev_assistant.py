import json
import re
import subprocess
from pathlib import Path

from helpers.config import get_path

DEV_PROJECTS_PATH = get_path("DEV_PROJECTS_PATH", "generated_projects")


class DevAssistant:
    def __init__(self, projects_root=DEV_PROJECTS_PATH):
        self.projects_root = Path(projects_root)

    @staticmethod
    def _sanitize_project_name(name):
        cleaned = re.sub(r"[^a-zA-Z0-9 _-]", "", name.strip())
        cleaned = re.sub(r"\s+", "_", cleaned)
        return cleaned.strip("_-").lower()

    def _next_available_name(self, base_name):
        candidate = self._sanitize_project_name(base_name)
        if not candidate:
            candidate = "new_project"

        if not (self.projects_root / candidate).exists():
            return candidate

        index = 2
        while (self.projects_root / f"{candidate}_{index}").exists():
            index += 1

        return f"{candidate}_{index}"

    def parse_request(self, text):
        lowered = text.strip().lower()

        if not re.match(r"^(?:start|create|make)\b", lowered):
            return None

        stack_match = re.search(r"\b(python|node|react|fastapi|flask)\b", lowered)
        if not stack_match:
            return None

        if "project" not in lowered and "app" not in lowered:
            return None

        name_match = re.search(r"\b(?:called|named)\s+(.+?)(?:\s+and\s+.*)?$", text.strip(), flags=re.IGNORECASE)
        if name_match:
            raw_name = name_match.group(1).strip()
            project_name = self._sanitize_project_name(raw_name)
        else:
            raw_name = f"{stack_match.group(1)} project"
            project_name = self._next_available_name(raw_name)

        if not project_name:
            return None

        return {
            "stack": stack_match.group(1),
            "project_name": project_name,
            "display_name": raw_name.strip(),
            "open_vscode": bool(re.search(r"\b(?:in|open it in)\s+(?:vs code|vscode|code)\b", lowered)),
            "initial_commit": "initial commit" in lowered,
        }

    def create_project(self, spec, app_launcher=None):
        project_path = self.projects_root / spec["project_name"]
        if project_path.exists():
            return {
                "success": False,
                "reason": "exists",
                "project_path": project_path,
                "project_name": spec["project_name"],
                "stack": spec["stack"],
            }

        project_path.mkdir(parents=True, exist_ok=False)
        self._write_template(project_path, spec)

        commit_created = False
        if spec.get("initial_commit"):
            commit_created = self._create_initial_commit(project_path)

        editor_opened = False
        if spec.get("open_vscode"):
            editor_opened = self._open_in_vscode(project_path, app_launcher)

        return {
            "success": True,
            "project_path": project_path,
            "project_name": spec["project_name"],
            "stack": spec["stack"],
            "commit_created": commit_created,
            "editor_opened": editor_opened,
            "requested_commit": spec.get("initial_commit", False),
            "requested_editor": spec.get("open_vscode", False),
        }

    def _open_in_vscode(self, project_path, app_launcher):
        if not app_launcher:
            return False

        app_key = app_launcher.resolve_alias("vscode")
        if not app_key or not hasattr(app_launcher, "launch_with_target"):
            return False

        success, _ = app_launcher.launch_with_target(app_key, str(project_path))
        return success

    @staticmethod
    def _run_git(project_path, *args):
        try:
            subprocess.run(
                ["git", *args],
                cwd=project_path,
                check=True,
                capture_output=True,
                text=True,
            )
            return True
        except Exception:
            return False

    def _create_initial_commit(self, project_path):
        if not self._run_git(project_path, "init"):
            return False
        if not self._run_git(project_path, "add", "."):
            return False
        return self._run_git(project_path, "commit", "-m", "Initial commit")

    def _write_template(self, project_path, spec):
        templates = self._build_templates(spec)
        for relative_path, content in templates.items():
            file_path = project_path / relative_path
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")

    def _build_templates(self, spec):
        stack = spec["stack"]
        project_name = spec["project_name"]

        if stack == "python":
            return self._python_template(project_name)
        if stack == "node":
            return self._node_template(project_name)
        if stack == "react":
            return self._react_template(project_name)
        if stack == "fastapi":
            return self._fastapi_template(project_name)
        return self._flask_template(project_name)

    @staticmethod
    def _base_readme(project_name, stack):
        return (
            f"# {project_name}\n\n"
            f"Starter {stack} project generated by Maya.\n"
        )

    def _python_template(self, project_name):
        return {
            "README.md": self._base_readme(project_name, "Python"),
            ".gitignore": "__pycache__/\n.venv/\n.env\n",
            "requirements.txt": "",
            "main.py": (
                'def main():\n'
                f'    print("hello from {project_name}")\n\n'
                'if __name__ == "__main__":\n'
                '    main()\n'
            ),
        }

    def _node_template(self, project_name):
        package_json = {
            "name": project_name,
            "version": "0.1.0",
            "private": True,
            "main": "index.js",
            "scripts": {
                "start": "node index.js",
            },
        }
        return {
            "README.md": self._base_readme(project_name, "Node"),
            ".gitignore": "node_modules/\n.env\n",
            "package.json": json.dumps(package_json, indent=2) + "\n",
            "index.js": f'console.log("hello from {project_name}");\n',
        }

    def _react_template(self, project_name):
        package_json = {
            "name": project_name,
            "version": "0.1.0",
            "private": True,
            "scripts": {
                "dev": "vite",
                "build": "vite build",
                "preview": "vite preview",
            },
            "dependencies": {
                "react": "^18.3.1",
                "react-dom": "^18.3.1",
            },
            "devDependencies": {
                "vite": "^5.4.0",
            },
        }
        return {
            "README.md": self._base_readme(project_name, "React"),
            ".gitignore": "node_modules/\ndist/\n.env\n",
            "package.json": json.dumps(package_json, indent=2) + "\n",
            "index.html": (
                "<!doctype html>\n"
                "<html>\n"
                "  <head>\n"
                '    <meta charset="UTF-8" />\n'
                f"    <title>{project_name}</title>\n"
                "  </head>\n"
                "  <body>\n"
                '    <div id="root"></div>\n'
                '    <script type="module" src="/src/main.jsx"></script>\n'
                "  </body>\n"
                "</html>\n"
            ),
            "src/App.jsx": (
                "export default function App() {\n"
                "  return <h1>Hello from Maya</h1>;\n"
                "}\n"
            ),
            "src/main.jsx": (
                'import React from "react";\n'
                'import ReactDOM from "react-dom/client";\n'
                'import App from "./App.jsx";\n\n'
                'ReactDOM.createRoot(document.getElementById("root")).render(\n'
                "  <React.StrictMode>\n"
                "    <App />\n"
                "  </React.StrictMode>\n"
                ");\n"
            ),
        }

    def _fastapi_template(self, project_name):
        return {
            "README.md": self._base_readme(project_name, "FastAPI"),
            ".gitignore": "__pycache__/\n.venv/\n.env\n",
            "requirements.txt": "fastapi\nuvicorn\n",
            "main.py": (
                "from fastapi import FastAPI\n\n"
                "app = FastAPI()\n\n"
                '@app.get("/")\n'
                "def read_root():\n"
                f'    return {{"message": "hello from {project_name}"}}\n'
            ),
        }

    def _flask_template(self, project_name):
        return {
            "README.md": self._base_readme(project_name, "Flask"),
            ".gitignore": "__pycache__/\n.venv/\n.env\n",
            "requirements.txt": "flask\n",
            "app.py": (
                "from flask import Flask\n\n"
                "app = Flask(__name__)\n\n"
                '@app.get("/")\n'
                "def home():\n"
                f'    return {{"message": "hello from {project_name}"}}\n\n'
                'if __name__ == "__main__":\n'
                '    app.run(debug=True)\n'
            ),
        }
