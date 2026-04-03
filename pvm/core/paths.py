from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ProjectPaths:
    """Centralized path access for the `.pvm/` project layout."""

    root: Path

    @property
    def project_dir(self) -> Path:
        return self.root / ".pvm"

    @property
    def config_file(self) -> Path:
        return self.project_dir / "config.yaml"

    @property
    def settings_dir(self) -> Path:
        return self.project_dir / "settings"

    @property
    def template_file(self) -> Path:
        return self.settings_dir / "template.yaml"

    @property
    def prompts_dir(self) -> Path:
        return self.project_dir / "prompts"

    def prompt_dir(self, prompt_id: str) -> Path:
        return self.prompts_dir / prompt_id

    def prompt_info_file(self, prompt_id: str) -> Path:
        return self.prompt_dir(prompt_id) / "info.yaml"

    def prompt_production_file(self, prompt_id: str) -> Path:
        return self.prompt_dir(prompt_id) / "production.json"

    def prompt_history_file(self, prompt_id: str) -> Path:
        return self.prompt_dir(prompt_id) / "history.jsonl"

    def prompt_versions_dir(self, prompt_id: str) -> Path:
        return self.prompt_dir(prompt_id) / "versions"

    def prompt_version_dir(self, prompt_id: str, version: str) -> Path:
        return self.prompt_versions_dir(prompt_id) / version

    def prompt_version_file(self, prompt_id: str, version: str, filename: str) -> Path:
        return self.prompt_version_dir(prompt_id, version) / filename

    @property
    def snapshots_dir(self) -> Path:
        return self.project_dir / "snapshots"

    @property
    def snapshot_versions_dir(self) -> Path:
        return self.snapshots_dir / "versions"

    def snapshot_version_dir(self, version: str) -> Path:
        return self.snapshot_versions_dir / version

    def snapshot_manifest_file(self, version: str) -> Path:
        return self.snapshot_version_dir(version) / "manifest.json"

    def snapshot_prompts_dir(self, version: str) -> Path:
        return self.snapshot_version_dir(version) / "prompts"

    def snapshot_prompt_dir(self, version: str, prompt_id: str) -> Path:
        return self.snapshot_prompts_dir(version) / prompt_id

    @property
    def snapshot_history_file(self) -> Path:
        return self.snapshots_dir / "history.jsonl"
