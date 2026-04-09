from __future__ import annotations

from pathlib import Path
from typing import Any

from pvm.core.paths import ProjectPaths
from pvm.prompts.common import ensure_prompt_exists
from pvm.storage.yaml_io import dump_yaml, load_yaml


def edit_prompt_info(
    root: Path, prompt_id: str, *, description: str | None = None, author: str | None = None
) -> dict[str, Any]:
    """Update mutable fields in prompt info.yaml."""
    paths = ProjectPaths(root.resolve())
    ensure_prompt_exists(paths, prompt_id)

    info_file = paths.prompt_info_file(prompt_id)
    info = load_yaml(info_file)

    if description is not None:
        info["description"] = description
    if author is not None:
        info["author"] = author

    dump_yaml(info_file, info)
    return info
