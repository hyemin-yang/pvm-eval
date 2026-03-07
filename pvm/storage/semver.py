from __future__ import annotations

import re

from pvm.core.errors import InvalidVersionError


SEMVER_PATTERN = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def parse_semver(version: str) -> tuple[int, int, int]:
    """Parse and validate a semantic version string."""
    match = SEMVER_PATTERN.fullmatch(version)
    if not match:
        raise InvalidVersionError(f"Invalid semantic version: {version}")
    major_str, minor_str, patch_str = match.groups()
    return int(major_str), int(minor_str), int(patch_str)


def semver_sort_key(version: str) -> tuple[int, int, int]:
    """Return a sortable key for a semantic version string."""
    return parse_semver(version)


def bump_patch(version: str) -> str:
    """Increment the patch portion of a semantic version string."""
    major, minor, patch = parse_semver(version)
    return f"{major}.{minor}.{patch + 1}"


def bump_minor(version: str) -> str:
    """Increment the minor portion and reset patch to zero."""
    major, minor, _patch = parse_semver(version)
    return f"{major}.{minor + 1}.0"


def bump_major(version: str) -> str:
    """Increment the major portion and reset minor/patch to zero."""
    major, _minor, _patch = parse_semver(version)
    return f"{major + 1}.0.0"
