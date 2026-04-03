from __future__ import annotations

from pathlib import Path

from pvm.core.errors import VersionNotFoundError
from pvm.core.paths import ProjectPaths
from pvm.storage.semver import bump_major, bump_minor, bump_patch, parse_semver, semver_sort_key


INITIAL_VERSION = "0.1.0"


def list_snapshot_versions(paths: ProjectPaths) -> list[str]:
    """Return snapshot versions sorted by semantic version."""
    if not paths.snapshot_versions_dir.exists():
        return []
    versions = [
        path.name
        for path in paths.snapshot_versions_dir.iterdir()
        if path.is_dir()
    ]
    return sorted(versions, key=semver_sort_key)


def get_next_snapshot_version(paths: ProjectPaths, bump_level: str = "patch") -> str:
    """Compute the next snapshot version using the requested semver bump level."""
    versions = list_snapshot_versions(paths)
    if not versions:
        return INITIAL_VERSION
    latest = versions[-1]
    if bump_level == "major":
        return bump_major(latest)
    if bump_level == "minor":
        return bump_minor(latest)
    return bump_patch(latest)


def ensure_snapshot_exists(paths: ProjectPaths, version: str) -> None:
    """Raise if a snapshot version does not exist."""
    parse_semver(version)
    snapshot_dir = paths.snapshot_version_dir(version)
    if not snapshot_dir.exists():
        raise VersionNotFoundError(f"Snapshot version not found: {version}")
