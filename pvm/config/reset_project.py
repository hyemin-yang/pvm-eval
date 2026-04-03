from __future__ import annotations

from pathlib import Path
from typing import Any

from pvm.config.destroy_project import destroy_project
from pvm.config.init_project import DEFAULT_PROJECT_NAME, init_project
from pvm.config.load_config import load_config


def reset_project(root: Path) -> dict[str, Any]:
    """Reset the `.pvm/` project by destroying and re-initializing with the same name."""
    resolved = root.resolve()
    try:
        name = load_config(resolved)["name"]
    except Exception:
        name = DEFAULT_PROJECT_NAME
    destroy_project(resolved)
    return init_project(resolved, name=name)
