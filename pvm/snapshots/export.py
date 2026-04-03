from __future__ import annotations

import zipfile
from pathlib import Path
from typing import Any

from pvm.core.paths import ProjectPaths
from pvm.snapshots.common import ensure_snapshot_exists


def export_snapshot(root: Path, version: str, output_path: str | Path | None = None) -> dict[str, Any]:
    """Export a snapshot version as a zip file."""
    paths = ProjectPaths(root.resolve())
    ensure_snapshot_exists(paths, version)

    snapshot_dir = paths.snapshot_version_dir(version)

    if output_path is None:
        output_path = root.resolve() / f"snapshot-{version}.zip"
    else:
        output_path = Path(output_path).resolve()

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for file in snapshot_dir.rglob("*"):
            if file.is_file():
                arcname = file.relative_to(snapshot_dir)
                zf.write(file, arcname)

    return {
        "version": version,
        "output_path": str(output_path),
    }
