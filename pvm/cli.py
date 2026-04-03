from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer
import yaml

from pvm.core.errors import PVMError
from pvm.project import PVMProject


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, ensure_ascii=False))


def _render_project_tree(project: PVMProject) -> str:
    """Render the project summary as a labeled tree."""
    project_name = project.load_config()["name"]
    prompt_ids = project.list_prompt_ids()
    snapshot_versions = project.list_snapshots()
    if not prompt_ids and not snapshot_versions:
        return f"project: {project_name}"

    lines = [f"project: {project_name}"]
    items: list[tuple[str, str]] = [("prompt", prompt_id) for prompt_id in prompt_ids]
    items.extend(("snapshot", version) for version in snapshot_versions)

    for item_index, (item_type, value) in enumerate(items):
        is_last_item = item_index == len(items) - 1
        item_prefix = "└── " if is_last_item else "├── "

        if item_type == "prompt":
            prompt_id = value
            lines.append(f"{item_prefix}id: {prompt_id}")
            prompt_info = project.get_prompt_info(prompt_id)
            production = prompt_info["production"]["version"] if prompt_info["production"] else None
            versions = project.list_prompt_versions(prompt_id)
            for version_index, version in enumerate(versions):
                is_last_version = version_index == len(versions) - 1
                version_prefix = "    " if is_last_item else "│   "
                branch = "└── " if is_last_version else "├── "
                suffix = " <--- production" if version == production else ""
                lines.append(f"{version_prefix}{branch}version: {version}{suffix}")
            continue

        snapshot_version = value
        lines.append(f"{item_prefix}snapshot: {snapshot_version}")

    return "\n".join(lines)


app = typer.Typer(help="Prompt version management")
snapshot_app = typer.Typer(help="Snapshot operations")
app.add_typer(snapshot_app, name="snapshot")


def _project() -> PVMProject:
    """Return the current working directory project facade."""
    return PVMProject.cwd()


@app.command("check")
def check() -> None:
    """Check project integrity and report missing directories or files."""
    _print_json(_project().check_integrity())


@app.command("init")
def init(name: str = typer.Argument("my-project")) -> None:
    """Initialize a pvm project."""
    _print_json(_project().init(name))


@app.command("destroy")
def destroy(
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
) -> None:
    """Remove the .pvm/ directory tree entirely."""
    if not force:
        confirm = typer.confirm("This will permanently delete the .pvm/ project. Continue?")
        if not confirm:
            raise SystemExit(0)
    _print_json(_project().destroy())


@app.command("reset")
def reset(
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
) -> None:
    """Reset the .pvm/ project to a clean state (same project name, new project id)."""
    if not force:
        confirm = typer.confirm("This will delete all prompts and snapshots. Continue?")
        if not confirm:
            raise SystemExit(0)
    _print_json(_project().reset())


@app.command("add")
def add(
    template: Path,
    minor: bool = typer.Option(False, "--minor", help="Bump the minor version"),
    major: bool = typer.Option(False, "--major", help="Bump the major version"),
) -> None:
    """Add a prompt template as a new immutable version."""
    if minor and major:
        typer.secho("Options --minor and --major are mutually exclusive", fg=typer.colors.RED, err=True)
        raise SystemExit(1)

    bump_level = "patch"
    if major:
        bump_level = "major"
    elif minor:
        bump_level = "minor"

    result = _project().add_prompt(template, bump_level=bump_level)
    if not result["changed"]:
        print("No changes")
        return
    _print_json(result)


@app.command("deploy")
def deploy(
    prompt_id: str = typer.Argument(..., metavar="ID"),
    version: str | None = typer.Argument(None),
) -> None:
    """Deploy a prompt version to production, defaulting to the latest version."""
    result = _project().deploy(prompt_id, version)
    if not result["changed"]:
        if result.get("reason") == "already_deployed":
            print("Already deployed to production")
        else:
            print("Version not found")
        return
    _print_json(result)


@app.command("rollback")
def rollback(prompt_id: str = typer.Argument(..., metavar="ID")) -> None:
    """Rollback a prompt to the previous production version."""
    result = _project().rollback(prompt_id)
    if not result["changed"]:
        print("No rollback target")
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


@app.command("project")
def project() -> None:
    """Show the current project summary as a logical tree."""
    print(_render_project_tree(_project()))


@app.command("template")
def template() -> None:
    """Print the default prompt template stored in the project."""
    print(
        yaml.safe_dump(
            _project().load_template(),
            allow_unicode=True,
            sort_keys=False,
        ).rstrip()
    )


@snapshot_app.command("create")
def snapshot_create(
    minor: bool = typer.Option(False, "--minor", help="Bump the minor snapshot version"),
    major: bool = typer.Option(False, "--major", help="Bump the major snapshot version"),
) -> None:
    """Create a production snapshot."""
    if minor and major:
        typer.secho("Options --minor and --major are mutually exclusive", fg=typer.colors.RED, err=True)
        raise SystemExit(1)

    bump_level = "patch"
    if major:
        bump_level = "major"
    elif minor:
        bump_level = "minor"

    _print_json(_project().create_snapshot(bump_level=bump_level))


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
    try:
        app()
    except PVMError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
