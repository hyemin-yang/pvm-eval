from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from pvm.project import PVMProject


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


app = typer.Typer(help="Prompt version management")
snapshot_app = typer.Typer(help="Snapshot operations")
app.add_typer(snapshot_app, name="snapshot")


def _project() -> PVMProject:
    """Return the current working directory project facade."""
    return PVMProject.cwd()


@app.command("init")
def init(name: str) -> None:
    """Initialize a pvm project."""
    _print_json(_project().init(name))


@app.command("add")
def add(template: Path) -> None:
    """Add a prompt template as a new immutable version."""
    result = _project().add_prompt(template)
    if not result["changed"]:
        print("변경 없음")
        return
    _print_json(result)


@app.command("deploy")
def deploy(prompt_id: str = typer.Argument(..., metavar="ID"), version: str = typer.Argument(...)) -> None:
    """Deploy a prompt version to production."""
    result = _project().deploy(prompt_id, version)
    if not result["changed"]:
        print("없는 버전")
        return
    _print_json(result)


@app.command("rollback")
def rollback(prompt_id: str = typer.Argument(..., metavar="ID")) -> None:
    """Rollback a prompt to the previous production version."""
    result = _project().rollback(prompt_id)
    if not result["changed"]:
        print("되돌릴 기록 없음")
        return
    _print_json(result)


@app.command("get")
def get(
    prompt_id: str = typer.Argument(..., metavar="ID"),
    version: str | None = typer.Option(None, "--version", help="Explicit prompt version"),
) -> None:
    """Read a prompt version or the current production version."""
    _print_json(_project().get_prompt(prompt_id, version=version))


@app.command("diff")
def diff(
    prompt_id: str = typer.Argument(..., metavar="ID"),
    from_version: str = typer.Argument(...),
    to_version: str = typer.Argument(...),
) -> None:
    """Diff two prompt versions."""
    _print_json(_project().diff_prompt(prompt_id, from_version, to_version))


@app.command("list")
def list_command(
    prompt_id: str | None = typer.Option(None, "--id", help="Optional prompt id to list versions for"),
) -> None:
    """List prompt ids or versions for a single prompt."""
    project = _project()
    if prompt_id:
        _print_json(project.list_prompt_versions(prompt_id))
        return
    _print_json(project.list_prompt_ids())


@app.command("id")
def id_command(
    prompt_id: str = typer.Argument(..., metavar="ID"),
    info: bool = typer.Option(False, "--info", help="Show prompt info"),
    list_versions: bool = typer.Option(False, "--list", help="Show prompt versions"),
) -> None:
    """Inspect a prompt id."""
    project = _project()
    if info:
        _print_json(project.get_prompt_info(prompt_id))
        return
    if list_versions:
        _print_json(project.list_prompt_versions(prompt_id))
        return
    _print_json(project.get_prompt(prompt_id))


@app.command("log")
def log(prompt_id: str | None = typer.Option(None, "--id", help="Prompt id")) -> None:
    """Read snapshot or prompt history logs."""
    project = _project()
    if prompt_id:
        history_file = project.paths.prompt_history_file(prompt_id)
    else:
        history_file = project.paths.snapshot_history_file
    if not history_file.exists():
        print("[]")
        return
    print(history_file.read_text(encoding="utf-8").rstrip())


@app.command("tree")
def tree() -> None:
    """Show the current `.pvm/` tree."""
    project = _project()
    for path in sorted(project.paths.project_dir.rglob("*")):
        print(path.relative_to(project.root))


@snapshot_app.command("create")
def snapshot_create() -> None:
    """Create a production snapshot."""
    _print_json(_project().create_snapshot())


@snapshot_app.command("list")
def snapshot_list() -> None:
    """List snapshot versions."""
    _print_json(_project().list_snapshots())


@snapshot_app.command("get")
def snapshot_get(version: str) -> None:
    """Read a snapshot manifest."""
    _print_json(_project().get_snapshot(version))


@snapshot_app.command("read")
def snapshot_read(version: str) -> None:
    """Read a fully expanded snapshot."""
    _print_json(_project().read_snapshot(version))


@snapshot_app.command("diff")
def snapshot_diff(from_version: str, to_version: str) -> None:
    """Diff two snapshots."""
    _print_json(_project().diff_snapshot(from_version, to_version))


def main() -> None:
    """Execute the pvm CLI."""
    app()


if __name__ == "__main__":
    main()
