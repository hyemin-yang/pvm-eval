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

    @property
    def snapshots_dir(self) -> Path:
        return self.project_dir / "snapshots"

    @property
    def snapshot_versions_dir(self) -> Path:
        return self.snapshots_dir / "versions"

    @property
    def snapshot_history_file(self) -> Path:
        return self.snapshots_dir / "history.jsonl"
