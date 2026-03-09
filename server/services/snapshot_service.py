from __future__ import annotations

from typing import Any

from pvm.project import PVMProject
from server.services.project_service import ProjectService


class SnapshotService:
    def __init__(self, project_service: ProjectService) -> None:
        self.ps = project_service

    def _pvm(self, project_id: str) -> PVMProject:
        return self.ps._get_pvm(project_id)

    def create(self, project_id: str, bump_level: str = "patch") -> dict[str, Any]:
        return self._pvm(project_id).create_snapshot(bump_level=bump_level)

    def list(self, project_id: str) -> list[str]:
        return self._pvm(project_id).list_snapshots()

    def get(self, project_id: str, version: str) -> dict[str, Any]:
        return self._pvm(project_id).get_snapshot(version)

    def read(self, project_id: str, version: str) -> dict[str, Any]:
        return self._pvm(project_id).read_snapshot(version)

    def diff(self, project_id: str, from_ver: str, to_ver: str) -> dict[str, Any]:
        return self._pvm(project_id).diff_snapshot(from_ver, to_ver)
