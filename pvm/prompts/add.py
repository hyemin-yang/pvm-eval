from __future__ import annotations

from pathlib import Path
from typing import Any

from pvm.core.paths import ProjectPaths
from pvm.prompts.common import (
    get_next_prompt_version,
    load_prompt_template,
    read_prompt_metadata,
)
from pvm.storage.checksum import sha256_data
from pvm.storage.history import append_history
from pvm.storage.json_io import dump_json, write_text
from pvm.storage.semver import semver_sort_key
from pvm.storage.time import utc_now_iso
from pvm.storage.yaml_io import dump_yaml


def add_prompt(root: Path, template_path: Path, bump_level: str = "patch") -> dict[str, Any]:
    """Store a prompt YAML template as a new immutable version artifact."""
    resolved_root = root.resolve()
    resolved_template_path = template_path.resolve()
    paths = ProjectPaths(resolved_root)
    template = load_prompt_template(resolved_template_path)
    prompt_id = template["id"]
    versions_dir = paths.prompt_versions_dir(prompt_id)
    history_file = paths.prompt_history_file(prompt_id)
    info_file = paths.prompt_info_file(prompt_id)

    versions_dir.mkdir(parents=True, exist_ok=True)
    if not history_file.exists():
        write_text(history_file, "")

    existing_versions = [path.name for path in versions_dir.iterdir() if path.is_dir()]
    next_version = get_next_prompt_version(
        paths,
        prompt_id,
        bump_level=bump_level,
        versions=existing_versions,
    )
    checksum_payload = {
        "prompt": template["prompt"],
        "llm": template["llm"],
        "description": template.get("description"),
        "author": template.get("author"),
    }
    template_checksum = sha256_data(checksum_payload)

    if existing_versions:
        latest_version = sorted(existing_versions, key=semver_sort_key)[-1]
        latest_metadata = read_prompt_metadata(paths, prompt_id, latest_version)
        if latest_metadata["template_checksum"] == template_checksum:
            return {
                "id": prompt_id,
                "version": latest_version,
                "changed": False,
                "reason": "no_changes",
            }

    version_dir = paths.prompt_version_dir(prompt_id, next_version)
    version_dir.mkdir(parents=True, exist_ok=False)

    created_at = utc_now_iso()
    prompt_checksum = sha256_data(template["prompt"])
    model_config_checksum = sha256_data(template["llm"])

    write_text(paths.prompt_version_file(prompt_id, next_version, "prompt.md"), template["prompt"])
    dump_json(paths.prompt_version_file(prompt_id, next_version, "model_config.json"), template["llm"])
    dump_yaml(paths.prompt_version_file(prompt_id, next_version, "template.yaml"), template)
    dump_json(
        paths.prompt_version_file(prompt_id, next_version, "metadata.json"),
        {
            "id": prompt_id,
            "version": next_version,
            "description": template.get("description", ""),
            "author": template.get("author", ""),
            "created_at": created_at,
            "source_file": _source_file_value(resolved_root, resolved_template_path),
            "prompt_checksum": prompt_checksum,
            "model_config_checksum": model_config_checksum,
            "template_checksum": template_checksum,
        },
    )

    if not info_file.exists():
        dump_yaml(
            info_file,
            {
                "id": prompt_id,
                "description": template.get("description", ""),
                "author": template.get("author", ""),
                "created_at": created_at,
            },
        )

    append_history(
        history_file,
        {
            "ts": created_at,
            "event": "add",
            "id": prompt_id,
            "version": next_version,
            "template_checksum": template_checksum,
        },
    )

    return {
        "id": prompt_id,
        "version": next_version,
        "changed": True,
    }


def _source_file_value(root: Path, template_path: Path) -> str:
    """Store a stable source file reference for metadata."""
    try:
        return str(template_path.relative_to(root))
    except ValueError:
        return template_path.name
