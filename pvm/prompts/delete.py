from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from pvm.core.paths import ProjectPaths
from pvm.prompts.common import ensure_prompt_exists


def delete_prompt(root: Path, prompt_id: str) -> dict[str, Any]:
    """Delete a prompt and all its versions entirely."""
    paths = ProjectPaths(root.resolve())
    ensure_prompt_exists(paths, prompt_id)

    shutil.rmtree(paths.prompt_dir(prompt_id))

    return {"id": prompt_id, "deleted": True}
