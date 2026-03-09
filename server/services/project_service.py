from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from pvm.project import PVMProject
from pvm.storage.time import utc_now_iso
from pvm.storage.ulid import generate_ulid
from server.config import STORAGE_ROOT
from server.db.models import ProjectModel


class ProjectNotFoundError(Exception):
    pass


class ProjectService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.storage_root = STORAGE_ROOT

    def _get_row(self, project_id: str) -> ProjectModel:
        row = self.db.query(ProjectModel).filter_by(id=project_id).first()
        if not row:
            raise ProjectNotFoundError(f"Project not found: {project_id}")
        return row

    def _get_pvm(self, project_id: str) -> PVMProject:
        row = self._get_row(project_id)
        return PVMProject(Path(row.storage_path))

    def create(self, name: str) -> dict[str, Any]:
        project_id = generate_ulid()
        storage_path = self.storage_root / project_id
        storage_path.mkdir(parents=True, exist_ok=True)

        pvm = PVMProject(storage_path)
        result = pvm.init(name)

        row = ProjectModel(
            id=project_id,
            name=name,
            storage_path=str(storage_path),
            created_at=utc_now_iso(),
        )
        self.db.add(row)
        self.db.commit()
        return {**result, "server_project_id": project_id}

    def list(self) -> list[dict[str, Any]]:
        rows = self.db.query(ProjectModel).all()
        result = []
        for r in rows:
            try:
                pvm = PVMProject(Path(r.storage_path))
                prompt_count = len(pvm.list_prompt_ids())
            except Exception:
                prompt_count = 0
            result.append({
                "id": r.id,
                "name": r.name,
                "created_at": r.created_at,
                "prompt_count": prompt_count,
            })
        return result

    def get(self, project_id: str) -> dict[str, Any]:
        row = self._get_row(project_id)
        pvm = self._get_pvm(project_id)

        prompt_ids = pvm.list_prompt_ids()
        prompts = []
        for pid in prompt_ids:
            try:
                prompts.append(pvm.get_prompt_info(pid))
            except Exception:
                prompts.append({"id": pid})

        return {
            "id": project_id,
            "name": row.name,
            "created_at": row.created_at,
            "config": pvm.load_config(),
            "prompts": prompts,
            "snapshots": pvm.list_snapshots(),
        }

    def delete(self, project_id: str) -> None:
        row = self._get_row(project_id)
        shutil.rmtree(row.storage_path, ignore_errors=True)
        self.db.delete(row)
        self.db.commit()
