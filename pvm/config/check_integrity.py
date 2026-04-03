from __future__ import annotations

from pathlib import Path
from typing import Any

from pvm.core.paths import ProjectPaths


def check_integrity(root: Path) -> dict[str, Any]:
    """Check which required directories and files are missing from `.pvm/`."""
    paths = ProjectPaths(root.resolve())

    required_dirs = (
        paths.project_dir,
        paths.settings_dir,
        paths.prompts_dir,
        paths.snapshots_dir,
        paths.snapshot_versions_dir,
    )
    required_files = (
        paths.config_file,
        paths.template_file,
        paths.snapshot_history_file,
    )

    missing_dirs = [
        str(d.relative_to(paths.root)) for d in required_dirs if not d.is_dir()
    ]
    missing_files = [
        str(f.relative_to(paths.root)) for f in required_files if not f.is_file()
    ]

    return {
        "valid": not missing_dirs and not missing_files,
        "missing_dirs": missing_dirs,
        "missing_files": missing_files,
    }
