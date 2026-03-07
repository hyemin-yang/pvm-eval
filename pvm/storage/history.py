from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def append_history(path: Path, record: dict[str, Any]) -> None:
    """Append a single JSON record to a JSONL history file."""
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False))
        handle.write("\n")


def read_history(path: Path) -> list[dict[str, Any]]:
    """Read a JSONL history file into a list of records."""
    if not path.exists():
        return []

    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records
