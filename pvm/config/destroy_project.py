from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from pvm.core.paths import ProjectPaths


def destroy_project(root: Path) -> dict[str, Any]:
    """Remove the `.pvm/` directory tree entirely."""
    paths = ProjectPaths(root.resolve())

    project_dir = paths.project_dir
    if not project_dir.exists():
        return {"destroyed": False, "reason": "not_found"}

    shutil.rmtree(project_dir)

    return {"destroyed": True, "root": str(paths.root)}
