from __future__ import annotations


def bump_patch(version: str) -> str:
    """Increment the patch portion of a semantic version string."""
    major_str, minor_str, patch_str = version.split(".")
    major = int(major_str)
    minor = int(minor_str)
    patch = int(patch_str)
    return f"{major}.{minor}.{patch + 1}"
