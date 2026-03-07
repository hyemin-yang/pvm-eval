from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pvm.core.errors import (
    InvalidPromptTemplateError,
    PromptNotFoundError,
    VersionNotFoundError,
)
from pvm.core.paths import ProjectPaths
from pvm.storage.json_io import load_json
from pvm.storage.semver import bump_major, bump_minor, bump_patch, parse_semver, semver_sort_key
from pvm.storage.yaml_io import load_yaml


ID_PATTERN = re.compile(r"^[^\s/]+$")
INITIAL_VERSION = "0.1.0"
BUMP_LEVELS = {"patch", "minor", "major"}


def validate_prompt_id(prompt_id: str) -> None:
    """Validate the prompt id against the current MVP constraints."""
    if not prompt_id or not ID_PATTERN.match(prompt_id):
        raise InvalidPromptTemplateError(
            "Prompt id must be non-empty and cannot contain whitespace or '/'."
        )


def load_prompt_template(template_path: Path) -> dict[str, Any]:
    """Load and validate a prompt YAML template from disk."""
    data = load_yaml(template_path)
    for field in ("id", "llm", "prompt"):
        if not data.get(field):
            raise InvalidPromptTemplateError(
                f"Prompt template is missing required field: {field}"
            )
    validate_prompt_id(data["id"])
    if not isinstance(data["llm"], dict):
        raise InvalidPromptTemplateError("Prompt template field 'llm' must be a mapping.")
    if not isinstance(data["prompt"], str):
        raise InvalidPromptTemplateError("Prompt template field 'prompt' must be a string.")
    return data


def ensure_prompt_exists(paths: ProjectPaths, prompt_id: str) -> None:
    """Raise if the given prompt id does not exist in the project."""
    if not paths.prompt_dir(prompt_id).exists():
        raise PromptNotFoundError(f"Prompt not found: {prompt_id}")


def ensure_prompt_version_exists(paths: ProjectPaths, prompt_id: str, version: str) -> None:
    """Raise if the given prompt version does not exist."""
    parse_semver(version)
    version_dir = paths.prompt_version_dir(prompt_id, version)
    if not version_dir.exists():
        raise VersionNotFoundError(f"Prompt version not found: {prompt_id}@{version}")


def list_prompt_versions(paths: ProjectPaths, prompt_id: str) -> list[str]:
    """Return prompt versions sorted by semantic version."""
    ensure_prompt_exists(paths, prompt_id)
    versions_dir = paths.prompt_versions_dir(prompt_id)
    if not versions_dir.exists():
        return []
    versions = [path.name for path in versions_dir.iterdir() if path.is_dir()]
    return sorted(versions, key=semver_sort_key)


def get_next_prompt_version(
    paths: ProjectPaths,
    prompt_id: str,
    bump_level: str = "patch",
    versions: list[str] | None = None,
) -> str:
    """Compute the next prompt version using the requested semver bump level."""
    if bump_level not in BUMP_LEVELS:
        raise ValueError(f"Unsupported bump level: {bump_level}")
    prompt_dir = paths.prompt_dir(prompt_id)
    if not prompt_dir.exists():
        return INITIAL_VERSION
    known_versions = list_prompt_versions(paths, prompt_id) if versions is None else sorted(
        versions, key=semver_sort_key
    )
    if not known_versions:
        return INITIAL_VERSION
    latest = known_versions[-1]
    if bump_level == "major":
        return bump_major(latest)
    if bump_level == "minor":
        return bump_minor(latest)
    return bump_patch(latest)


def read_prompt_metadata(paths: ProjectPaths, prompt_id: str, version: str) -> dict[str, Any]:
    """Read metadata for a specific prompt version."""
    return load_json(paths.prompt_version_file(prompt_id, version, "metadata.json"))
