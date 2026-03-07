from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any

from pvm.core.paths import ProjectPaths
from pvm.prompts.common import ensure_prompt_exists, ensure_prompt_version_exists
from pvm.storage.json_io import load_json


def diff_prompt_versions(
    root: Path, prompt_id: str, from_version: str, to_version: str
) -> dict[str, Any]:
    """Compare two prompt versions and return a summary plus unified diff."""
    paths = ProjectPaths(root.resolve())
    ensure_prompt_exists(paths, prompt_id)
    ensure_prompt_version_exists(paths, prompt_id, from_version)
    ensure_prompt_version_exists(paths, prompt_id, to_version)

    from_dir = paths.prompt_version_dir(prompt_id, from_version)
    to_dir = paths.prompt_version_dir(prompt_id, to_version)

    old_prompt = (from_dir / "prompt.md").read_text(encoding="utf-8")
    new_prompt = (to_dir / "prompt.md").read_text(encoding="utf-8")
    old_lines = old_prompt.splitlines(keepends=True)
    new_lines = new_prompt.splitlines(keepends=True)
    diff_lines = list(
        difflib.unified_diff(
            old_lines,
            new_lines,
            fromfile=f"{from_version}/prompt.md",
            tofile=f"{to_version}/prompt.md",
        )
    )

    old_model = load_json(from_dir / "model_config.json")
    new_model = load_json(to_dir / "model_config.json")
    old_metadata = load_json(from_dir / "metadata.json")
    new_metadata = load_json(to_dir / "metadata.json")

    return {
        "id": prompt_id,
        "from_version": from_version,
        "to_version": to_version,
        "changed": old_prompt != new_prompt or old_model != new_model,
        "prompt_length_delta": len(new_prompt) - len(old_prompt),
        "lines_added": sum(
            1 for line in diff_lines if line.startswith("+") and not line.startswith("+++")
        ),
        "lines_removed": sum(
            1 for line in diff_lines if line.startswith("-") and not line.startswith("---")
        ),
        "model_config_changed": old_model != new_model,
        "checksum_from": old_metadata["template_checksum"],
        "checksum_to": new_metadata["template_checksum"],
        "unified_diff": "".join(diff_lines) if diff_lines else "(no changes)",
    }
