from __future__ import annotations

from pathlib import Path

from pvm.core.paths import ProjectPaths
from pvm.snapshots.common import list_snapshot_versions


def list_snapshots(root: Path) -> list[str]:
    """List all snapshot versions in the current project."""
    paths = ProjectPaths(root.resolve())
    return list_snapshot_versions(paths)
