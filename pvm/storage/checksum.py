from __future__ import annotations

import hashlib
import json
from typing import Any


def normalize_data(value: Any) -> str:
    """Normalize JSON-serializable data into a stable string form."""
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_text(text: str) -> str:
    """Return the SHA-256 digest for a UTF-8 string."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_data(value: Any) -> str:
    """Return the SHA-256 digest for normalized structured data."""
    return sha256_text(normalize_data(value))
