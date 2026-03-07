from __future__ import annotations

from pathlib import Path

from pvm.core.paths import ProjectPaths
from pvm.storage.yaml_io import load_yaml


def load_config(root: Path) -> dict:
    """Load project-level metadata from `.pvm/config.yaml`."""
    paths = ProjectPaths(root.resolve())
    return load_yaml(paths.config_file)
