from __future__ import annotations

from pathlib import Path
from typing import Any

from pvm.core.paths import ProjectPaths
from pvm.prompts.common import list_prompt_versions, read_prompt_metadata
from pvm.prompts.list_ids import list_prompt_ids
from pvm.snapshots.common import get_next_snapshot_version
from pvm.storage.history import append_history
from pvm.storage.json_io import dump_json, load_json
from pvm.storage.time import utc_now_iso


def create_snapshot(root: Path) -> dict[str, Any]:
    """Create a snapshot of the current production prompt set."""
    paths = ProjectPaths(root.resolve())
    version = get_next_snapshot_version(paths)
    created_at = utc_now_iso()
    prompts: dict[str, Any] = {}

    for prompt_id in list_prompt_ids(root):
        production_file = paths.prompt_production_file(prompt_id)
        if not production_file.exists():
            continue
        production = load_json(production_file)
        prompt_version = production["version"]
        metadata = read_prompt_metadata(paths, prompt_id, prompt_version)
        prompts[prompt_id] = {
            "version": prompt_version,
            "prompt_checksum": metadata["prompt_checksum"],
            "model_config_checksum": metadata["model_config_checksum"],
        }

    manifest = {
        "version": version,
        "created_at": created_at,
        "prompt_count": len(prompts),
        "prompts": prompts,
    }
    dump_json(paths.snapshot_versions_dir / f"{version}.json", manifest)
    append_history(
        paths.snapshot_history_file,
        {
            "ts": created_at,
            "event": "create",
            "version": version,
            "prompt_count": len(prompts),
        },
    )
    return manifest
