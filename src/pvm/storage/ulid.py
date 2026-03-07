from __future__ import annotations

import os
import time


_CROCKFORD_BASE32 = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _encode_base32(value: int, length: int) -> str:
    """Encode an integer using Crockford base32 with fixed length."""
    chars: list[str] = []
    for _ in range(length):
        chars.append(_CROCKFORD_BASE32[value & 0x1F])
        value >>= 5
    return "".join(reversed(chars))


def generate_ulid() -> str:
    """Generate a ULID string without introducing an extra runtime dependency."""
    timestamp_ms = int(time.time() * 1000)
    randomness = int.from_bytes(os.urandom(10), "big")
    return f"{_encode_base32(timestamp_ms, 10)}{_encode_base32(randomness, 16)}"
