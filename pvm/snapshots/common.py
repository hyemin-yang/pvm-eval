from __future__ import annotations

from pathlib import Path

from pvm.core.errors import VersionNotFoundError
from pvm.core.paths import ProjectPaths
from pvm.storage.semver import bump_patch


INITIAL_VERSION = "0.1.0"


def list_snapshot_versions(paths: ProjectPaths) -> list[str]:
    """Return snapshot versions sorted by semantic version."""
    if not paths.snapshot_versions_dir.exists():
        return []
    versions = [
        path.stem
        for path in paths.snapshot_versions_dir.iterdir()
        if path.is_file() and path.suffix == ".json"
    ]
    return sorted(versions, key=lambda value: tuple(int(part) for part in value.split(".")))


def get_next_snapshot_version(paths: ProjectPaths) -> str:
    """Compute the next snapshot version using patch-only increment rules."""
    versions = list_snapshot_versions(paths)
    if not versions:
        return INITIAL_VERSION
    return bump_patch(versions[-1])


def ensure_snapshot_exists(paths: ProjectPaths, version: str) -> None:
    """Raise if a snapshot version does not exist."""
    snapshot_file = paths.snapshot_versions_dir / f"{version}.json"
    if not snapshot_file.exists():
        raise VersionNotFoundError(f"Snapshot version not found: {version}")
