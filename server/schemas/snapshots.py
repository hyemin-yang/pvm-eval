from __future__ import annotations

from pydantic import BaseModel


class CreateSnapshotRequest(BaseModel):
    bump_level: str = "patch"
