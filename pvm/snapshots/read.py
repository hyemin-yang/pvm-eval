from __future__ import annotations

from pathlib import Path
from typing import Any

from pvm.core.paths import ProjectPaths
from pvm.snapshots.get import get_snapshot
from pvm.storage.json_io import load_json


def read_snapshot(root: Path, version: str) -> dict[str, Any]:
    """Read a snapshot with full prompt contents from its own stored files."""
    paths = ProjectPaths(root.resolve())
    manifest = get_snapshot(root, version)
    prompts: dict[str, Any] = {}

    for prompt_id, prompt_info in manifest["prompts"].items():
        prompt_dir = paths.snapshot_prompt_dir(version, prompt_id)
        prompt_text = (prompt_dir / "prompt.md").read_text(encoding="utf-8")
        model_config = load_json(prompt_dir / "model_config.json")
        metadata = load_json(prompt_dir / "metadata.json")

        prompts[prompt_id] = {
            "version": prompt_info["version"],
            "llm": model_config,
            "prompt": prompt_text,
            "metadata": metadata,
        }

    return {
        "version": manifest["version"],
        "created_at": manifest["created_at"],
        "prompt_count": manifest["prompt_count"],
        "prompts": prompts,
    }
