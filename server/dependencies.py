from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from server.db.session import get_db
from server.services.project_service import ProjectService
from server.services.prompt_service import PromptService
from server.services.snapshot_service import SnapshotService


def get_project_service(db: Session = Depends(get_db)) -> ProjectService:
    return ProjectService(db)


def get_prompt_service(ps: ProjectService = Depends(get_project_service)) -> PromptService:
    return PromptService(ps)


def get_snapshot_service(ps: ProjectService = Depends(get_project_service)) -> SnapshotService:
    return SnapshotService(ps)
