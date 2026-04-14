from __future__ import annotations

import shutil
from pathlib import Path

from pvm.core.errors import AlreadyInitializedError, NotValidProjectError
from pvm.core.paths import ProjectPaths
from pvm.storage.json_io import write_text
from pvm.storage.time import utc_now_iso
from pvm.storage.ulid import generate_ulid
from pvm.storage.yaml_io import dump_yaml

# 패키지에 번들된 _skills/ 디렉토리 경로
_BUNDLED_SKILLS_DIR = Path(__file__).parent.parent / "_skills"


DEFAULT_TEMPLATE = {
    "id": "intent_classifier",
    "description": "Describe the role of this prompt",
    "author": "alice",
    "llm": {
        "provider": "openai",
        "model": "gpt-4.1",
        "params": {
            "temperature": 0.2,
            "max_tokens": 300,
        },
    },
    "prompt": "Classify the intent of the user input.",
    "input_variables": ["user_input", "history"],
}

DEFAULT_PROJECT_NAME = "my-project"


def init_project(root: Path, name: str = DEFAULT_PROJECT_NAME) -> dict[str, str]:
    """Create the `.pvm/` directory tree and initial project metadata."""
    paths = ProjectPaths(root.resolve())

    if paths.project_dir.exists():
        raise AlreadyInitializedError(
            f"pvm project is already initialized: {paths.project_dir}"
        )

    created_at = utc_now_iso()
    project_id = generate_ulid()

    paths.project_dir.mkdir(parents=True, exist_ok=False)
    paths.settings_dir.mkdir(parents=True, exist_ok=False)
    paths.prompts_dir.mkdir(parents=True, exist_ok=False)
    paths.snapshot_versions_dir.mkdir(parents=True, exist_ok=False)

    dump_yaml(
        paths.config_file,
        {
            "project_id": project_id,
            "name": name,
            "description": "",
            "created_at": created_at,
        },
    )
    dump_yaml(paths.template_file, DEFAULT_TEMPLATE)
    write_text(paths.snapshot_history_file, "")

    _install_claude_skills(root)

    required_dirs = (
        paths.project_dir,
        paths.settings_dir,
        paths.prompts_dir,
        paths.snapshots_dir,
        paths.snapshot_versions_dir,
    )
    required_files = (
        paths.config_file,
        paths.template_file,
        paths.snapshot_history_file,
    )
    is_valid = all(path.exists() and path.is_dir() for path in required_dirs) and all(
        path.exists() and path.is_file() for path in required_files
    )
    if not is_valid:
        raise NotValidProjectError(
            f"Initialized project is missing required files: {paths.project_dir}"
        )

    return {
        "project_id": project_id,
        "name": name,
        "description": "",
        "created_at": created_at,
        "root": str(paths.root),
    }


def _install_claude_skills(root: Path) -> None:
    """패키지에 번들된 Claude Code skills를 프로젝트 루트의 .claude/skills/에 복사한다."""
    if not _BUNDLED_SKILLS_DIR.exists():
        return

    skills_dest = root / ".claude" / "skills"
    skills_dest.mkdir(parents=True, exist_ok=True)

    for skill_src in _BUNDLED_SKILLS_DIR.iterdir():
        if not skill_src.is_dir():
            continue
        skill_dest = skills_dest / skill_src.name
        if skill_dest.exists():
            shutil.rmtree(skill_dest)
        shutil.copytree(skill_src, skill_dest, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"))
