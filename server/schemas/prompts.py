from __future__ import annotations

from pydantic import BaseModel


class AddPromptRequest(BaseModel):
    yaml_content: str
    bump_level: str = "patch"


class DeployRequest(BaseModel):
    version: str | None = None
