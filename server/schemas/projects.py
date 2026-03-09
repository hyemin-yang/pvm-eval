from __future__ import annotations

from pydantic import BaseModel


class CreateProjectRequest(BaseModel):
    name: str = "my-project"
