from __future__ import annotations

from pathlib import Path
from typing import Any

from pvm.core.paths import ProjectPaths
from pvm.prompts.common import ensure_prompt_exists, list_prompt_versions
from pvm.storage.semver import parse_semver
from pvm.storage.history import append_history
from pvm.storage.json_io import dump_json, load_json
from pvm.storage.time import utc_now_iso


def deploy_prompt(root: Path, prompt_id: str, version: str | None = None) -> dict[str, Any]:
    """Point a prompt's production pointer at a specific version."""
    paths = ProjectPaths(root.resolve())
    ensure_prompt_exists(paths, prompt_id)

    target_version = version
    if target_version is None:
        versions = list_prompt_versions(paths, prompt_id)
        if not versions:
            return {
                "id": prompt_id,
                "version": None,
                "changed": False,
                "reason": "version_not_found",
            }
        target_version = versions[-1]
    else:
        parse_semver(target_version)

    version_dir = paths.prompt_version_dir(prompt_id, target_version)
    if not version_dir.exists():
        return {
            "id": prompt_id,
            "version": target_version,
            "changed": False,
            "reason": "version_not_found",
        }

    production_file = paths.prompt_production_file(prompt_id)
    current = load_json(production_file) if production_file.exists() else None
    if current and current["version"] == target_version:
        return {
            "id": prompt_id,
            "version": target_version,
            "changed": False,
            "reason": "already_deployed",
        }

    updated_at = utc_now_iso()

    previous_versions: list[str] = []
    if current:
        previous_versions = current.get("previous_versions", [])
        previous_versions = [*previous_versions, current["version"]]

    dump_json(
        production_file,
        {
            "id": prompt_id,
            "version": target_version,
            "previous_versions": previous_versions,
            "updated_at": updated_at,
        },
    )
    append_history(
        paths.prompt_history_file(prompt_id),
        {
            "ts": updated_at,
            "event": "deploy",
            "id": prompt_id,
            "from_version": current["version"] if current else None,
            "to_version": target_version,
        },
    )
    return {
        "id": prompt_id,
        "version": target_version,
        "changed": True,
        "from_version": current["version"] if current else None,
    }
