from __future__ import annotations

from pathlib import Path

from pvm.core.paths import ProjectPaths
from pvm.prompts.common import list_prompt_versions


def list_prompt_ids(root: Path) -> list[str]:
    """Return all prompt ids in the current project."""
    paths = ProjectPaths(root.resolve())
    if not paths.prompts_dir.exists():
        return []
    prompt_ids = [path.name for path in paths.prompts_dir.iterdir() if path.is_dir()]
    return sorted(prompt_ids)


def list_prompt_versions_for_id(root: Path, prompt_id: str) -> list[str]:
    """Return all versions for a single prompt id."""
    paths = ProjectPaths(root.resolve())
    return list_prompt_versions(paths, prompt_id)
