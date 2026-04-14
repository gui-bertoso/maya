import re
import subprocess
from pathlib import Path


APP_VERSION = "1.1.0"
BUILD_REVISION_FILE = ".maya_build_revision"
SOURCE_REVISION_FILE = ".maya_source_revision"


def get_project_root():
    return Path(__file__).resolve().parent.parent


def _resolve_git_dir(repo_root):
    dot_git = repo_root / ".git"
    if dot_git.is_dir():
        return dot_git
    if dot_git.is_file():
        content = dot_git.read_text(encoding="utf-8").strip()
        prefix = "gitdir:"
        if content.lower().startswith(prefix):
            git_dir = content[len(prefix):].strip()
            return (repo_root / git_dir).resolve()
    return None


def _read_head_revision(git_dir):
    head_path = git_dir / "HEAD"
    if not head_path.exists():
        return None

    head_value = head_path.read_text(encoding="utf-8").strip()
    if head_value.startswith("ref:"):
        ref_name = head_value.split(":", 1)[1].strip()
        ref_path = git_dir / ref_name
        if ref_path.exists():
            return ref_path.read_text(encoding="utf-8").strip() or None
        packed_refs = git_dir / "packed-refs"
        if packed_refs.exists():
            for line in packed_refs.read_text(encoding="utf-8").splitlines():
                if not line or line.startswith("#") or line.startswith("^"):
                    continue
                revision, name = line.split(" ", 1)
                if name.strip() == ref_name:
                    return revision.strip() or None
        return None
    return head_value or None


def get_revision(project_root=None):
    root = Path(project_root) if project_root else get_project_root()

    for revision_file in (SOURCE_REVISION_FILE, BUILD_REVISION_FILE):
        path = root / revision_file
        if path.exists():
            value = path.read_text(encoding="utf-8").strip()
            if value:
                return value

    git_dir = _resolve_git_dir(root)
    if git_dir is None:
        return None
    return _read_head_revision(git_dir)


def get_short_revision(revision=None, length=7):
    value = (revision or "").strip()
    if not value:
        return None
    return value[:length]


def _run_git_describe(project_root):
    try:
        completed = subprocess.run(
            ["git", "describe", "--tags", "--long", "--always", "--abbrev=7"],
            cwd=project_root,
            check=True,
            capture_output=True,
            text=True,
        )
    except Exception:
        return None
    return completed.stdout.strip() or None


def get_git_describe(project_root=None):
    root = Path(project_root) if project_root else get_project_root()
    return _run_git_describe(root)


def format_version_from_describe(describe, fallback_version=None):
    value = (describe or "").strip()
    base_version = (fallback_version or APP_VERSION).strip()
    if not value:
        return f"v{base_version}"

    match = re.fullmatch(r"v?(.+)-(\d+)-g([0-9a-f]{7,})", value)
    if match:
        tag_version, commits_since_tag, revision = match.groups()
        if commits_since_tag == "0":
            return f"v{tag_version}"
        return f"v{tag_version}+{commits_since_tag}.g{revision[:7]}"

    short_revision = get_short_revision(value)
    if short_revision:
        return f"v{base_version}+g{short_revision}"
    return f"v{base_version}"


def get_version_display(version=None, revision=None, describe=None):
    base_version = (version or APP_VERSION).strip()
    describe_value = describe if describe is not None else get_git_describe()
    if describe_value:
        return format_version_from_describe(describe_value, fallback_version=base_version)

    short_revision = get_short_revision(revision if revision is not None else get_revision())
    if short_revision:
        return f"v{base_version}+g{short_revision}"
    return f"v{base_version}"
