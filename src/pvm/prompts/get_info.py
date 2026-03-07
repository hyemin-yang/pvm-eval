from __future__ import annotations

from pathlib import Path
from typing import Any

from pvm.core.paths import ProjectPaths
from pvm.prompts.common import ensure_prompt_exists, list_prompt_versions
from pvm.storage.json_io import load_json
from pvm.storage.yaml_io import load_yaml


def get_prompt_info(root: Path, prompt_id: str) -> dict[str, Any]:
    """Return stable prompt metadata plus version and production summary."""
    paths = ProjectPaths(root.resolve())
    ensure_prompt_exists(paths, prompt_id)

    versions = list_prompt_versions(paths, prompt_id)
    production = None
    production_file = paths.prompt_production_file(prompt_id)
    if production_file.exists():
        production = load_json(production_file)

    return {
        "id": prompt_id,
        "info": load_yaml(paths.prompt_info_file(prompt_id)),
        "versions": versions,
        "latest_version": versions[-1] if versions else None,
        "production": production,
    }
