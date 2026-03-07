from __future__ import annotations

from pathlib import Path
from typing import Any

from pvm.core.paths import ProjectPaths
from pvm.snapshots.common import ensure_snapshot_exists
from pvm.storage.json_io import load_json


def get_snapshot(root: Path, version: str) -> dict[str, Any]:
    """Load a snapshot manifest by version."""
    paths = ProjectPaths(root.resolve())
    ensure_snapshot_exists(paths, version)
    return load_json(paths.snapshot_versions_dir / f"{version}.json")
