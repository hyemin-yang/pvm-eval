from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from pvm.core.paths import ProjectPaths
from pvm.config.init_project import _BUNDLED_SKILLS_DIR


def destroy_project(root: Path) -> dict[str, Any]:
    """Remove the `.pvm/` directory tree entirely."""
    paths = ProjectPaths(root.resolve())

    shutil.rmtree(paths.project_dir)
    _remove_installed_claude_skills(paths.root)

    return {"destroyed": True, "root": str(paths.root)}


def _remove_installed_claude_skills(root: Path) -> None:
    """Remove Claude skills that were installed by `pvm init`.

    Only removes skill directories that correspond to bundled pvm skills.
    Leaves unrelated `.claude` contents untouched.
    """
    if not _BUNDLED_SKILLS_DIR.exists():
        return

    skills_dir = root / ".claude" / "skills"
    if not skills_dir.exists():
        return

    for skill_src in _BUNDLED_SKILLS_DIR.iterdir():
        if not skill_src.is_dir():
            continue
        skill_path = skills_dir / skill_src.name
        if skill_path.is_symlink() or skill_path.is_file():
            skill_path.unlink(missing_ok=True)
        elif skill_path.exists():
            shutil.rmtree(skill_path)

    _remove_dir_if_empty(skills_dir)
    _remove_dir_if_empty(root / ".claude")


def _remove_dir_if_empty(path: Path) -> None:
    if path.exists() and path.is_dir() and not any(path.iterdir()):
        path.rmdir()
