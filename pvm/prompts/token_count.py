from __future__ import annotations

from pathlib import Path
from typing import Any

import tiktoken
import tiktoken.model

from pvm.core.errors import PVMError
from pvm.core.paths import ProjectPaths
from pvm.prompts.common import ensure_prompt_exists, ensure_prompt_version_exists


def count_tokens(root: Path, prompt_id: str, version: str, model: str) -> dict[str, Any]:
    """Count tokens in a prompt version using the specified model's tokenizer."""
    paths = ProjectPaths(root.resolve())
    ensure_prompt_exists(paths, prompt_id)
    ensure_prompt_version_exists(paths, prompt_id, version)

    try:
        encoding = tiktoken.encoding_for_model(model)
    except KeyError:
        raise PVMError(f"Unsupported model for token counting: {model}")

    version_dir = paths.prompt_version_dir(prompt_id, version)
    text = (version_dir / "prompt.md").read_text(encoding="utf-8")

    return {
        "id": prompt_id,
        "version": version,
        "model": model,
        "token_count": len(encoding.encode(text)),
    }


def list_supported_models() -> list[str]:
    """Return sorted list of models tiktoken supports."""
    return sorted(tiktoken.model.MODEL_TO_ENCODING.keys())
