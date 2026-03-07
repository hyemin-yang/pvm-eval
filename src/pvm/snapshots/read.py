from __future__ import annotations

from pathlib import Path
from typing import Any

from pvm.core.paths import ProjectPaths
from pvm.prompts.get import get_prompt
from pvm.snapshots.get import get_snapshot


def read_snapshot(root: Path, version: str) -> dict[str, Any]:
    """Expand a snapshot manifest into the concrete prompt contents it references."""
    paths = ProjectPaths(root.resolve())
    _ = paths  # keep root/path normalization symmetric with other snapshot functions
    manifest = get_snapshot(root, version)
    prompts: dict[str, Any] = {}
    for prompt_id, prompt_info in manifest["prompts"].items():
        prompt_version = prompt_info["version"]
        resolved = get_prompt(root, prompt_id, version=prompt_version)
        prompts[prompt_id] = {
            "version": prompt_version,
            "llm": resolved["llm"],
            "prompt": resolved["prompt"],
            "metadata": resolved["metadata"],
        }
    return {
        "version": manifest["version"],
        "created_at": manifest["created_at"],
        "prompt_count": manifest["prompt_count"],
        "prompts": prompts,
    }
