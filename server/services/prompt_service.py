from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from pvm.project import PVMProject
from server.services.project_service import ProjectService


class PromptService:
    def __init__(self, project_service: ProjectService) -> None:
        self.ps = project_service

    def _pvm(self, project_id: str) -> PVMProject:
        return self.ps._get_pvm(project_id)

    def add(self, project_id: str, yaml_content: str, bump_level: str = "patch") -> dict[str, Any]:
        pvm = self._pvm(project_id)
        with tempfile.NamedTemporaryFile(
            suffix=".yaml", delete=False, mode="w", encoding="utf-8"
        ) as f:
            f.write(yaml_content)
            tmp = Path(f.name)
        try:
            return pvm.add_prompt(tmp, bump_level=bump_level)
        finally:
            tmp.unlink(missing_ok=True)

    def list_ids(self, project_id: str) -> list[str]:
        return self._pvm(project_id).list_prompt_ids()

    def list_versions(self, project_id: str, prompt_id: str) -> list[str]:
        return self._pvm(project_id).list_prompt_versions(prompt_id)

    def get(self, project_id: str, prompt_id: str, version: str | None = None) -> dict[str, Any]:
        return self._pvm(project_id).get_prompt(prompt_id, version=version)

    def get_info(self, project_id: str, prompt_id: str) -> dict[str, Any]:
        return self._pvm(project_id).get_prompt_info(prompt_id)

    def deploy(self, project_id: str, prompt_id: str, version: str | None = None) -> dict[str, Any]:
        return self._pvm(project_id).deploy(prompt_id, version)

    def rollback(self, project_id: str, prompt_id: str) -> dict[str, Any]:
        return self._pvm(project_id).rollback(prompt_id)

    def diff(self, project_id: str, prompt_id: str, from_ver: str, to_ver: str) -> dict[str, Any]:
        return self._pvm(project_id).diff_prompt(prompt_id, from_ver, to_ver)

    def get_log(self, project_id: str, prompt_id: str) -> list[dict[str, Any]]:
        pvm = self._pvm(project_id)
        history_file = pvm.paths.prompt_history_file(prompt_id)
        if not history_file.exists():
            return []
        lines = history_file.read_text(encoding="utf-8").strip().splitlines()
        return [json.loads(line) for line in lines if line.strip()]
