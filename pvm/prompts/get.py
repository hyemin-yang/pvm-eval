from __future__ import annotations

from pathlib import Path
from typing import Any

from pvm.core.errors import VersionNotFoundError
from pvm.core.paths import ProjectPaths
from pvm.prompts.common import (
    ensure_prompt_exists,
    ensure_prompt_version_exists,
    list_prompt_versions,
)
from pvm.storage.json_io import load_json


def get_prompt(root: Path, prompt_id: str, version: str | None = None) -> dict[str, Any]:
    """Read a prompt by explicit version, production version, or latest version."""
    paths = ProjectPaths(root.resolve())
    ensure_prompt_exists(paths, prompt_id)

    target_version = version
    if target_version is None:
        production_file = paths.prompt_production_file(prompt_id)
        if production_file.exists():
            target_version = load_json(production_file)["version"]
        else:
            versions = list_prompt_versions(paths, prompt_id)
            if not versions:
                raise VersionNotFoundError(f"No versions exist for prompt: {prompt_id}")
            target_version = versions[-1]

    ensure_prompt_version_exists(paths, prompt_id, target_version)
    version_dir = paths.prompt_version_dir(prompt_id, target_version)
    return {
        "id": prompt_id,
        "version": target_version,
        "llm": load_json(version_dir / "model_config.json"),
        "prompt": (version_dir / "prompt.md").read_text(encoding="utf-8"),
        "metadata": load_json(version_dir / "metadata.json"),
    }
