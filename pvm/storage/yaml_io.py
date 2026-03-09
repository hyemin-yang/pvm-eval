from __future__ import annotations

import locale
from pathlib import Path
from typing import Any

import yaml


def _decode_bytes(raw: bytes) -> str:
    """Decode raw bytes to str, handling all common BOM variants and falling back to the system encoding."""
    # UTF-32 BOM must be checked before UTF-16 (they share a prefix)
    if raw.startswith(b"\x00\x00\xfe\xff"):
        return raw.decode("utf-32-be")
    if raw.startswith(b"\xff\xfe\x00\x00"):
        return raw.decode("utf-32-le")
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        return raw.decode("utf-16")
    if raw.startswith(b"\xef\xbb\xbf"):
        return raw.decode("utf-8-sig")
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode(locale.getpreferredencoding(False))


def load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML mapping from disk, tolerating any encoding."""
    text = _decode_bytes(path.read_bytes())
    data = yaml.safe_load(text) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Expected YAML mapping in {path}")
    return data


def dump_yaml(path: Path, data: Any) -> None:
    """Write YAML to disk while preserving key order."""
    with path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(
            data,
            handle,
            allow_unicode=True,
            sort_keys=False,
        )
