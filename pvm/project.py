from __future__ import annotations

from pathlib import Path
from typing import Any

from pvm.config.check_integrity import check_integrity
from pvm.config.destroy_project import destroy_project
from pvm.config.init_project import init_project
from pvm.config.reset_project import reset_project
from pvm.config.load_config import load_config
from pvm.config.load_template import load_template
from pvm.core.errors import NotValidProjectError
from pvm.core.paths import ProjectPaths
from pvm.prompts.add import add_prompt
from pvm.prompts.token_count import count_tokens as count_prompt_tokens, list_supported_models
from pvm.prompts.delete import delete_prompt
from pvm.prompts.deploy import deploy_prompt
from pvm.prompts.diff import diff_prompt_versions
from pvm.prompts.get import get_prompt
from pvm.prompts.get_info import get_prompt_info
from pvm.prompts.list_ids import list_prompt_ids, list_prompt_versions_for_id
from pvm.prompts.rollback import rollback_prompt
from pvm.snapshots.create import create_snapshot
from pvm.snapshots.diff import diff_snapshots
from pvm.snapshots.export import export_snapshot
from pvm.snapshots.get import get_snapshot
from pvm.snapshots.list import list_snapshots
from pvm.snapshots.read import read_snapshot


class PVMProject:
    """Facade for project-scoped pvm operations."""

    def __init__(self, root: Path | str):
        """Bind the project facade to a filesystem root."""
        root = Path(root)

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

    def check_integrity(self) -> dict[str, Any]:
        """Check which required directories and files are missing from `.pvm/`."""
        return check_integrity(self.root)

    def require_valid(self) -> None:
        """Raise if the current root is not an initialized pvm project."""
        if not self.is_valid():
            if self.paths.project_dir.exists():
                msg = (
                    f"Project is corrupted: {self.root}\n"
                    "Run integrity check to inspect missing items, "
                    "or reset the project to re-initialize."
                )
            else:
                msg = (
                    f"No pvm project found: {self.root}\n"
                    "Initialize a new project first."
                )
            raise NotValidProjectError(msg)

    def init(self, name: str = "my-project") -> dict[str, Any]:
        """Initialize a new project in the current root."""
        return init_project(self.root, name=name)

    def destroy(self) -> dict[str, Any]:
        """Remove the `.pvm/` directory tree entirely."""
        self.require_valid()
        return destroy_project(self.root)

    def reset(self) -> dict[str, Any]:
        """Reset the project by destroying and re-initializing with the same name."""
        self.require_valid()
        return reset_project(self.root)

    def load_config(self) -> dict[str, Any]:
        """Load `.pvm/config.yaml` for the current project."""
        self.require_valid()
        return load_config(self.root)

    def load_template(self) -> dict[str, Any]:
        """Load the default prompt template stored in project settings."""
        self.require_valid()
        return load_template(self.root)

    def add_prompt(
        self, template_path: str | Path, bump_level: str = "patch"
    ) -> dict[str, Any]:
        """Create a new prompt version from a YAML template file."""
        self.require_valid()
        return add_prompt(self.root, Path(template_path), bump_level=bump_level)

    def list_prompt_ids(self) -> list[str]:
        """List all prompt ids in the current project."""
        self.require_valid()
        return list_prompt_ids(self.root)

    def list_prompt_versions(self, prompt_id: str) -> list[str]:
        """List all versions for a single prompt id."""
        self.require_valid()
        return list_prompt_versions_for_id(self.root, prompt_id)

    def get_prompt(self, prompt_id: str, version: str | None = None) -> dict[str, Any]:
        """Read a prompt by explicit version or current production version."""
        self.require_valid()
        return get_prompt(self.root, prompt_id, version=version)

    def get_prompt_info(self, prompt_id: str) -> dict[str, Any]:
        """Read stable prompt metadata and version summary."""
        self.require_valid()
        return get_prompt_info(self.root, prompt_id)

    def delete_prompt(self, prompt_id: str) -> dict[str, Any]:
        """Delete a prompt and all its versions entirely."""
        self.require_valid()
        return delete_prompt(self.root, prompt_id)

    def deploy(self, prompt_id: str, version: str | None = None) -> dict[str, Any]:
        """Promote a prompt version to production, defaulting to the latest version."""
        self.require_valid()
        return deploy_prompt(self.root, prompt_id, version)

    def rollback(self, prompt_id: str) -> dict[str, Any]:
        """Rollback a prompt to the previous production version."""
        self.require_valid()
        return rollback_prompt(self.root, prompt_id)

    def diff_prompt(
        self, prompt_id: str, from_version: str, to_version: str
    ) -> dict[str, Any]:
        """Compare two versions of the same prompt."""
        self.require_valid()
        return diff_prompt_versions(self.root, prompt_id, from_version, to_version)

    def count_tokens(self, prompt_id: str, version: str, model: str) -> dict[str, Any]:
        """Count tokens in a prompt version using the specified model's tokenizer."""
        self.require_valid()
        return count_prompt_tokens(self.root, prompt_id, version, model)

    def list_token_models(self) -> list[str]:
        """List models supported for token counting."""
        return list_supported_models()

    def create_snapshot(self, bump_level: str = "patch") -> dict[str, Any]:
        """Create a snapshot from the current production prompt set."""
        self.require_valid()
        return create_snapshot(self.root, bump_level=bump_level)

    def list_snapshots(self) -> list[str]:
        """List snapshot versions in the current project."""
        self.require_valid()
        return list_snapshots(self.root)

    def get_snapshot(self, version: str) -> dict[str, Any]:
        """Load a snapshot manifest by version."""
        self.require_valid()
        return get_snapshot(self.root, version)

    def read_snapshot(self, version: str) -> dict[str, Any]:
        """Expand a snapshot into the prompt contents it references."""
        self.require_valid()
        return read_snapshot(self.root, version)

    def export_snapshot(self, version: str, output_path: str | Path | None = None) -> dict[str, Any]:
        """Export a snapshot version as a zip file."""
        self.require_valid()
        return export_snapshot(self.root, version, output_path)

    def diff_snapshot(self, from_version: str, to_version: str) -> dict[str, Any]:
        """Compare two snapshots by prompt membership and version mapping."""
        self.require_valid()
        return diff_snapshots(self.root, from_version, to_version)
