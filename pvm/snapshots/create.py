from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from pvm.core.paths import ProjectPaths
from pvm.prompts.common import list_prompt_versions, read_prompt_metadata
from pvm.prompts.list_ids import list_prompt_ids
from pvm.snapshots.common import get_next_snapshot_version
from pvm.storage.history import append_history
from pvm.storage.json_io import dump_json, load_json
from pvm.storage.time import utc_now_iso


def create_snapshot(root: Path, bump_level: str = "patch") -> dict[str, Any]:
    """Create a snapshot of the current production prompt set."""
    paths = ProjectPaths(root.resolve())
    version = get_next_snapshot_version(paths, bump_level=bump_level)
    created_at = utc_now_iso()
    prompts: dict[str, Any] = {}

    snapshot_prompts_dir = paths.snapshot_prompts_dir(version)
    snapshot_prompts_dir.mkdir(parents=True, exist_ok=True)

    for prompt_id in list_prompt_ids(root):
        production_file = paths.prompt_production_file(prompt_id)
        if not production_file.exists():
            continue
        production = load_json(production_file)
        prompt_version = production["version"]
        metadata = read_prompt_metadata(paths, prompt_id, prompt_version)

        # Copy prompt files to snapshot
        src_dir = paths.prompt_version_dir(prompt_id, prompt_version)
        dst_dir = paths.snapshot_prompt_dir(version, prompt_id)
        dst_dir.mkdir(parents=True, exist_ok=True)

        for filename in ("prompt.md", "model_config.json", "metadata.json"):
            src_file = src_dir / filename
            if src_file.exists():
                shutil.copy2(src_file, dst_dir / filename)

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
    dump_json(paths.snapshot_manifest_file(version), manifest)
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
