from __future__ import annotations

from pathlib import Path

from pvm.core.paths import ProjectPaths
from pvm.storage.yaml_io import load_yaml


def load_template(root: Path) -> dict:
    """Load the default prompt template from `.pvm/settings/template.yaml`."""
    paths = ProjectPaths(root.resolve())
    return load_yaml(paths.template_file)
