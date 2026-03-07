from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def append_history(path: Path, record: dict[str, Any]) -> None:
    """Append a single JSON record to a JSONL history file."""
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False))
        handle.write("\n")
