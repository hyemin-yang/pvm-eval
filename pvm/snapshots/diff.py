from __future__ import annotations

from pathlib import Path
from typing import Any

from pvm.snapshots.get import get_snapshot


def diff_snapshots(root: Path, from_version: str, to_version: str) -> dict[str, Any]:
    """Compare two snapshot manifests at the prompt id/version level."""
    old_snapshot = get_snapshot(root, from_version)
    new_snapshot = get_snapshot(root, to_version)
    old_prompts = old_snapshot["prompts"]
    new_prompts = new_snapshot["prompts"]

    old_ids = set(old_prompts)
    new_ids = set(new_prompts)

    added_ids = sorted(new_ids - old_ids)
    removed_ids = sorted(old_ids - new_ids)
    changed_ids = []

    for prompt_id in sorted(old_ids & new_ids):
        old_prompt = old_prompts[prompt_id]
        new_prompt = new_prompts[prompt_id]
        if old_prompt["version"] != new_prompt["version"]:
            changed_ids.append(
                {
                    "id": prompt_id,
                    "from_version": old_prompt["version"],
                    "to_version": new_prompt["version"],
                }
            )

    return {
        "from_version": from_version,
        "to_version": to_version,
        "added_ids": added_ids,
        "removed_ids": removed_ids,
        "changed_ids": changed_ids,
    }
