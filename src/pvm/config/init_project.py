from __future__ import annotations

from pathlib import Path

from pvm.core.errors import AlreadyInitializedError
from pvm.core.paths import ProjectPaths
from pvm.storage.json_io import write_text
from pvm.storage.time import utc_now_iso
from pvm.storage.ulid import generate_ulid
from pvm.storage.yaml_io import dump_yaml


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


def init_project(root: Path, name: str) -> dict[str, str]:
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
            "created_at": created_at,
        },
    )
    dump_yaml(paths.template_file, DEFAULT_TEMPLATE)
    write_text(paths.snapshot_history_file, "")

    return {
        "project_id": project_id,
        "name": name,
        "created_at": created_at,
        "root": str(paths.root),
    }
