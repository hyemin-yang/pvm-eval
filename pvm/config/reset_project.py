from __future__ import annotations

from pathlib import Path
from typing import Any

from pvm.config.destroy_project import destroy_project
from pvm.config.init_project import DEFAULT_PROJECT_NAME, init_project
from pvm.config.load_config import load_config


def reset_project(root: Path) -> dict[str, Any]:
    """Reset the `.pvm/` project by destroying and re-initializing with the same name."""
    resolved = root.resolve()
    description = ""
    try:
        config = load_config(resolved)
        name = config["name"]
        description = config.get("description", "")
    except Exception:
        name = DEFAULT_PROJECT_NAME
    destroy_project(resolved)
    result = init_project(resolved, name=name)
    if description:
        config = load_config(resolved)
        config["description"] = description
        from pvm.core.paths import ProjectPaths
        from pvm.storage.yaml_io import dump_yaml

        dump_yaml(ProjectPaths(resolved).config_file, config)
        result["description"] = description
    return result
