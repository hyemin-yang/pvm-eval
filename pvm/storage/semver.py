from __future__ import annotations


def _parse(version: str) -> tuple[int, int, int]:
    major_str, minor_str, patch_str = version.split(".")
    return int(major_str), int(minor_str), int(patch_str)


def bump_patch(version: str) -> str:
    """Increment the patch portion of a semantic version string."""
    major, minor, patch = _parse(version)
    return f"{major}.{minor}.{patch + 1}"


def bump_minor(version: str) -> str:
    """Increment the minor portion and reset patch to zero."""
    major, minor, _patch = _parse(version)
    return f"{major}.{minor + 1}.0"


def bump_major(version: str) -> str:
    """Increment the major portion and reset minor/patch to zero."""
    major, _minor, _patch = _parse(version)
    return f"{major + 1}.0.0"
