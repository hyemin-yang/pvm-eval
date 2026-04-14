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
eval_app = typer.Typer(help="Judge evaluation pipeline")
app.add_typer(snapshot_app, name="snapshot")
app.add_typer(eval_app, name="eval")


def _project() -> PVMProject:
    """Return the current working directory project facade."""
    return PVMProject.cwd()


@app.command("check")
def check() -> None:
    """Check project integrity and report missing directories or files."""
    _print_json(_project().check_integrity())


@app.command("init")
def init(name: str = typer.Argument(None)) -> None:
    """Initialize a pvm project."""
    if name is None:
        name = Path.cwd().name
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


@app.command("delete")
def delete(
    prompt_id: str = typer.Argument(..., metavar="ID"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation prompt"),
) -> None:
    """Delete a prompt and all its versions entirely."""
    if not force:
        confirm = typer.confirm(f"This will permanently delete prompt '{prompt_id}'. Continue?")
        if not confirm:
            raise SystemExit(0)
    _print_json(_project().delete_prompt(prompt_id))


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


@app.command("token-count")
def token_count(
    prompt_id: str = typer.Argument(None, metavar="ID"),
    version: str = typer.Argument(None),
    model: str = typer.Argument(None),
    list_models: bool = typer.Option(False, "--list-models", help="List supported models"),
) -> None:
    """Count tokens in a prompt version for a specific model."""
    if list_models:
        _print_json(_project().list_token_models())
        return
    if not prompt_id or not version or not model:
        typer.secho("Usage: pvm token-count <ID> <VERSION> <MODEL>", fg=typer.colors.RED, err=True)
        raise SystemExit(1)
    _print_json(_project().count_tokens(prompt_id, version, model))


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


@snapshot_app.command("export")
def snapshot_export(
    version: str = typer.Argument(...),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output zip file path"),
) -> None:
    """Export a snapshot as a zip file."""
    _print_json(_project().export_snapshot(version, output))


@snapshot_app.command("diff")
def snapshot_diff(from_version: str, to_version: str) -> None:
    """Diff two snapshots."""
    _print_json(_project().diff_snapshot(from_version, to_version))


@app.command("ui")
def ui(
    port: int = typer.Option(8001, "--port", "-p", help="Port number"),
) -> None:
    """Launch the local web UI."""
    from ui.app import run
    run(root=Path.cwd(), port=port)


# ── eval subcommands ──────────────────────────────────────────────────────────


@eval_app.command("register")
def eval_register(
    input: Path = typer.Option(..., "--input", "-i", help="등록할 CSV 또는 xlsx 파일 경로"),
) -> None:
    """Register a CSV/xlsx dataset to .pvm/datasets/."""
    import tempfile

    import pandas as pd

    from pvm.eval_pipeline.pvm_storage import register_csv

    pvm_root = Path(".pvm")
    input_path = input.resolve()
    ext = input_path.suffix.lower()

    if ext in (".xlsx", ".xls"):
        df = pd.read_excel(input_path)
        tmp = tempfile.NamedTemporaryFile(suffix=".csv", delete=False)
        df.to_csv(tmp.name, index=False)
        csv_path = Path(tmp.name)
        original_path = input_path
    elif ext == ".csv":
        csv_path = input_path
        original_path = None
    else:
        typer.secho(f"지원하지 않는 파일 형식: {ext}", fg=typer.colors.RED, err=True)
        raise SystemExit(1)

    csv_hash, data_path = register_csv(pvm_root, csv_path, original_path=original_path)

    already = data_path.exists() and csv_path != data_path
    if already:
        print(f"[register] 이미 등록된 데이터셋 (csv_hash: {csv_hash})")
    else:
        print(f"[register] data.csv 복사 완료 → {data_path}")

    import json as _json
    meta = _json.loads((pvm_root / "datasets" / csv_hash / "meta.json").read_text(encoding="utf-8"))
    print(f"[register] csv_hash: {csv_hash}  rows: {meta['row_count']}  columns: {meta['columns']}")


@eval_app.command("pipeline")
def eval_pipeline(
    csv_hash: str = typer.Option(..., "--csv-hash", help="register 명령으로 얻은 csv_hash"),
    prompt_id: str = typer.Option(..., "--prompt-id", help=".pvm에 등록된 prompt ID"),
    version: str = typer.Option(..., "--version", help="평가할 prompt version"),
    provider: str = typer.Option("openai", "--provider", help="LLM provider"),
    model: str = typer.Option("gpt-5.4-2026-03-05", "--model", help="LLM 모델명"),
    judge_type: str = typer.Option("pointwise", "--judge-type", help="pointwise / pairwise"),
) -> None:
    """Create a pipeline run directory and pipeline_meta.json."""
    from pvm.eval_pipeline.pvm_storage import create_pipeline_run

    pvm_root = Path(".pvm")
    pipeline_hash, run_dir = create_pipeline_run(
        pvm_root=pvm_root,
        prompt_id=prompt_id,
        prompt_version=version,
        judge_type=judge_type,
        csv_hash=csv_hash,
        judge_model=model,
        judge_provider=provider,
    )
    print(f"[pipeline] pipeline_hash: {pipeline_hash}")
    print(f"[pipeline] HASH_DIR: {run_dir}")


@eval_app.command("step0")
def eval_step0(
    run_dir: Path = typer.Option(..., "--run-dir", help="pipeline HASH_DIR 경로"),
) -> None:
    """Step 0: config.yaml 생성 (pipeline_meta.json에서 파라미터 자동 로드)."""
    from pvm.eval_pipeline.step0_generate_config import run_from_dir

    run_from_dir(run_dir.resolve(), Path(".pvm").resolve())


@eval_app.command("step1")
def eval_step1(
    run_dir: Path = typer.Option(..., "--run-dir", help="pipeline HASH_DIR 경로"),
) -> None:
    """Step 1: 에러 분석 (error_analysis.json 생성)."""
    from pvm.eval_pipeline.step1_error_analysis import run

    config_path = run_dir / "config.yaml"
    if not config_path.exists():
        typer.secho(f"config.yaml 없음: {config_path}  (step0을 먼저 실행하세요)", fg=typer.colors.RED, err=True)
        raise SystemExit(1)
    run(str(config_path))


@eval_app.command("step2")
def eval_step2(
    run_dir: Path = typer.Option(..., "--run-dir", help="pipeline HASH_DIR 경로"),
) -> None:
    """Step 2: judge component 생성 (judge.yaml + judge_prompt.md)."""
    from pvm.eval_pipeline.step2_generate_judge_prompts import run

    config_path = run_dir / "config.yaml"
    if not config_path.exists():
        typer.secho(f"config.yaml 없음: {config_path}  (step0을 먼저 실행하세요)", fg=typer.colors.RED, err=True)
        raise SystemExit(1)
    run(str(config_path))


@eval_app.command("step3")
def eval_step3(
    run_dir: Path = typer.Option(..., "--run-dir", help="pipeline HASH_DIR 경로"),
) -> None:
    """Step 3: LLM judge 실행 (judge_results.json 생성)."""
    from pvm.eval_pipeline.step3_run_judge import run

    config_path = run_dir / "config.yaml"
    if not config_path.exists():
        typer.secho(f"config.yaml 없음: {config_path}  (step0을 먼저 실행하세요)", fg=typer.colors.RED, err=True)
        raise SystemExit(1)
    run(str(config_path))


@eval_app.command("mark-step")
def eval_mark_step(
    run_dir: Path = typer.Option(..., "--run-dir", help="pipeline HASH_DIR 경로"),
    step: str = typer.Option(..., "--step", help="완료된 step (step0~step3)"),
) -> None:
    """Mark a pipeline step as completed in pipeline_meta.json."""
    from pvm.eval_pipeline.pvm_storage import mark_step_completed

    steps = mark_step_completed(run_dir, step)
    print(f"[mark-step] steps_completed: {steps}")


@eval_app.command("results")
def eval_results(
    run_dir: Path = typer.Option(..., "--run-dir", help="pipeline HASH_DIR 경로"),
) -> None:
    """Show judge results: verdict distribution and confusion matrix."""
    from pvm.eval_pipeline.show_results import show_results

    results_path = run_dir / "judge_results.json"
    if not results_path.exists():
        typer.secho(f"judge_results.json 없음: {results_path}  (step3을 먼저 실행하세요)", fg=typer.colors.RED, err=True)
        raise SystemExit(1)
    show_results(run_dir)


@eval_app.command("runs")
def eval_runs(
    prompt_id: str = typer.Option(..., "--prompt-id", help=".pvm에 등록된 prompt ID"),
    version: str | None = typer.Option(None, "--version", help="prompt version (생략 시 전체)"),
) -> None:
    """List pipeline runs for a prompt (최신순)."""
    import json as _json

    from pvm.eval_pipeline.pvm_storage import list_pipeline_runs

    pvm_root = Path(".pvm")

    if version:
        versions = [version]
    else:
        ver_dir = pvm_root / "prompts" / prompt_id / "versions"
        if not ver_dir.exists():
            print("실행 이력 없음")
            return
        versions = sorted(d.name for d in ver_dir.iterdir() if d.is_dir())

    rows = []
    for ver in versions:
        for run in list_pipeline_runs(pvm_root, prompt_id, ver):
            csv_meta_path = pvm_root / "datasets" / run.get("csv_hash", "") / "meta.json"
            original_name = ""
            if csv_meta_path.exists():
                csv_meta = _json.loads(csv_meta_path.read_text(encoding="utf-8"))
                original_name = Path(csv_meta.get("original_path", "")).name
            rows.append({
                "hash": run["pipeline_hash"],
                "version": ver,
                "created_at": run.get("created_at", ""),
                "csv_file": original_name,
                "judge_type": run.get("judge_type", ""),
                "steps": ", ".join(run.get("steps_completed", [])),
                "model": run.get("model", ""),
            })

    if not rows:
        print("실행 이력 없음")
        return

    # Simple tabular output
    header = f"{'#':>3}  {'hash':12}  {'version':8}  {'created_at':22}  {'csv_file':24}  {'judge_type':10}  {'steps':30}  model"
    print(header)
    print("-" * len(header))
    for i, r in enumerate(rows, 1):
        print(
            f"{i:>3}  {r['hash']:12}  {r['version']:8}  {r['created_at']:22}  "
            f"{r['csv_file']:24}  {r['judge_type']:10}  {r['steps']:30}  {r['model']}"
        )


def main() -> None:
    """Execute the pvm CLI."""
    try:
        app()
    except PVMError as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
