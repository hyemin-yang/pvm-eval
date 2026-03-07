from __future__ import annotations

from pathlib import Path
from typing import Any

from pvm.config.init_project import init_project
from pvm.config.load_config import load_config
from pvm.config.load_template import load_template
from pvm.core.errors import NotValidProjectError
from pvm.core.paths import ProjectPaths


class PVMProject:
    """Facade for project-scoped pvm operations."""

    def __init__(self, root: Path):
        """Bind the project facade to a filesystem root."""
        self.root = root.resolve()
        self.paths = ProjectPaths(self.root)

    @classmethod
    def cwd(cls) -> "PVMProject":
        """Create a project facade for the current working directory."""
        return cls(Path.cwd())

    def is_valid(self) -> bool:
        """Return whether the current root contains the minimum `.pvm/` layout."""
        required_dirs = (
            self.paths.project_dir,
            self.paths.settings_dir,
            self.paths.prompts_dir,
            self.paths.snapshots_dir,
            self.paths.snapshot_versions_dir,
        )
        required_files = (
            self.paths.config_file,
            self.paths.template_file,
            self.paths.snapshot_history_file,
        )
        return all(path.exists() and path.is_dir() for path in required_dirs) and all(
            path.exists() and path.is_file() for path in required_files
        )

    def require_valid(self) -> None:
        """Raise if the current root is not an initialized pvm project."""
        if not self.is_valid():
            raise NotValidProjectError(
                f"Current directory is not a valid pvm project: {self.root}"
            )

    def init(self, name: str) -> dict[str, Any]:
        """Initialize a new project in the current root."""
        return init_project(self.root, name=name)

    def load_config(self) -> dict[str, Any]:
        """Load `.pvm/config.yaml` for the current project."""
        self.require_valid()
        return load_config(self.root)

    def load_template(self) -> dict[str, Any]:
        """Load the default prompt template stored in project settings."""
        self.require_valid()
        return load_template(self.root)
