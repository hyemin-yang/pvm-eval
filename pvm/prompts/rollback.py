from __future__ import annotations
from pathlib import Path
from typing import Any

from pvm.core.paths import ProjectPaths
from pvm.prompts.common import ensure_prompt_exists
from pvm.storage.history import append_history
from pvm.storage.json_io import dump_json, load_json
from pvm.storage.time import utc_now_iso


def rollback_prompt(root: Path, prompt_id: str) -> dict[str, Any]:
    """Rollback a prompt to the previous production version from history."""
    paths = ProjectPaths(root.resolve())
    ensure_prompt_exists(paths, prompt_id)

    production_file = paths.prompt_production_file(prompt_id)
    if not production_file.exists():
        return {
            "id": prompt_id,
            "changed": False,
            "reason": "no_production_version",
        }

    current = load_json(production_file)
    current_version = current["version"]
    previous_versions: list[str] = current.get("previous_versions", [])

    if not previous_versions:
        return {
            "id": prompt_id,
            "changed": False,
            "reason": "no_rollback_target",
        }

    candidate_version = previous_versions[-1]
    remaining_versions = previous_versions[:-1]

    updated_at = utc_now_iso()
    dump_json(
        production_file,
        {
            "id": prompt_id,
            "version": candidate_version,
            "previous_versions": remaining_versions,
            "updated_at": updated_at,
        },
    )

    history_file = paths.prompt_history_file(prompt_id)
    append_history(
        history_file,
        {
            "ts": updated_at,
            "event": "rollback",
            "id": prompt_id,
            "from_version": current_version,
            "to_version": candidate_version,
        },
    )
    return {
        "id": prompt_id,
        "changed": True,
        "from_version": current_version,
        "to_version": candidate_version,
    }
