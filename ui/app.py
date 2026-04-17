from __future__ import annotations

import os
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pvm.core.errors import PVMError
from pvm.eval_pipeline.pvm_storage import select_judge_component_file
from pvm.project import PVMProject
from pvm.storage.history import read_history
from pvm.storage.yaml_io import dump_yaml

from .eval_runner import (
    get_pipeline_dir, get_run_status, get_step_status, is_configured, is_running,
    load_json, load_log, load_step2_yaml, patch_config_for_pvm,
    run_step0_sync, set_pipeline_dir, start_step_async, stop_step,
)

UI_DIR = Path(__file__).parent
app = FastAPI(title="pvm ui")
app.mount("/static", StaticFiles(directory=UI_DIR / "static"), name="static")
templates = Jinja2Templates(directory=UI_DIR / "templates")
templates.env.globals["api_keys_missing"] = lambda: not any([
    os.environ.get("ANTHROPIC_API_KEY"),
    os.environ.get("OPENAI_API_KEY"),
    os.environ.get("GEMINI_API_KEY"),
])

_project: PVMProject | None = None


def get_project() -> PVMProject:
    assert _project is not None
    return _project


def _render(request: Request, name: str, **kwargs: Any):
    return templates.TemplateResponse(request=request, name=name, context=kwargs)


def _parse_iso_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _format_timestamp(value: str | None) -> str:
    dt = _parse_iso_timestamp(value)
    if dt is None:
        return value or "-"
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


def _activity_label(entry: dict[str, Any]) -> str:
    event = entry.get("event")
    if event == "add":
        version = entry.get("version")
        return f"Prompt {entry.get('id')} added" + (f" ({version})" if version else "")
    if event == "deploy":
        to_version = entry.get("to_version")
        return f"Prompt {entry.get('id')} deployed" + (f" to {to_version}" if to_version else "")
    if event == "rollback":
        to_version = entry.get("to_version")
        return f"Prompt {entry.get('id')} rolled back" + (f" to {to_version}" if to_version else "")
    if event == "create":
        version = entry.get("version")
        return f"Snapshot created" + (f" ({version})" if version else "")
    return str(event or "activity")


def _activity_href(entry: dict[str, Any]) -> str:
    event = entry.get("event")
    if event == "create" and entry.get("version"):
        return f"/snapshots/{entry['version']}"
    if entry.get("id"):
        return f"/prompts/{entry['id']}"
    return "/history"


def _activity_tone(entry: dict[str, Any]) -> str:
    event = entry.get("event")
    if event == "deploy":
        return "green"
    if event == "rollback":
        return "yellow"
    if event == "create":
        return "blue"
    return "gray"


# --- Dashboard ---

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    project = get_project()
    if not project.is_valid():
        return _render(request, "setup.html",
            root_path=str(project.root),
            exists=project.paths.project_dir.exists(),
        )
    config = project.load_config()
    integrity = project.check_integrity()
    prompt_ids = project.list_prompt_ids()

    prompts_summary = []
    for pid in prompt_ids:
        info = project.get_prompt_info(pid)
        prompts_summary.append(info)

    # 최근 추가된 Prompt (created_at 기준)
    recent_prompts = sorted(
        prompts_summary,
        key=lambda item: _parse_iso_timestamp(item["info"].get("created_at"))
            or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )[:5]

    kpis = [
        {"label": "전체 Prompt", "value": len(prompts_summary)},
    ]

    return _render(request, "dashboard.html",
        config=config,
        integrity=integrity,
        recent_prompts=recent_prompts,
        kpis=kpis,
    )


@app.post("/project/edit-info")
def project_edit_info(
    description: str = Form(""),
):
    project = get_project()
    config = project.load_config()
    config["description"] = description.strip()
    dump_yaml(project.paths.config_file, config)
    return RedirectResponse("/", status_code=303)


# --- Tree ---

@app.get("/tree", response_class=HTMLResponse)
def tree(request: Request):
    project = get_project()
    config = project.load_config()
    prompt_ids = project.list_prompt_ids()
    snapshots = project.list_snapshots()

    prompts_summary = []
    for pid in prompt_ids:
        info = project.get_prompt_info(pid)
        prompts_summary.append(info)

    return _render(request, "tree.html",
        config=config,
        prompts_summary=prompts_summary,
        snapshots=snapshots,
        root_path=str(project.root),
    )


# --- Prompts ---

@app.get("/prompts", response_class=HTMLResponse)
def prompt_list(request: Request):
    project = get_project()
    prompt_ids = project.list_prompt_ids()
    prompts_summary = []
    for pid in prompt_ids:
        info = project.get_prompt_info(pid)
        prompts_summary.append(info)
    prompts_summary.sort(
        key=lambda p: _parse_iso_timestamp(p["info"].get("created_at"))
            or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )
    return _render(request, "prompts.html",
        prompts_summary=prompts_summary,
    )


@app.get("/prompts/add", response_class=HTMLResponse)
def prompt_add_form(request: Request):
    import yaml
    project = get_project()
    template = project.load_template()
    default_yaml = yaml.safe_dump(template, allow_unicode=True, sort_keys=False).rstrip()
    return _render(request, "prompt_add.html", yaml_content=default_yaml)


@app.post("/prompts/add")
async def prompt_add(
    request: Request,
    template_file: UploadFile = File(...),
    bump_level: str = Form("patch"),
):
    project = get_project()
    tmp_path = project.root / f"_tmp_{template_file.filename}"
    try:
        content = await template_file.read()
        tmp_path.write_bytes(content)
        result = project.add_prompt(tmp_path, bump_level=bump_level)
    finally:
        tmp_path.unlink(missing_ok=True)

    if not result["changed"]:
        return _render(request, "prompt_add.html",
            message="No changes detected.",
        )
    return RedirectResponse(f"/prompts/{result['id']}", status_code=303)


@app.post("/prompts/add/form")
async def prompt_add_form_submit(request: Request):
    import yaml

    form = await request.form()
    prompt_id = form.get("prompt_id", "")
    prompt_text = form.get("prompt_text", "")
    llm_provider = form.get("llm_provider", "")
    llm_model = form.get("llm_model", "")
    description = form.get("description", "")
    author = form.get("author", "")
    temperature = form.get("temperature")
    max_tokens = form.get("max_tokens")
    bump_level = form.get("bump_level", "patch")
    extra_keys = form.getlist("extra_keys")
    extra_values = form.getlist("extra_values")

    project = get_project()
    template: dict = {
        "id": prompt_id,
        "prompt": prompt_text,
        "llm": {
            "provider": llm_provider,
            "model": llm_model,
        },
    }
    params = {}
    if temperature:
        params["temperature"] = float(temperature)
    if max_tokens:
        params["max_tokens"] = int(max_tokens)
    if params:
        template["llm"]["params"] = params
    if description:
        template["description"] = description
    if author:
        template["author"] = author

    for key, value in zip(extra_keys, extra_values):
        if key.strip() and value.strip():
            template[key.strip()] = value.strip()

    tmp_path = project.root / "_tmp_form_input.yaml"
    try:
        yaml_content = yaml.safe_dump(template, allow_unicode=True, sort_keys=False)
        tmp_path.write_text(yaml_content, encoding="utf-8")
        result = project.add_prompt(tmp_path, bump_level=bump_level)
    finally:
        tmp_path.unlink(missing_ok=True)

    if not result["changed"]:
        return _render(request, "prompt_add.html",
            message="No changes detected.",
            yaml_content=yaml_content,
        )
    return RedirectResponse(f"/prompts/{result['id']}", status_code=303)


@app.post("/prompts/add/editor")
async def prompt_add_editor(
    request: Request,
    yaml_content: str = Form(...),
    bump_level: str = Form("patch"),
):
    project = get_project()
    tmp_path = project.root / "_tmp_editor_input.yaml"
    try:
        tmp_path.write_text(yaml_content, encoding="utf-8")
        result = project.add_prompt(tmp_path, bump_level=bump_level)
    finally:
        tmp_path.unlink(missing_ok=True)

    if not result["changed"]:
        return _render(request, "prompt_add.html",
            message="No changes detected.",
            yaml_content=yaml_content,
        )
    return RedirectResponse(f"/prompts/{result['id']}", status_code=303)


@app.get("/api/token-count/models")
def token_count_models():
    project = get_project()
    return JSONResponse(content=project.list_token_models())


@app.get("/api/token-count/{prompt_id}/{version}")
def token_count_api(prompt_id: str, version: str, model: str = Query(...)):
    project = get_project()
    return JSONResponse(content=project.count_tokens(prompt_id, version, model))


@app.get("/prompts/{prompt_id}/version/{version}/export")
def prompt_export(prompt_id: str, version: str, fmt: str = Query("txt", alias="format")):
    import json as _json
    import yaml as _yaml
    from fastapi.responses import Response

    project = get_project()
    d = project.get_prompt(prompt_id, version=version)
    meta = d.get("metadata", {})

    if fmt == "txt":
        content = d["prompt"]
        media_type = "text/plain; charset=utf-8"
        filename = f"{prompt_id}_v{version}.txt"

    elif fmt == "md":
        lines = [f"# {prompt_id}", "", f"**버전**: `{version}`"]
        if meta.get("author"):
            lines.append(f"**작성자**: {meta['author']}")
        if meta.get("created_at"):
            lines.append(f"**생성일**: {meta['created_at']}")
        lines += ["", "---", "", "## Prompt", "", d["prompt"]]
        if d.get("llm"):
            lines += ["", "## LLM 설정", "", "```json",
                      _json.dumps(d["llm"], ensure_ascii=False, indent=2), "```"]
        content = "\n".join(lines)
        media_type = "text/markdown; charset=utf-8"
        filename = f"{prompt_id}_v{version}.md"

    elif fmt == "json":
        content = _json.dumps(d, ensure_ascii=False, indent=2)
        media_type = "application/json; charset=utf-8"
        filename = f"{prompt_id}_v{version}.json"

    elif fmt == "yaml":
        template: dict = {"id": prompt_id, "prompt": d["prompt"]}
        if d.get("llm"):
            template["llm"] = d["llm"]
        if meta.get("author"):
            template["author"] = meta["author"]
        content = _yaml.safe_dump(template, allow_unicode=True, sort_keys=False)
        media_type = "text/yaml; charset=utf-8"
        filename = f"{prompt_id}_v{version}.yaml"

    else:
        content = d["prompt"]
        media_type = "text/plain; charset=utf-8"
        filename = f"{prompt_id}_v{version}.txt"

    return Response(
        content=content.encode("utf-8"),
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _eval_ui_url(project) -> str:
    """프로젝트 config에서 eval_ui_url을 읽는다. 없으면 기본값."""
    try:
        cfg = project.load_config()
        return cfg.get("eval_ui_url", "http://localhost:8010").rstrip("/")
    except Exception:
        return "http://localhost:8010"


def _augment_eval_metrics(metrics: dict | None, results: list[dict] | None = None) -> dict | None:
    """Normalize eval metrics across old and new judge_results formats."""
    if metrics is None:
        return None

    normalized = dict(metrics)
    results = results or []

    judged_results = [r for r in results if r.get("judge_verdict") != "PARSE_ERROR"]
    pass_count_from_results = sum(1 for r in judged_results if r.get("judge_verdict") in {"Pass", "A"})
    judged_total_from_results = len(judged_results)

    if normalized.get("pass_count") is None:
        normalized["pass_count"] = pass_count_from_results
    if normalized.get("judged_total") is None:
        normalized["judged_total"] = judged_total_from_results or normalized.get("valid", 0)
    if normalized.get("pass_rate") is None:
        judged_total = normalized.get("judged_total") or 0
        pass_count = normalized.get("pass_count") or 0
        normalized["pass_rate"] = (pass_count / judged_total) if judged_total else 0.0

    return normalized


def _get_eval_summary(project, prompt_id: str) -> dict[str, dict | None]:
    """각 버전의 최신 judge 결과 요약(metrics)을 반환한다.

    Returns:
        {version: metrics_dict | None}  — 결과 없으면 None
    """
    import json

    pvm_dir = project.root / ".pvm"
    try:
        versions = project.list_prompt_versions(prompt_id)
    except Exception:
        return {}
    benchmark_csv_hash = _prompt_benchmark_csv_hash(project, prompt_id)

    summary: dict[str, dict | None] = {}
    for ver in versions:
        judge_dir = pvm_dir / "prompts" / prompt_id / "versions" / ver / "judge"
        if not judge_dir.exists():
            summary[ver] = None
            continue

        # 가장 최근 실행 디렉토리 중 judge_results.json이 있는 것 (created_at 기준)
        def _run_created_at(p: Path) -> str:
            meta = p / "pipeline_meta.json"
            if meta.exists():
                try:
                    return json.loads(meta.read_text(encoding="utf-8")).get("created_at", "")
                except Exception:
                    pass
            return ""
        found = None
        for run_dir in sorted(judge_dir.iterdir(), key=_run_created_at, reverse=True):
            results_path = run_dir / "judge_results.json"
            if results_path.exists():
                try:
                    meta_path = run_dir / "pipeline_meta.json"
                    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
                    csv_info = _resolve_run_csv_info(project, run_dir, meta) or {}
                    data = json.loads(results_path.read_text(encoding="utf-8"))
                    found = _augment_eval_metrics(
                        data.get("metrics"),
                        data.get("results", []),
                    )
                    if found is not None:
                        found = dict(found)
                        found["run_at"] = data.get("run_at", "")
                        found["partial"] = data.get("partial", False)
                        found["pipeline_hash"] = run_dir.name
                        csv_hash = meta.get("csv_hash", "") or csv_info.get("csv_hash", "")
                        dataset_meta = _load_dataset_meta(project, csv_hash)
                        found["csv_hash"] = csv_hash
                        found["dataset_name"] = _dataset_display_name(csv_hash, dataset_meta, csv_info.get("csv_filename", ""))
                        found["dataset_badge"] = _dataset_usage_badge(csv_hash, benchmark_csv_hash)
                except Exception:
                    pass
                break
        summary[ver] = found
    return summary


def _augment_compare_summary(compare_meta: dict | None, judge_data: dict | None) -> dict | None:
    if not compare_meta:
        return None

    results = (judge_data or {}).get("results", [])
    a_wins = sum(1 for r in results if r.get("judge_verdict") == "A")
    b_wins = sum(1 for r in results if r.get("judge_verdict") == "B")
    ties = sum(1 for r in results if r.get("judge_verdict") == "SAME")
    errors = sum(1 for r in results if r.get("judge_verdict") == "PARSE_ERROR")
    total = len(results)

    return {
        "compare_hash": compare_meta.get("compare_hash", ""),
        "version_a": compare_meta.get("version_a", ""),
        "version_b": compare_meta.get("version_b", ""),
        "judge_provider": compare_meta.get("judge_provider", ""),
        "judge_model": compare_meta.get("judge_model", ""),
        "matched_traces": compare_meta.get("matched_traces", 0),
        "created_at": _format_timestamp(compare_meta.get("created_at", "")),
        "created_at_raw": compare_meta.get("created_at", ""),
        "step1_skipped": compare_meta.get("step1_skipped", False),
        "criteria_source_version": compare_meta.get("criteria_source_version", ""),
        "criteria_source_run_hash": compare_meta.get("criteria_source_run_hash", ""),
        "result_count": total,
        "a_wins": a_wins,
        "b_wins": b_wins,
        "ties": ties,
        "errors": errors,
        "a_rate": round(a_wins / total * 100, 1) if total else 0.0,
        "b_rate": round(b_wins / total * 100, 1) if total else 0.0,
        "tie_rate": round(ties / total * 100, 1) if total else 0.0,
        "has_report": bool(judge_data and (judge_data.get("results") or judge_data.get("metrics"))),
        "partial": bool((judge_data or {}).get("partial", False)),
    }


def _get_compare_history(project, prompt_id: str) -> list[dict]:
    import json as _j

    compare_root = _pvm_dir(project) / "prompts" / prompt_id / "compare"
    if not compare_root.exists():
        return []

    history: list[dict] = []
    for compare_dir in sorted(compare_root.iterdir(), reverse=True):
        if not compare_dir.is_dir():
            continue
        meta_path = compare_dir / "compare_meta.json"
        if not meta_path.exists():
            continue
        try:
            meta = _j.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue

        judge_data = None
        results_path = compare_dir / "judge_results.json"
        if results_path.exists():
            try:
                judge_data = _j.loads(results_path.read_text(encoding="utf-8"))
            except Exception:
                judge_data = None

        summary = _augment_compare_summary(meta, judge_data)
        if summary is None:
            continue
        history.append(summary)

    history.sort(key=lambda item: item.get("created_at_raw", ""), reverse=True)
    return history


def _get_latest_compare_summary(project, prompt_id: str) -> dict | None:
    history = _get_compare_history(project, prompt_id)
    return history[0] if history else None


@app.get("/prompts/{prompt_id}", response_class=HTMLResponse)
def prompt_detail(request: Request, prompt_id: str):
    project = get_project()
    info = project.get_prompt_info(prompt_id)
    versions = project.list_prompt_versions(prompt_id)

    current_version = versions[-1] if versions else None

    prompt_data = None
    if current_version:
        prompt_data = project.get_prompt(prompt_id, version=current_version)

    eval_summary = _get_eval_summary(project, prompt_id)
    compare_summary = _get_latest_compare_summary(project, prompt_id)
    return _render(request, "prompt_detail.html",
        info=info,
        versions=versions,
        current_version=current_version,
        prompt_data=prompt_data,
        eval_ui_url=_eval_ui_url(project),
        pvm_root=str(project.root),
        eval_summary=eval_summary,
        compare_summary=compare_summary,
    )


@app.get("/prompts/{prompt_id}/version/{version}", response_class=HTMLResponse)
def prompt_version_detail(request: Request, prompt_id: str, version: str):
    project = get_project()
    info = project.get_prompt_info(prompt_id)
    versions = project.list_prompt_versions(prompt_id)
    prompt_data = project.get_prompt(prompt_id, version=version)

    eval_summary = _get_eval_summary(project, prompt_id)
    compare_summary = _get_latest_compare_summary(project, prompt_id)
    return _render(request, "prompt_detail.html",
        info=info,
        versions=versions,
        current_version=version,
        prompt_data=prompt_data,
        eval_ui_url=_eval_ui_url(project),
        pvm_root=str(project.root),
        eval_summary=eval_summary,
        compare_summary=compare_summary,
    )


@app.get("/prompts/{prompt_id}/update", response_class=HTMLResponse)
def prompt_update_form(request: Request, prompt_id: str, bump: str = Query("patch")):
    import yaml

    project = get_project()
    info = project.get_prompt_info(prompt_id)
    current_version = info["latest_version"]

    # Load current version's template.yaml
    template_file = project.paths.prompt_version_file(prompt_id, current_version, "template.yaml")
    template = {}
    yaml_content = ""
    if template_file.exists():
        from pvm.storage.yaml_io import load_yaml
        template = load_yaml(template_file)
        yaml_content = yaml.safe_dump(template, allow_unicode=True, sort_keys=False).rstrip()

    # Extract form fields
    llm = template.get("llm", {})
    params = llm.get("params", {})
    known_keys = {"id", "prompt", "llm", "description", "author"}
    extra_fields = [(k, v) for k, v in template.items() if k not in known_keys]

    return _render(request, "prompt_update.html",
        prompt_id=prompt_id,
        current_version=current_version,
        bump_level=bump,
        yaml_content=yaml_content,
        prompt_text=template.get("prompt", ""),
        llm_provider=llm.get("provider", ""),
        llm_model=llm.get("model", ""),
        description=template.get("description", ""),
        author=template.get("author", ""),
        temperature=params.get("temperature", ""),
        max_tokens=params.get("max_tokens", ""),
        extra_fields=extra_fields,
    )


@app.post("/prompts/{prompt_id}/update/form")
async def prompt_update_form_submit(request: Request, prompt_id: str):
    import yaml

    form = await request.form()
    bump_level = form.get("bump_level", "patch")
    prompt_text = form.get("prompt_text", "")
    llm_provider = form.get("llm_provider", "")
    llm_model = form.get("llm_model", "")
    description = form.get("description", "")
    author = form.get("author", "")
    temperature = form.get("temperature")
    max_tokens = form.get("max_tokens")
    extra_keys = form.getlist("extra_keys")
    extra_values = form.getlist("extra_values")

    project = get_project()
    template: dict = {
        "id": prompt_id,
        "prompt": prompt_text,
        "llm": {
            "provider": llm_provider,
            "model": llm_model,
        },
    }
    params = {}
    if temperature:
        params["temperature"] = float(temperature)
    if max_tokens:
        params["max_tokens"] = int(max_tokens)
    if params:
        template["llm"]["params"] = params
    if description:
        template["description"] = description
    if author:
        template["author"] = author
    for key, value in zip(extra_keys, extra_values):
        if key.strip() and value.strip():
            template[key.strip()] = value.strip()

    tmp_path = project.root / "_tmp_update_form.yaml"
    try:
        yaml_content = yaml.safe_dump(template, allow_unicode=True, sort_keys=False)
        tmp_path.write_text(yaml_content, encoding="utf-8")
        result = project.add_prompt(tmp_path, bump_level=bump_level)
    finally:
        tmp_path.unlink(missing_ok=True)

    if not result["changed"]:
        return _render(request, "prompt_update.html",
            prompt_id=prompt_id,
            current_version=project.get_prompt_info(prompt_id)["latest_version"],
            bump_level=bump_level,
            yaml_content=yaml_content,
            prompt_text=prompt_text,
            llm_provider=llm_provider,
            llm_model=llm_model,
            description=description,
            author=author,
            temperature=temperature or "",
            max_tokens=max_tokens or "",
            extra_fields=list(zip(extra_keys, extra_values)),
            message="No changes detected.",
        )
    return RedirectResponse(f"/prompts/{prompt_id}", status_code=303)


@app.post("/prompts/{prompt_id}/update")
async def prompt_update_submit(request: Request, prompt_id: str):
    form = await request.form()
    bump_level = form.get("bump_level", "patch")
    yaml_content = form.get("yaml_content", "")

    project = get_project()
    tmp_path = project.root / "_tmp_update_input.yaml"
    try:
        tmp_path.write_text(yaml_content, encoding="utf-8")
        result = project.add_prompt(tmp_path, bump_level=bump_level)
    finally:
        tmp_path.unlink(missing_ok=True)

    if not result["changed"]:
        return _render(request, "prompt_update.html",
            prompt_id=prompt_id,
            current_version=project.get_prompt_info(prompt_id)["latest_version"],
            bump_level=bump_level,
            yaml_content=yaml_content,
            message="No changes detected.",
        )
    return RedirectResponse(f"/prompts/{prompt_id}", status_code=303)


@app.post("/prompts/{prompt_id}/update/upload")
async def prompt_update_upload(request: Request, prompt_id: str):
    form = await request.form()
    bump_level = form.get("bump_level", "patch")
    template_file = form["template_file"]

    project = get_project()
    tmp_path = project.root / f"_tmp_{template_file.filename}"
    try:
        content = await template_file.read()
        tmp_path.write_bytes(content)
        result = project.add_prompt(tmp_path, bump_level=bump_level)
    finally:
        tmp_path.unlink(missing_ok=True)

    if not result["changed"]:
        return _render(request, "prompt_update.html",
            prompt_id=prompt_id,
            current_version=project.get_prompt_info(prompt_id)["latest_version"],
            bump_level=bump_level,
            yaml_content="",
            message="No changes detected.",
        )
    return RedirectResponse(f"/prompts/{prompt_id}", status_code=303)



@app.post("/prompts/{prompt_id}/delete")
def prompt_delete(prompt_id: str):
    project = get_project()
    project.delete_prompt(prompt_id)
    return RedirectResponse("/prompts", status_code=303)


@app.post("/prompts/{prompt_id}/version/{version}/delete")
def version_delete(prompt_id: str, version: str):
    import shutil as _shutil
    project = get_project()
    versions = project.list_prompt_versions(prompt_id)
    if len(versions) <= 1:
        # 마지막 버전은 삭제 불가 — prompt 삭제를 사용하도록 유도
        return RedirectResponse(f"/prompts/{prompt_id}", status_code=303)
    ver_dir = _pvm_dir(project) / "prompts" / prompt_id / "versions" / version
    if ver_dir.exists():
        _shutil.rmtree(ver_dir)
    return RedirectResponse(f"/prompts/{prompt_id}", status_code=303)


@app.post("/prompts/{prompt_id}/version/{version}/eval/{pipeline_hash}/delete")
def eval_run_delete(prompt_id: str, version: str, pipeline_hash: str):
    import shutil as _shutil
    project = get_project()
    run_dir = _run_dir(project, prompt_id, version, pipeline_hash)
    if run_dir.exists():
        _shutil.rmtree(run_dir)
    return RedirectResponse(
        f"/prompts/{prompt_id}/version/{version}/eval/history", status_code=303
    )


@app.post("/prompts/{prompt_id}/compare/{compare_hash}/delete")
def compare_run_delete(prompt_id: str, compare_hash: str):
    import shutil as _shutil

    project = get_project()
    compare_dir = _compare_run_dir(project, prompt_id, compare_hash)
    if compare_dir.exists():
        _shutil.rmtree(compare_dir)
    return RedirectResponse(f"/prompts/{prompt_id}/compare/history", status_code=303)


@app.post("/prompts/{prompt_id}/edit-info")
def prompt_edit_info(
    prompt_id: str,
    description: str = Form(""),
    author: str = Form(""),
):
    project = get_project()
    project.edit_prompt_info(prompt_id, description=description, author=author)
    return RedirectResponse(f"/prompts/{prompt_id}", status_code=303)


@app.get("/prompts/{prompt_id}/diff", response_class=HTMLResponse)
def prompt_diff(
    request: Request,
    prompt_id: str,
    from_version: str = Query(..., alias="from"),
    to_version: str = Query(..., alias="to"),
):
    project = get_project()
    diff_result = project.diff_prompt(prompt_id, from_version, to_version)
    versions = project.list_prompt_versions(prompt_id)

    return _render(request, "prompt_diff.html",
        prompt_id=prompt_id,
        diff_result=diff_result,
        versions=versions,
    )




# --- Open Explorer ---

@app.post("/project/open")
def project_open():
    import platform
    import subprocess

    project = get_project()
    path = str(project.root)
    system = platform.system()
    if system == "Windows":
        subprocess.Popen(["explorer", path])
    elif system == "Darwin":
        subprocess.Popen(["open", path])
    else:
        subprocess.Popen(["xdg-open", path])
    return RedirectResponse("/", status_code=303)


# --- Project Init / Reset / Destroy ---

@app.post("/project/init")
def project_init(name: str = Form("my-project"), description: str = Form("")):
    project = get_project()
    project.init(name)
    if description.strip():
        config = project.load_config()
        config["description"] = description.strip()
        dump_yaml(project.paths.config_file, config)
    return RedirectResponse("/", status_code=303)


@app.post("/project/reset")
def project_reset():
    project = get_project()
    project.reset()
    return RedirectResponse("/", status_code=303)


@app.post("/project/destroy")
def project_destroy():
    project = get_project()
    project.destroy()
    return RedirectResponse("/", status_code=303)


# --- Error handler ---

# ── Eval 파이프라인 ──────────────────────────────────────────────────────────

def _pvm_dir(project) -> Path:
    return project.root / ".pvm"


def _run_dir(project, prompt_id: str, version: str, pipeline_hash: str) -> Path:
    return _pvm_dir(project) / "prompts" / prompt_id / "versions" / version / "judge" / pipeline_hash


def _meta_created_at(run_dir: Path) -> str:
    meta_path = run_dir / "pipeline_meta.json"
    if meta_path.exists():
        try:
            import json as _j
            return _j.loads(meta_path.read_text(encoding="utf-8")).get("created_at", "")
        except Exception:
            pass
    return ""


def _resolve_run_csv_info(project, run_dir: Path, meta: dict | None = None) -> dict | None:
    """Resolve the CSV backing an eval run from metadata or config fallback."""
    import json as _j
    import yaml as _yaml

    meta = meta or {}
    pvm_dir = _pvm_dir(project)

    csv_hash = meta.get("csv_hash", "") or ""
    if csv_hash:
        csv_path = pvm_dir / "datasets" / csv_hash / "data.csv"
        if csv_path.exists():
            csv_filename = ""
            meta_path = pvm_dir / "datasets" / csv_hash / "meta.json"
            if meta_path.exists():
                try:
                    csv_filename = _j.loads(meta_path.read_text(encoding="utf-8")).get("original_name", "")
                except Exception:
                    pass
            return {
                "csv_hash": csv_hash,
                "csv_path": csv_path,
                "csv_filename": csv_filename or csv_path.name,
            }

    config_path = run_dir / "config.yaml"
    if config_path.exists():
        try:
            cfg = _yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        except Exception:
            cfg = {}
        input_csv = str(cfg.get("input_csv", "")).strip()
        if input_csv:
            csv_path = Path(input_csv)
            if not csv_path.is_absolute():
                csv_path = run_dir / input_csv
            if csv_path.exists():
                recovered_hash = ""
                parts = csv_path.parts
                if "datasets" in parts:
                    idx = parts.index("datasets")
                    if idx + 1 < len(parts):
                        recovered_hash = parts[idx + 1]
                return {
                    "csv_hash": recovered_hash,
                    "csv_path": csv_path,
                    "csv_filename": csv_path.name,
                }

    return None


def _load_dataset_meta(project, csv_hash: str) -> dict:
    if not csv_hash:
        return {}
    meta_path = _pvm_dir(project) / "datasets" / csv_hash / "meta.json"
    if not meta_path.exists():
        return {}
    try:
        return _json.loads(meta_path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _dataset_display_name(csv_hash: str, meta: dict | None = None, fallback: str = "") -> str:
    meta = meta or {}
    return (
        meta.get("dataset_name")
        or meta.get("original_name")
        or fallback
        or (f"dataset:{csv_hash[:8]}" if csv_hash else "legacy dataset")
    )


def _dataset_usage_badge(csv_hash: str, benchmark_csv_hash: str) -> dict:
    if not csv_hash:
        return {
            "code": "legacy",
            "label": "dataset 정보 없음",
            "tone": "gray",
            "comparable": False,
        }
    if not benchmark_csv_hash:
        return {
            "code": "unknown",
            "label": "비교 기준 없음",
            "tone": "gray",
            "comparable": False,
        }
    if csv_hash == benchmark_csv_hash:
        return {
            "code": "same",
            "label": "동일 dataset",
            "tone": "green",
            "comparable": True,
        }
    return {
        "code": "mismatch",
        "label": "dataset 다름",
        "tone": "yellow",
        "comparable": False,
    }


def _iter_prompt_eval_runs(project, prompt_id: str) -> list[dict]:
    runs: list[dict] = []
    try:
        versions = project.list_prompt_versions(prompt_id)
    except Exception:
        return runs

    for ver in versions:
        judge_dir = _pvm_dir(project) / "prompts" / prompt_id / "versions" / ver / "judge"
        if not judge_dir.exists():
            continue
        for run_dir in judge_dir.iterdir():
            if not run_dir.is_dir():
                continue
            meta_path = run_dir / "pipeline_meta.json"
            meta: dict = {}
            if meta_path.exists():
                try:
                    meta = _json.loads(meta_path.read_text(encoding="utf-8"))
                except Exception:
                    meta = {}
            csv_info = _resolve_run_csv_info(project, run_dir, meta)
            judge_data = None
            results_path = run_dir / "judge_results.json"
            if results_path.exists():
                try:
                    judge_data = _json.loads(results_path.read_text(encoding="utf-8"))
                except Exception:
                    judge_data = None
            runs.append({
                "version": ver,
                "run_dir": run_dir,
                "meta": meta,
                "csv_info": csv_info,
                "judge_data": judge_data,
                "created_at_raw": meta.get("created_at", ""),
            })

    runs.sort(key=lambda item: item.get("created_at_raw", ""), reverse=True)
    return runs


def _prompt_benchmark_csv_hash(project, prompt_id: str) -> str:
    for item in _iter_prompt_eval_runs(project, prompt_id):
        if not item.get("judge_data"):
            continue
        csv_info = item.get("csv_info") or {}
        csv_hash = csv_info.get("csv_hash", "")
        if csv_hash:
            return csv_hash
    return ""


def _recommended_dataset_for_version(project, prompt_id: str, version: str) -> dict | None:
    try:
        versions = project.list_prompt_versions(prompt_id)
    except Exception:
        return None

    previous_versions: set[str] = set()
    if version in versions:
        previous_versions = set(versions[:versions.index(version)])

    for item in _iter_prompt_eval_runs(project, prompt_id):
        if item["version"] not in previous_versions:
            continue
        if not item.get("judge_data"):
            continue
        csv_info = item.get("csv_info") or {}
        csv_hash = csv_info.get("csv_hash", "")
        if not csv_hash:
            continue
        dataset_meta = _load_dataset_meta(project, csv_hash)
        return {
            "csv_hash": csv_hash,
            "version": item["version"],
            "pipeline_hash": item["run_dir"].name,
            "created_at": _format_timestamp(item["created_at_raw"]),
            "dataset_name": _dataset_display_name(csv_hash, dataset_meta, csv_info.get("csv_filename", "")),
            "row_count": dataset_meta.get("row_count"),
            "query_count": dataset_meta.get("query_count"),
            "csv_filename": csv_info.get("csv_filename", ""),
        }
    return None


def _eval_reusable_csvs(project, prompt_id: str, target_version: str | None = None) -> list[dict]:
    """Return unique reusable CSVs seen in prior eval runs for a prompt."""
    import json as _j

    items: list[dict] = []
    seen: set[tuple[str, str]] = set()
    recommended = (
        _recommended_dataset_for_version(project, prompt_id, version=target_version)
        if target_version
        else None
    )
    try:
        versions = project.list_prompt_versions(prompt_id)
    except Exception:
        return items

    for ver in reversed(versions):
        judge_dir = _pvm_dir(project) / "prompts" / prompt_id / "versions" / ver / "judge"
        if not judge_dir.exists():
            continue
        for run_dir in sorted(judge_dir.iterdir(), reverse=True):
            if not run_dir.is_dir():
                continue
            meta_path = run_dir / "pipeline_meta.json"
            meta: dict = {}
            if meta_path.exists():
                try:
                    meta = _j.loads(meta_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            csv_info = _resolve_run_csv_info(project, run_dir, meta)
            if csv_info is None:
                continue
            dedupe_key = (csv_info.get("csv_hash", ""), str(csv_info["csv_path"]))
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            csv_hash = csv_info.get("csv_hash", "")
            dataset_meta = _load_dataset_meta(project, csv_hash)
            items.append({
                "version": ver,
                "hash": run_dir.name,
                "created_at": _format_timestamp(meta.get("created_at", "")),
                "judge_model": meta.get("judge_model", "-"),
                "judge_provider": meta.get("judge_provider", "-"),
                "csv_hash": csv_hash,
                "csv_filename": csv_info.get("csv_filename", csv_info["csv_path"].name),
                "csv_path": str(csv_info["csv_path"]),
                "dataset_name": _dataset_display_name(csv_hash, dataset_meta, csv_info.get("csv_filename", "")),
                "row_count": dataset_meta.get("row_count"),
                "query_count": dataset_meta.get("query_count"),
                "recommended": bool(recommended and recommended.get("csv_hash") == csv_hash),
            })
    return items


def _get_eval_history(project, prompt_id: str, version: str) -> list:
    import json as _j
    judge_dir = project.root / ".pvm" / "prompts" / prompt_id / "versions" / version / "judge"
    if not judge_dir.exists():
        return []
    benchmark_csv_hash = _prompt_benchmark_csv_hash(project, prompt_id)
    history = []
    def _meta_created_at(p: Path) -> str:
        mp = p / "pipeline_meta.json"
        if mp.exists():
            try:
                return _j.loads(mp.read_text(encoding="utf-8")).get("created_at", "")
            except Exception:
                pass
        return ""
    for run_dir in sorted(judge_dir.iterdir(), key=_meta_created_at, reverse=True):
        if not run_dir.is_dir():
            continue
        meta: dict = {}
        meta_path = run_dir / "pipeline_meta.json"
        if meta_path.exists():
            try:
                meta = _j.loads(meta_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        judge_data = None
        results_path = run_dir / "judge_results.json"
        if results_path.exists():
            try:
                judge_data = _j.loads(results_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        step_status = get_run_status(run_dir)
        created_at_raw = meta.get("created_at", "")
        csv_info = _resolve_run_csv_info(project, run_dir, meta) or {}
        csv_hash = meta.get("csv_hash", "") or csv_info.get("csv_hash", "")
        dataset_meta = _load_dataset_meta(project, csv_hash)
        csv_filename = dataset_meta.get("original_name", "") or csv_info.get("csv_filename", "")
        history.append({
            "pipeline_hash": run_dir.name,
            "created_at": _format_timestamp(created_at_raw),
            "judge_type": meta.get("judge_type", "-"),
            "judge_model": meta.get("judge_model", "-"),
            "judge_provider": meta.get("judge_provider", "-"),
            "csv_hash": csv_hash,
            "csv_filename": csv_filename,
            "dataset_name": _dataset_display_name(csv_hash, dataset_meta, csv_info.get("csv_filename", csv_filename)),
            "dataset_badge": _dataset_usage_badge(csv_hash, benchmark_csv_hash),
            "row_count": dataset_meta.get("row_count"),
            "query_count": dataset_meta.get("query_count"),
            "step_status": step_status,
            "metrics": _augment_eval_metrics(
                judge_data.get("metrics") if judge_data else None,
                (judge_data or {}).get("results", []),
            ),
            "partial": (judge_data or {}).get("partial", False),
            "result_count": len((judge_data or {}).get("results", [])),
            "eval_url_base": f"/prompts/{prompt_id}/version/{version}/eval/{run_dir.name}",
        })
    return history


@app.get("/prompts/{prompt_id}/version/{version}/eval/history", response_class=HTMLResponse)
def eval_history(request: Request, prompt_id: str, version: str):
    project = get_project()
    info = project.get_prompt_info(prompt_id)
    history = _get_eval_history(project, prompt_id, version)
    return _render(request, "eval_history.html",
        info=info,
        version=version,
        history=history,
    )


def _eval_runs_with_criteria(project, prompt_id: str) -> list:
    """이 prompt의 모든 버전 중 step2(judge_components)가 완료된 실행 목록을 반환."""
    import json as _j2
    runs = []
    try:
        versions = project.list_prompt_versions(prompt_id)
    except Exception:
        return runs
    pvm_dir = project.root / ".pvm"
    for ver in reversed(versions):  # 최신 버전부터
        judge_dir = pvm_dir / "prompts" / prompt_id / "versions" / ver / "judge"
        if not judge_dir.exists():
            continue
        for run_dir in sorted(judge_dir.iterdir(), reverse=True):
            if not run_dir.is_dir():
                continue
            # step2 완료 여부 확인
            comp_dir = run_dir / "judge_components"
            comp_file = select_judge_component_file(run_dir)
            if comp_file is None:
                continue
            meta: dict = {}
            meta_path = run_dir / "pipeline_meta.json"
            if meta_path.exists():
                try:
                    meta = _j2.loads(meta_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            # criteria 미리보기: judge_components yaml에서 criteria 텍스트 앞부분
            criteria_preview = ""
            if comp_file is not None:
                try:
                    import yaml as _yaml
                    comp_data = _yaml.safe_load(comp_file.read_text(encoding="utf-8"))
                    raw = comp_data.get("criteria", "") or ""
                    criteria_preview = raw[:120].replace("\n", " ") + ("..." if len(raw) > 120 else "")
                except Exception:
                    pass
            runs.append({
                "version": ver,
                "hash": run_dir.name,
                "created_at": _format_timestamp(meta.get("created_at", "")),
                "judge_model": meta.get("judge_model", "-"),
                "judge_provider": meta.get("judge_provider", "-"),
                "judge_type": meta.get("judge_type", "-"),
                "criteria_preview": criteria_preview,
            })
    return runs


@app.get("/prompts/{prompt_id}/version/{version}/eval/api/reusable-runs")
def eval_api_reusable_runs(prompt_id: str, version: str):
    project = get_project()
    return JSONResponse(_eval_runs_with_criteria(project, prompt_id))


@app.get("/prompts/{prompt_id}/version/{version}/eval/api/reusable-csvs")
def eval_api_reusable_csvs(prompt_id: str, version: str):
    project = get_project()
    return JSONResponse(_eval_reusable_csvs(project, prompt_id, target_version=version))


# ── Query Dataset 관리 ────────────────────────────────────────────────────────

@app.get("/prompts/{prompt_id}/datasets", response_class=HTMLResponse)
def prompt_datasets_page(request: Request, prompt_id: str):
    from pvm.eval_pipeline.pvm_storage import list_query_datasets
    project = get_project()
    info = project.get_prompt_info(prompt_id)
    datasets = list_query_datasets(_pvm_dir(project), prompt_id)
    for ds in datasets:
        ds["registered_at_fmt"] = _format_timestamp(ds.get("registered_at", ""))
    return _render(request, "prompt_datasets.html",
        info=info,
        datasets=datasets,
    )


@app.post("/prompts/{prompt_id}/datasets/upload")
async def prompt_datasets_upload(
    prompt_id: str,
    csv_file: UploadFile = File(...),
    name: str = Form(""),
):
    import tempfile
    from pvm.eval_pipeline.pvm_storage import register_query_dataset
    project = get_project()
    content = await csv_file.read()
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    try:
        register_query_dataset(
            _pvm_dir(project), prompt_id, tmp_path,
            name=name or csv_file.filename or "",
        )
    finally:
        tmp_path.unlink(missing_ok=True)
    return RedirectResponse(f"/prompts/{prompt_id}/datasets", status_code=303)


@app.post("/prompts/{prompt_id}/datasets/{dataset_id}/delete")
def prompt_datasets_delete(prompt_id: str, dataset_id: str):
    from pvm.eval_pipeline.pvm_storage import delete_query_dataset
    project = get_project()
    delete_query_dataset(_pvm_dir(project), prompt_id, dataset_id)
    return RedirectResponse(f"/prompts/{prompt_id}/datasets", status_code=303)


@app.get("/prompts/{prompt_id}/datasets/api/list")
def prompt_datasets_api_list(prompt_id: str):
    from pvm.eval_pipeline.pvm_storage import list_query_datasets
    project = get_project()
    datasets = list_query_datasets(_pvm_dir(project), prompt_id)
    for ds in datasets:
        ds["registered_at_fmt"] = _format_timestamp(ds.get("registered_at", ""))
    return JSONResponse(datasets)


@app.get("/prompts/{prompt_id}/version/{version}/eval/new", response_class=HTMLResponse)
def eval_new_form(request: Request, prompt_id: str, version: str):
    project = get_project()
    info = project.get_prompt_info(prompt_id)
    prompt_data = project.get_prompt(prompt_id, version=version)
    recommended_dataset = _recommended_dataset_for_version(project, prompt_id, version)
    return _render(request, "eval_start.html",
        info=info,
        version=version,
        prompt_data=prompt_data,
        eval_configured=is_configured(),
        recommended_dataset=recommended_dataset,
    )


@app.post("/prompts/{prompt_id}/version/{version}/eval/start")
async def eval_start(
    request: Request,
    prompt_id: str,
    version: str,
    csv_file: UploadFile | None = File(None),
    response_file: UploadFile | None = File(None),
    query_dataset_id: str = Form(""),
    provider: str = Form("openai"),
    model: str = Form("gpt-4.1"),
    judge_type: str = Form("pointwise"),
    reuse_run_hash: str = Form(""),
    reuse_from_version: str = Form(""),
    reuse_csv_hash: str = Form(""),
):
    project = get_project()
    recommended_dataset = _recommended_dataset_for_version(project, prompt_id, version)

    from pvm.eval_pipeline.pvm_storage import create_pipeline_run, register_csv
    prompt_data = project.get_prompt(prompt_id, version=version)
    system_prompt = prompt_data.get("prompt", "")
    pvm_dir = _pvm_dir(project)

    # CSV 결정: (1) query+response join 모드 / (2) 기존 재사용 / (3) 전체 CSV 업로드
    import json as _json2
    import tempfile as _tempfile
    registered_csv: Path | None = None
    csv_hash = ""

    def _eval_error(msg: str):
        return _render(
            request, "eval_start.html",
            info=project.get_prompt_info(prompt_id),
            version=version,
            prompt_data=project.get_prompt(prompt_id, version=version),
            eval_configured=is_configured(),
            recommended_dataset=recommended_dataset,
            error=msg,
        )

    # (1) query dataset + response CSV join 모드
    if query_dataset_id:
        from pvm.eval_pipeline.pvm_storage import join_query_and_response, register_csv as _reg_csv
        if response_file is None or not response_file.filename:
            return _eval_error("Response CSV를 업로드해주세요.")
        resp_content = await response_file.read()
        with _tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp.write(resp_content)
            resp_tmp = Path(tmp.name)
        try:
            joined_path, missing = join_query_and_response(
                pvm_dir, prompt_id, query_dataset_id, resp_tmp
            )
        except FileNotFoundError:
            resp_tmp.unlink(missing_ok=True)
            return _eval_error("선택한 Query Dataset을 찾을 수 없습니다.")
        finally:
            resp_tmp.unlink(missing_ok=True)

        if missing:
            joined_path.unlink(missing_ok=True)
            return _eval_error(
                f"Response CSV에 Query Dataset에 없는 trace_id가 {len(missing)}개 있습니다: "
                + ", ".join(missing[:5]) + ("..." if len(missing) > 5 else "")
            )
        csv_hash, registered_csv = _reg_csv(pvm_dir, joined_path,
                                             original_path=Path(response_file.filename))
        joined_path.unlink(missing_ok=True)
        # 업로드된 response 파일명으로 meta 갱신
        if response_file.filename:
            _mp = pvm_dir / "datasets" / csv_hash / "meta.json"
            if _mp.exists():
                _m = _json2.loads(_mp.read_text(encoding="utf-8"))
                _m["original_name"] = response_file.filename
                _m["query_dataset_id"] = query_dataset_id
                _mp.write_text(_json2.dumps(_m, ensure_ascii=False, indent=2), encoding="utf-8")

    elif reuse_csv_hash:
        candidate = pvm_dir / "datasets" / reuse_csv_hash / "data.csv"
        if not candidate.exists():
            return _render(
                request,
                "eval_start.html",
                info=project.get_prompt_info(prompt_id),
                version=version,
                prompt_data=prompt_data,
                eval_configured=is_configured(),
                recommended_dataset=recommended_dataset,
                error="선택한 기존 CSV를 찾을 수 없습니다. 다시 선택해주세요.",
            )
        csv_hash = reuse_csv_hash
        registered_csv = candidate
    else:
        if csv_file is None or not csv_file.filename:
            return _render(
                request,
                "eval_start.html",
                info=project.get_prompt_info(prompt_id),
                version=version,
                prompt_data=prompt_data,
                eval_configured=is_configured(),
                recommended_dataset=recommended_dataset,
                error="새 CSV를 업로드하거나 기존 CSV를 선택해주세요.",
            )

        import tempfile

        content = await csv_file.read()
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp.write(content)
            tmp_csv = Path(tmp.name)

        csv_hash, registered_csv = register_csv(pvm_dir, tmp_csv)
        tmp_csv.unlink(missing_ok=True)

        # 업로드된 실제 파일명으로 meta.json 갱신 (임시파일명 덮어쓰기)
        if csv_file.filename:
            meta_path = pvm_dir / "datasets" / csv_hash / "meta.json"
            if meta_path.exists():
                _meta = _json2.loads(meta_path.read_text(encoding="utf-8"))
                _meta["original_name"] = csv_file.filename
                meta_path.write_text(_json2.dumps(_meta, ensure_ascii=False, indent=2), encoding="utf-8")

    assert registered_csv is not None

    # 파이프라인 실행 디렉토리 생성
    pipeline_hash, run_dir = create_pipeline_run(
        pvm_root=pvm_dir,
        prompt_id=prompt_id,
        prompt_version=version,
        judge_type=judge_type,
        csv_hash=csv_hash,
        judge_model=model,
        judge_provider=provider,
    )

    # Step 0: config.yaml 생성
    result = run_step0_sync(
        run_dir=run_dir,
        csv_path=registered_csv,
        system_prompt=system_prompt,
        provider=provider,
        model=model,
        judge_type=judge_type,
        prompt_id=prompt_id,
    )
    if not result["success"]:
        return _render(request, "eval_start.html",
            info=project.get_prompt_info(prompt_id),
            version=version,
            prompt_data=prompt_data,
            eval_configured=is_configured(),
            recommended_dataset=recommended_dataset,
            error=result["output"],
        )

    # config.yaml에 pvm_ref + output_dir 추가
    patch_config_for_pvm(run_dir, {
        "prompt_id": prompt_id,
        "version": version,
        "pipeline_hash": pipeline_hash,
        "csv_hash": csv_hash,
        "pvm_root": str(project.root),
    })

    # criteria 재사용: 이전 run의 error_analysis.json + judge_components/ 복사
    if reuse_run_hash and reuse_from_version:
        import shutil as _shutil
        src_run = (project.root / ".pvm" / "prompts" / prompt_id
                   / "versions" / reuse_from_version / "judge" / reuse_run_hash)
        src_analysis = src_run / "error_analysis.json"
        src_components = src_run / "judge_components"
        if src_analysis.exists():
            _shutil.copy2(src_analysis, run_dir / "error_analysis.json")
        if src_components.exists():
            dest_components = run_dir / "judge_components"
            if dest_components.exists():
                _shutil.rmtree(dest_components)
            _shutil.copytree(src_components, dest_components)
        # step3로 바로 진입
        return RedirectResponse(
            f"/prompts/{prompt_id}/version/{version}/eval/{pipeline_hash}/step3",
            status_code=303,
        )

    return RedirectResponse(
        f"/prompts/{prompt_id}/version/{version}/eval/{pipeline_hash}/step1",
        status_code=303,
    )


def _eval_ctx(project, prompt_id: str, version: str, pipeline_hash: str) -> dict:
    import json as _json
    run_dir = _run_dir(project, prompt_id, version, pipeline_hash)
    step_status = get_run_status(run_dir)

    # pipeline_meta.json에서 실행 시각 읽기
    created_at = ""
    meta_path = run_dir / "pipeline_meta.json"
    if meta_path.exists():
        try:
            meta = _json.loads(meta_path.read_text(encoding="utf-8"))
            raw = meta.get("created_at", "")
            if raw:
                from datetime import timezone as _tz
                dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                created_at = dt.astimezone(_tz.utc).strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            pass

    return {
        "info": project.get_prompt_info(prompt_id),
        "version": version,
        "pipeline_hash": pipeline_hash,
        "created_at": created_at,
        "run_dir": run_dir,
        "step_status": step_status,
        "eval_url_base": f"/prompts/{prompt_id}/version/{version}/eval/{pipeline_hash}",
    }


# ── Step 1 ────────────────────────────────────────────────────────────────────

@app.get("/prompts/{prompt_id}/version/{version}/eval/{pipeline_hash}/step1", response_class=HTMLResponse)
def eval_step1(request: Request, prompt_id: str, version: str, pipeline_hash: str):
    project = get_project()
    ctx = _eval_ctx(project, prompt_id, version, pipeline_hash)
    run_dir = ctx["run_dir"]
    ctx.update({
        "result": load_json(run_dir, "error_analysis.json"),
        "run_log": load_log(prompt_id, version, pipeline_hash, 1),
        "is_running": is_running(prompt_id, version, pipeline_hash, 1),
    })
    return _render(request, "eval_step1.html", **ctx)


@app.post("/prompts/{prompt_id}/version/{version}/eval/{pipeline_hash}/step1/run")
def eval_step1_run(prompt_id: str, version: str, pipeline_hash: str):
    project = get_project()
    run_dir = _run_dir(project, prompt_id, version, pipeline_hash)
    start_step_async(prompt_id, version, pipeline_hash, 1, run_dir)
    return RedirectResponse(
        f"/prompts/{prompt_id}/version/{version}/eval/{pipeline_hash}/step1",
        status_code=303,
    )


@app.get("/prompts/{prompt_id}/version/{version}/eval/{pipeline_hash}/step1/status")
def eval_step1_status(prompt_id: str, version: str, pipeline_hash: str):
    status = get_step_status(prompt_id, version, pipeline_hash, 1)
    return JSONResponse({"status": status, "log": load_log(prompt_id, version, pipeline_hash, 1) or ""})


@app.post("/prompts/{prompt_id}/version/{version}/eval/{pipeline_hash}/step1/stop")
def eval_step1_stop(prompt_id: str, version: str, pipeline_hash: str):
    stop_step(prompt_id, version, pipeline_hash, 1)
    return RedirectResponse(
        f"/prompts/{prompt_id}/version/{version}/eval/{pipeline_hash}/step1",
        status_code=303,
    )


@app.post("/prompts/{prompt_id}/version/{version}/eval/{pipeline_hash}/step1/update-actions")
async def eval_step1_update_actions(
    request: Request,
    prompt_id: str,
    version: str,
    pipeline_hash: str,
):
    """code_check 카테고리를 Judge에 포함할지 여부를 error_analysis.json에 반영."""
    form = await request.form()
    include_ids = set(form.getlist("include_ids"))
    code_check_ids = set(form.getlist("code_check_ids"))

    project = get_project()
    run_dir = _run_dir(project, prompt_id, version, pipeline_hash)
    ea_path = run_dir / "error_analysis.json"

    if ea_path.exists():
        import json as _json
        data = _json.loads(ea_path.read_text(encoding="utf-8"))
        for cat in data.get("categories", []):
            if cat["id"] not in code_check_ids:
                continue
            # 최초 토글 시 original_action 보존
            if "original_action" not in cat:
                cat["original_action"] = cat["action"]
            cat["action"] = "judge_prompt" if cat["id"] in include_ids else "code_check"
        ea_path.write_text(
            _json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    return RedirectResponse(
        f"/prompts/{prompt_id}/version/{version}/eval/{pipeline_hash}/step1",
        status_code=303,
    )


@app.get("/prompts/{prompt_id}/version/{version}/eval/{pipeline_hash}/step1/failures/{category_id}")
def eval_step1_failures(prompt_id: str, version: str, pipeline_hash: str, category_id: str):
    """특정 카테고리에서 Fail로 분류된 트레이스 목록을 JSON으로 반환."""
    import csv as _csv
    import json as _json
    import yaml as _yaml

    project = get_project()
    run_dir = _run_dir(project, prompt_id, version, pipeline_hash)

    ea_path = run_dir / "error_analysis.json"
    if not ea_path.exists():
        return JSONResponse({"error": "error_analysis.json 없음"}, status_code=404)
    ea = _json.loads(ea_path.read_text(encoding="utf-8"))

    # 해당 카테고리에서 Fail인 trace_id 수집
    trace_labels = ea.get("trace_labels", {})
    fail_ids = {tid for tid, labels in trace_labels.items() if labels.get(category_id) == "Fail"}
    if not fail_ids:
        return JSONResponse({"cases": [], "total": 0})

    # config.yaml에서 column 매핑 로드
    config_path = run_dir / "config.yaml"
    if not config_path.exists():
        return JSONResponse({"error": "config.yaml 없음"}, status_code=404)
    cfg = _yaml.safe_load(config_path.read_text(encoding="utf-8"))
    cols = cfg.get("columns", {})
    tid_col = cols.get("trace_id", "trace_id")
    ui_col = cols.get("user_input", "")
    lo_col = cols.get("llm_output", "")
    conv_col = cols.get("conversation", "")
    hl_col = cols.get("human_label", "")
    hr_col = cols.get("human_reason", "")

    # CSV에서 해당 rows 추출
    csv_path = run_dir / "config.yaml"  # config에서 input_csv 경로 사용
    input_csv = cfg.get("input_csv", "")
    if not input_csv or not Path(input_csv).exists():
        # pipeline_meta.json → csv_hash 경로로 fallback
        meta_path = run_dir / "pipeline_meta.json"
        if not meta_path.exists():
            return JSONResponse({"error": "CSV 경로를 찾을 수 없음"}, status_code=404)
        meta = _json.loads(meta_path.read_text(encoding="utf-8"))
        csv_hash = meta.get("csv_hash", "")
        input_csv = str(_pvm_dir(project) / "datasets" / csv_hash / "data.csv")

    cases = []
    try:
        with open(input_csv, encoding="utf-8-sig") as f:
            for row in _csv.DictReader(f):
                tid = (row.get(tid_col) or "").strip()
                if tid not in fail_ids:
                    continue
                user_input = row.get(ui_col, "") if ui_col else ""
                llm_output = row.get(lo_col, "") if lo_col else ""
                conversation = row.get(conv_col, "") if conv_col else ""
                human_label = row.get(hl_col, "") if hl_col else ""
                human_reason = row.get(hr_col, "") if hr_col else ""
                cases.append({
                    "trace_id": tid,
                    "user_input": user_input,
                    "llm_output": llm_output,
                    "conversation": conversation,
                    "human_label": human_label,
                    "human_reason": human_reason,
                })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

    return JSONResponse({"cases": cases, "total": len(cases)})


# ── Step 2 ────────────────────────────────────────────────────────────────────

@app.get("/prompts/{prompt_id}/version/{version}/eval/{pipeline_hash}/step2", response_class=HTMLResponse)
def eval_step2(request: Request, prompt_id: str, version: str, pipeline_hash: str):
    project = get_project()
    ctx = _eval_ctx(project, prompt_id, version, pipeline_hash)
    run_dir = ctx["run_dir"]
    ctx.update({
        "result": load_step2_yaml(run_dir),
        "run_log": load_log(prompt_id, version, pipeline_hash, 2),
        "is_running": is_running(prompt_id, version, pipeline_hash, 2),
    })
    return _render(request, "eval_step2.html", **ctx)


@app.post("/prompts/{prompt_id}/version/{version}/eval/{pipeline_hash}/step2/run")
def eval_step2_run(prompt_id: str, version: str, pipeline_hash: str):
    project = get_project()
    run_dir = _run_dir(project, prompt_id, version, pipeline_hash)
    start_step_async(prompt_id, version, pipeline_hash, 2, run_dir)
    return RedirectResponse(
        f"/prompts/{prompt_id}/version/{version}/eval/{pipeline_hash}/step2",
        status_code=303,
    )


@app.get("/prompts/{prompt_id}/version/{version}/eval/{pipeline_hash}/step2/status")
def eval_step2_status(prompt_id: str, version: str, pipeline_hash: str):
    status = get_step_status(prompt_id, version, pipeline_hash, 2)
    return JSONResponse({"status": status, "log": load_log(prompt_id, version, pipeline_hash, 2) or ""})


@app.post("/prompts/{prompt_id}/version/{version}/eval/{pipeline_hash}/step2/stop")
def eval_step2_stop(prompt_id: str, version: str, pipeline_hash: str):
    stop_step(prompt_id, version, pipeline_hash, 2)
    return RedirectResponse(
        f"/prompts/{prompt_id}/version/{version}/eval/{pipeline_hash}/step2",
        status_code=303,
    )


@app.post("/prompts/{prompt_id}/version/{version}/eval/{pipeline_hash}/step2/criteria/save")
async def eval_step2_criteria_save(
    request: Request,
    prompt_id: str,
    version: str,
    pipeline_hash: str,
):
    """Criteria 텍스트를 직접 수정하여 저장. 타임스탬프 YAML을 생성해 재사용 목록에도 노출."""
    import yaml as _yaml
    from datetime import datetime as _dt

    form = await request.form()
    new_criteria = form.get("criteria", "").strip()
    if not new_criteria:
        return RedirectResponse(
            f"/prompts/{prompt_id}/version/{version}/eval/{pipeline_hash}/step2",
            status_code=303,
        )

    project = get_project()
    run_dir = _run_dir(project, prompt_id, version, pipeline_hash)
    comp_dir = run_dir / "judge_components"
    comp_dir.mkdir(parents=True, exist_ok=True)

    # 현재 YAML 로드 (few_shot 등 나머지 필드 유지)
    import json as _json
    existing = load_step2_yaml(run_dir) or {}
    existing["criteria"] = new_criteria

    # 1) 타임스탬프 버전 저장 (재사용 목록용)
    ts = _dt.now().strftime("%Y%m%d_%H%M%S")
    ts_path = comp_dir / f"{prompt_id}_judge_{ts}.yaml"
    ts_path.write_text(
        _yaml.dump(existing, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )

    # 2) 현재 canonical YAML도 갱신 (judge.yaml 또는 기존 *_judge.yaml 중 최신)
    canonical = comp_dir / "judge.yaml"
    all_files = list(comp_dir.glob("*_judge.yaml"))
    if not canonical.exists() and all_files:
        candidates = [p for p in all_files if not p.name.count("_") >= 3]  # 타임스탬프 없는 것 우선
        canonical = candidates[0] if candidates else all_files[0]
    canonical.write_text(
        _yaml.dump(existing, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )

    return RedirectResponse(
        f"/prompts/{prompt_id}/version/{version}/eval/{pipeline_hash}/step2",
        status_code=303,
    )


# ── Step 3 ────────────────────────────────────────────────────────────────────

@app.get("/prompts/{prompt_id}/version/{version}/eval/{pipeline_hash}/step3", response_class=HTMLResponse)
def eval_step3(request: Request, prompt_id: str, version: str, pipeline_hash: str):
    project = get_project()
    ctx = _eval_ctx(project, prompt_id, version, pipeline_hash)
    run_dir = ctx["run_dir"]
    ctx.update({
        "judge_data": load_json(run_dir, "judge_results.json"),
        "run_log": load_log(prompt_id, version, pipeline_hash, 3),
        "is_running": is_running(prompt_id, version, pipeline_hash, 3),
    })
    return _render(request, "eval_step3.html", **ctx)


@app.post("/prompts/{prompt_id}/version/{version}/eval/{pipeline_hash}/step3/run")
def eval_step3_run(prompt_id: str, version: str, pipeline_hash: str):
    project = get_project()
    run_dir = _run_dir(project, prompt_id, version, pipeline_hash)
    start_step_async(prompt_id, version, pipeline_hash, 3, run_dir)
    return RedirectResponse(
        f"/prompts/{prompt_id}/version/{version}/eval/{pipeline_hash}/step3",
        status_code=303,
    )


@app.get("/prompts/{prompt_id}/version/{version}/eval/{pipeline_hash}/step3/status")
def eval_step3_status(prompt_id: str, version: str, pipeline_hash: str):
    status = get_step_status(prompt_id, version, pipeline_hash, 3)
    return JSONResponse({"status": status, "log": load_log(prompt_id, version, pipeline_hash, 3) or ""})


@app.post("/prompts/{prompt_id}/version/{version}/eval/{pipeline_hash}/step3/stop")
def eval_step3_stop(prompt_id: str, version: str, pipeline_hash: str):
    stop_step(prompt_id, version, pipeline_hash, 3)
    return RedirectResponse(
        f"/prompts/{prompt_id}/version/{version}/eval/{pipeline_hash}/step3",
        status_code=303,
    )


# ── Report ────────────────────────────────────────────────────────────────────

@app.get("/prompts/{prompt_id}/version/{version}/eval/{pipeline_hash}/report", response_class=HTMLResponse)
def eval_report(request: Request, prompt_id: str, version: str, pipeline_hash: str):
    project = get_project()
    ctx = _eval_ctx(project, prompt_id, version, pipeline_hash)
    run_dir = ctx["run_dir"]
    ctx["judge_data"] = load_json(run_dir, "judge_results.json")
    if not ctx["judge_data"]:
        return RedirectResponse(
            f"/prompts/{prompt_id}/version/{version}/eval/{pipeline_hash}/step3"
        )
    return _render(request, "eval_report.html", **ctx)


# ── Pairwise Compare ──────────────────────────────────────────────────────────

def _compare_run_dir(project, prompt_id: str, compare_hash: str) -> Path:
    return project.root / ".pvm" / "prompts" / prompt_id / "compare" / compare_hash


_JOIN_KEY_CANDIDATES = [
    "trace_id",
    "scenario_id",
    "id",
    "sample_id",
    "row_id",
    "index",
    "conversation_id",
]


def _compare_available_runs(project, prompt_id: str, version: str) -> list:
    """버전에서 CSV가 있는 eval 실행 목록 반환."""
    runs = []
    judge_dir = project.root / ".pvm" / "prompts" / prompt_id / "versions" / version / "judge"
    if not judge_dir.exists():
        return runs
    for run_dir in sorted(judge_dir.iterdir(), key=_meta_created_at, reverse=True):
        if not run_dir.is_dir():
            continue
        meta_path = run_dir / "pipeline_meta.json"
        if not meta_path.exists():
            continue
        try:
            meta = _json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        csv_info = _resolve_run_csv_info(project, run_dir, meta)
        if csv_info is None:
            continue
        step_status = get_run_status(run_dir)
        runs.append({
            "hash": run_dir.name,
            "created_at": _format_timestamp(meta.get("created_at", "")),
            "judge_model": meta.get("judge_model", ""),
            "csv_hash": csv_info.get("csv_hash", ""),
            "csv_filename": csv_info.get("csv_filename", csv_info["csv_path"].name),
            "step3_done": step_status["step3"],
        })
    return runs


def _compare_csv_path(project, prompt_id: str, version: str, run_hash: str) -> Path:
    run_dir = _pvm_dir(project) / "prompts" / prompt_id / "versions" / version / "judge" / run_hash
    meta = _json.loads((run_dir / "pipeline_meta.json").read_text(encoding="utf-8"))
    csv_info = _resolve_run_csv_info(project, run_dir, meta)
    if csv_info is None:
        raise FileNotFoundError(f"CSV를 찾을 수 없음: {run_dir}")
    return csv_info["csv_path"]


def _load_csv_rows_and_columns(csv_path: Path) -> tuple[list[dict], list[str]]:
    import csv as _cm

    with open(csv_path, encoding="utf-8-sig") as f:
        rows = list(_cm.DictReader(f))
    columns = list(rows[0].keys()) if rows else []
    return rows, columns


def _normalize_join_value(value: object) -> str:
    return str(value or "").strip()


def _match_count_for_keys(rows_a: list[dict], key_a: str, rows_b: list[dict], key_b: str) -> tuple[int, int, int]:
    keys_a = {_normalize_join_value(row.get(key_a, "")) for row in rows_a}
    keys_a.discard("")
    keys_b = {_normalize_join_value(row.get(key_b, "")) for row in rows_b}
    keys_b.discard("")
    matched = len(keys_a & keys_b)
    return matched, len(keys_a - keys_b), len(keys_b - keys_a)


def _detect_compare_join_keys(rows_a: list[dict], cols_a: list[str], rows_b: list[dict], cols_b: list[str]) -> dict:
    shared_candidates = [col for col in _JOIN_KEY_CANDIDATES if col in cols_a and col in cols_b]
    candidates: list[dict] = []
    for col in shared_candidates:
        matched, only_a, only_b = _match_count_for_keys(rows_a, col, rows_b, col)
        candidates.append({
            "key_a": col,
            "key_b": col,
            "matched": matched,
            "only_a": only_a,
            "only_b": only_b,
        })

    candidates.sort(
        key=lambda item: (
            item["matched"],
            -_JOIN_KEY_CANDIDATES.index(item["key_a"]) if item["key_a"] in _JOIN_KEY_CANDIDATES else 0,
        ),
        reverse=True,
    )

    recommended = next((item for item in candidates if item["matched"] > 0), None)
    return {
        "columns_a": cols_a,
        "columns_b": cols_b,
        "candidates": candidates,
        "recommended": recommended,
    }


def _build_pairwise_csv(
    project, prompt_id: str,
    version_a: str, run_a_hash: str,
    version_b: str, run_b_hash: str,
    compare_dir: Path,
    join_key_a: str | None = None,
    join_key_b: str | None = None,
) -> tuple:
    """두 eval run의 CSV를 trace_id 기준으로 조인해 pairwise CSV를 생성한다."""
    import csv as _cm
    csv_a = _compare_csv_path(project, prompt_id, version_a, run_a_hash)
    csv_b = _compare_csv_path(project, prompt_id, version_b, run_b_hash)
    rows_a_raw, cols_a = _load_csv_rows_and_columns(csv_a)
    rows_b_raw, cols_b = _load_csv_rows_and_columns(csv_b)

    if not join_key_a or not join_key_b:
        detection = _detect_compare_join_keys(rows_a_raw, cols_a, rows_b_raw, cols_b)
        recommended = detection.get("recommended")
        if recommended is None:
            raise ValueError("자동으로 일치하는 join key를 찾지 못했습니다. 수동으로 선택해주세요.")
        join_key_a = recommended["key_a"]
        join_key_b = recommended["key_b"]

    rows_a: dict[str, dict] = {}
    for row in rows_a_raw:
        tid = _normalize_join_value(row.get(join_key_a, ""))
        if tid:
            rows_a[tid] = row

    combined = []
    only_b = 0
    for row_b in rows_b_raw:
        tid = _normalize_join_value(row_b.get(join_key_b, ""))
        if not tid:
            continue
        row_a = rows_a.pop(tid, None)
        if row_a is None:
            only_b += 1
            continue
        combined.append({
            "trace_id": tid,
            "scenario_id": row_b.get("scenario_id", row_a.get("scenario_id", "")),
            "user_input": row_a.get("user_input", ""),
            "response_a": row_a.get("llm_output", ""),   # version A 응답
            "llm_output": row_b.get("llm_output", ""),   # version B 응답
            "winner": "",
            "human_reason": "",
            "category": "",
            "few_shot_type": "",
        })

    compare_dir.mkdir(parents=True, exist_ok=True)
    combined_path = compare_dir / "combined.csv"
    fieldnames = ["trace_id", "scenario_id", "user_input",
                  "response_a", "llm_output", "winner",
                  "human_reason", "category", "few_shot_type"]
    with open(combined_path, "w", encoding="utf-8", newline="") as f:
        writer = _cm.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(combined)

    stats = {
        "matched": len(combined),
        "only_a": len(rows_a),
        "only_b": only_b,
        "join_key_a": join_key_a,
        "join_key_b": join_key_b,
    }
    return combined_path, stats


def _compare_ctx(project, prompt_id: str, compare_hash: str) -> dict:
    compare_dir = _compare_run_dir(project, prompt_id, compare_hash)
    step_status = get_run_status(compare_dir)
    meta: dict = {}
    meta_path = compare_dir / "compare_meta.json"
    if meta_path.exists():
        try:
            meta = _json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    created_at = ""
    raw = meta.get("created_at", "")
    if raw:
        from datetime import timezone as _tz2
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        created_at = dt.astimezone(_tz2.utc).strftime("%Y-%m-%d %H:%M UTC")
    return {
        "info": project.get_prompt_info(prompt_id),
        "compare_hash": compare_hash,
        "version_a": meta.get("version_a", "?"),
        "version_b": meta.get("version_b", "?"),
        "compare_meta": meta,
        "created_at": created_at,
        "compare_dir": compare_dir,
        "step_status": step_status,
        "compare_url_base": f"/prompts/{prompt_id}/compare/{compare_hash}",
    }


@app.get("/prompts/{prompt_id}/compare", response_class=HTMLResponse)
def compare_setup(request: Request, prompt_id: str):
    project = get_project()
    info = project.get_prompt_info(prompt_id)
    versions = project.list_prompt_versions(prompt_id)
    return _render(request, "compare_setup.html", info=info, versions=versions)


@app.get("/prompts/{prompt_id}/compare/history", response_class=HTMLResponse)
def compare_history(request: Request, prompt_id: str):
    project = get_project()
    info = project.get_prompt_info(prompt_id)
    history = _get_compare_history(project, prompt_id)
    return _render(request, "compare_history.html", info=info, history=history)


@app.get("/prompts/{prompt_id}/compare/api/runs/{version}")
def compare_api_runs(prompt_id: str, version: str):
    project = get_project()
    return JSONResponse(_compare_available_runs(project, prompt_id, version))


@app.get("/prompts/{prompt_id}/compare/api/reusable-runs")
def compare_api_reusable_runs(prompt_id: str):
    project = get_project()
    return JSONResponse(_eval_runs_with_criteria(project, prompt_id))


@app.get("/prompts/{prompt_id}/compare/api/join-preview")
def compare_api_join_preview(
    prompt_id: str,
    version_a: str,
    run_a_hash: str,
    version_b: str,
    run_b_hash: str,
    key_a: str = "",
    key_b: str = "",
):
    project = get_project()
    try:
        csv_a = _compare_csv_path(project, prompt_id, version_a, run_a_hash)
        csv_b = _compare_csv_path(project, prompt_id, version_b, run_b_hash)
        rows_a, cols_a = _load_csv_rows_and_columns(csv_a)
        rows_b, cols_b = _load_csv_rows_and_columns(csv_b)
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)

    detection = _detect_compare_join_keys(rows_a, cols_a, rows_b, cols_b)
    preview = None
    if key_a and key_b:
        matched, only_a, only_b = _match_count_for_keys(rows_a, key_a, rows_b, key_b)
        preview = {
            "key_a": key_a,
            "key_b": key_b,
            "matched": matched,
            "only_a": only_a,
            "only_b": only_b,
        }

    return JSONResponse({
        "ok": True,
        **detection,
        "preview": preview,
    })


@app.post("/prompts/{prompt_id}/compare/start")
async def compare_start(request: Request, prompt_id: str):
    import hashlib
    import shutil as _shutil
    from datetime import timezone as _tz3

    project = get_project()
    form = await request.form()
    mode = form.get("mode", "from_runs")
    if mode == "from_runs":
        version_a = str(form.get("version_a", ""))
        version_b = str(form.get("version_b", ""))
    else:
        version_a = str(form.get("version_a_csv", ""))
        version_b = str(form.get("version_b_csv", ""))
    run_a_hash = str(form.get("run_a_hash", ""))
    run_b_hash = str(form.get("run_b_hash", ""))
    join_key_a = str(form.get("join_key_a", "")).strip()
    join_key_b = str(form.get("join_key_b", "")).strip()
    reuse_run_hash = str(form.get("reuse_run_hash", "")).strip()
    reuse_from_version = str(form.get("reuse_from_version", "")).strip()
    provider = form.get("provider", "openai")
    model = form.get("model", "gpt-4.1")

    info = project.get_prompt_info(prompt_id)
    versions = project.list_prompt_versions(prompt_id)

    def _err(msg: str):
        return _render(request, "compare_setup.html",
            info=info, versions=versions, error=msg)

    if not version_a or not version_b:
        return _err("버전 A와 버전 B를 모두 선택해주세요.")

    compare_hash = hashlib.sha256(
        f"{mode}:{version_a}:{run_a_hash}:{version_b}:{run_b_hash}:{provider}:{model}:{reuse_from_version}:{reuse_run_hash}".encode()
    ).hexdigest()[:12]
    compare_dir = _compare_run_dir(project, prompt_id, compare_hash)

    if mode == "from_runs":
        if not run_a_hash or not run_b_hash:
            return _err("각 버전의 eval 실행을 선택해주세요.")
        try:
            csv_path, stats = _build_pairwise_csv(
                project, prompt_id, version_a, run_a_hash, version_b, run_b_hash, compare_dir,
                join_key_a=join_key_a or None,
                join_key_b=join_key_b or None,
            )
        except Exception as e:
            return _err(f"CSV 조인 실패: {e}")
        if stats["matched"] == 0:
            return _err("두 eval 실행 간에 trace_id가 일치하는 케이스가 없습니다.")
    else:
        csv_file = form.get("csv_file")
        if not csv_file or not csv_file.filename:
            return _err("CSV 파일을 업로드해주세요.")
        compare_dir.mkdir(parents=True, exist_ok=True)
        content = await csv_file.read()
        csv_path = compare_dir / "combined.csv"
        csv_path.write_bytes(content)
        stats = {"matched": 0, "only_a": 0, "only_b": 0}

    # version A의 system prompt 사용
    system_prompt = project.get_prompt(prompt_id, version=version_a).get("prompt", "")

    result = run_step0_sync(
        run_dir=compare_dir,
        csv_path=csv_path,
        system_prompt=system_prompt,
        provider=provider,
        model=model,
        judge_type="pairwise",
        prompt_id=prompt_id,
    )
    if not result["success"]:
        return _err(f"Step 0 실패:\n{result['output']}")

    patch_config_for_pvm(compare_dir, {
        "compare_hash": compare_hash,
        "prompt_id": prompt_id,
        "version_a": version_a,
        "run_a_hash": run_a_hash,
        "version_b": version_b,
        "run_b_hash": run_b_hash,
        "pvm_root": str(project.root),
    })

    if reuse_run_hash and reuse_from_version:
        src_run = (
            project.root / ".pvm" / "prompts" / prompt_id
            / "versions" / reuse_from_version / "judge" / reuse_run_hash
        )
        src_analysis = src_run / "error_analysis.json"
        if src_analysis.exists():
            _shutil.copy2(src_analysis, compare_dir / "error_analysis.json")

    compare_meta = {
        "compare_hash": compare_hash,
        "prompt_id": prompt_id,
        "version_a": version_a,
        "run_a_hash": run_a_hash,
        "version_b": version_b,
        "run_b_hash": run_b_hash,
        "judge_provider": provider,
        "judge_model": model,
        "matched_traces": stats["matched"],
        "only_a": stats["only_a"],
        "only_b": stats["only_b"],
        "join_key_a": stats.get("join_key_a", join_key_a),
        "join_key_b": stats.get("join_key_b", join_key_b),
        "step1_skipped": True,
        "criteria_source_version": reuse_from_version,
        "criteria_source_run_hash": reuse_run_hash,
        "created_at": datetime.now(_tz3.utc).isoformat(),
    }
    (compare_dir / "compare_meta.json").write_text(
        _json.dumps(compare_meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return RedirectResponse(
        f"/prompts/{prompt_id}/compare/{compare_hash}/step2", status_code=303
    )


def _compare_step_key(compare_hash: str, step: int) -> str:
    return f"__compare__{compare_hash}__step{step}"


@app.get("/prompts/{prompt_id}/compare/{compare_hash}/step1", response_class=HTMLResponse)
def compare_step1(request: Request, prompt_id: str, compare_hash: str):
    project = get_project()
    ctx = _compare_ctx(project, prompt_id, compare_hash)
    run_dir = ctx["compare_dir"]
    ctx.update({
        "result": load_json(run_dir, "error_analysis.json"),
        "run_log": load_log(_compare_step_key(compare_hash, 1), "", "", 1),
        "is_running": get_step_status(_compare_step_key(compare_hash, 1), "", "", 1) == "running",
    })
    return _render(request, "compare_step1.html", **ctx)


@app.post("/prompts/{prompt_id}/compare/{compare_hash}/step1/run")
def compare_step1_run(prompt_id: str, compare_hash: str):
    project = get_project()
    run_dir = _compare_run_dir(project, prompt_id, compare_hash)
    key = _compare_step_key(compare_hash, 1)
    start_step_async(key, "", "", 1, run_dir)
    return RedirectResponse(
        f"/prompts/{prompt_id}/compare/{compare_hash}/step1", status_code=303
    )


@app.get("/prompts/{prompt_id}/compare/{compare_hash}/step1/status")
def compare_step1_status(compare_hash: str):
    key = _compare_step_key(compare_hash, 1)
    return JSONResponse({"status": get_step_status(key, "", "", 1),
                         "log": load_log(key, "", "", 1) or ""})


@app.post("/prompts/{prompt_id}/compare/{compare_hash}/step1/stop")
def compare_step1_stop(prompt_id: str, compare_hash: str):
    key = _compare_step_key(compare_hash, 1)
    stop_step(key, "", "", 1)
    return RedirectResponse(
        f"/prompts/{prompt_id}/compare/{compare_hash}/step1", status_code=303
    )


@app.get("/prompts/{prompt_id}/compare/{compare_hash}/step2", response_class=HTMLResponse)
def compare_step2(request: Request, prompt_id: str, compare_hash: str):
    project = get_project()
    ctx = _compare_ctx(project, prompt_id, compare_hash)
    run_dir = ctx["compare_dir"]
    ctx.update({
        "result": load_step2_yaml(run_dir),
        "run_log": load_log(_compare_step_key(compare_hash, 2), "", "", 2),
        "is_running": get_step_status(_compare_step_key(compare_hash, 2), "", "", 2) == "running",
    })
    return _render(request, "compare_step2.html", **ctx)


@app.post("/prompts/{prompt_id}/compare/{compare_hash}/step2/run")
def compare_step2_run(prompt_id: str, compare_hash: str):
    project = get_project()
    run_dir = _compare_run_dir(project, prompt_id, compare_hash)
    key = _compare_step_key(compare_hash, 2)
    start_step_async(key, "", "", 2, run_dir)
    return RedirectResponse(
        f"/prompts/{prompt_id}/compare/{compare_hash}/step2", status_code=303
    )


@app.get("/prompts/{prompt_id}/compare/{compare_hash}/step2/status")
def compare_step2_status(compare_hash: str):
    key = _compare_step_key(compare_hash, 2)
    return JSONResponse({"status": get_step_status(key, "", "", 2),
                         "log": load_log(key, "", "", 2) or ""})


@app.post("/prompts/{prompt_id}/compare/{compare_hash}/step2/stop")
def compare_step2_stop(prompt_id: str, compare_hash: str):
    key = _compare_step_key(compare_hash, 2)
    stop_step(key, "", "", 2)
    return RedirectResponse(
        f"/prompts/{prompt_id}/compare/{compare_hash}/step2", status_code=303
    )


@app.get("/prompts/{prompt_id}/compare/{compare_hash}/step3", response_class=HTMLResponse)
def compare_step3(request: Request, prompt_id: str, compare_hash: str):
    project = get_project()
    ctx = _compare_ctx(project, prompt_id, compare_hash)
    run_dir = ctx["compare_dir"]
    judge_data = load_json(run_dir, "judge_results.json")
    if judge_data and judge_data.get("results"):
        results = judge_data["results"]
        a_wins = sum(1 for r in results if r.get("judge_verdict") == "A")
        b_wins = sum(1 for r in results if r.get("judge_verdict") == "B")
        ties   = sum(1 for r in results if r.get("judge_verdict") == "SAME")
        total  = len(results)
        judge_data["_summary"] = {
            "a_wins": a_wins, "b_wins": b_wins, "ties": ties, "total": total,
            "a_rate": round(a_wins / total * 100, 1) if total else 0,
            "b_rate": round(b_wins / total * 100, 1) if total else 0,
            "tie_rate": round(ties / total * 100, 1) if total else 0,
        }
    ctx.update({
        "judge_data": judge_data,
        "run_log": load_log(_compare_step_key(compare_hash, 3), "", "", 3),
        "is_running": get_step_status(_compare_step_key(compare_hash, 3), "", "", 3) == "running",
    })
    return _render(request, "compare_step3.html", **ctx)


@app.post("/prompts/{prompt_id}/compare/{compare_hash}/step3/run")
def compare_step3_run(prompt_id: str, compare_hash: str):
    project = get_project()
    run_dir = _compare_run_dir(project, prompt_id, compare_hash)
    key = _compare_step_key(compare_hash, 3)
    start_step_async(key, "", "", 3, run_dir)
    return RedirectResponse(
        f"/prompts/{prompt_id}/compare/{compare_hash}/step3", status_code=303
    )


@app.get("/prompts/{prompt_id}/compare/{compare_hash}/step3/status")
def compare_step3_status(compare_hash: str):
    key = _compare_step_key(compare_hash, 3)
    return JSONResponse({"status": get_step_status(key, "", "", 3),
                         "log": load_log(key, "", "", 3) or ""})


@app.post("/prompts/{prompt_id}/compare/{compare_hash}/step3/stop")
def compare_step3_stop(prompt_id: str, compare_hash: str):
    key = _compare_step_key(compare_hash, 3)
    stop_step(key, "", "", 3)
    return RedirectResponse(
        f"/prompts/{prompt_id}/compare/{compare_hash}/step3", status_code=303
    )


@app.get("/prompts/{prompt_id}/compare/{compare_hash}/report", response_class=HTMLResponse)
def compare_report(request: Request, prompt_id: str, compare_hash: str):
    import csv as _csv2
    project = get_project()
    ctx = _compare_ctx(project, prompt_id, compare_hash)
    run_dir = ctx["compare_dir"]
    judge_data = load_json(run_dir, "judge_results.json")
    if not judge_data:
        return RedirectResponse(f"/prompts/{prompt_id}/compare/{compare_hash}/step3")
    results = judge_data.get("results", [])
    a_wins = sum(1 for r in results if r.get("judge_verdict") == "A")
    b_wins = sum(1 for r in results if r.get("judge_verdict") == "B")
    ties   = sum(1 for r in results if r.get("judge_verdict") == "SAME")
    errors = sum(1 for r in results if r.get("judge_verdict") == "PARSE_ERROR")
    total  = len(results)

    # combined.csv에서 query / response_a / response_b 인덱스 구축
    trace_content: dict = {}
    combined_csv = run_dir / "combined.csv"
    if combined_csv.exists():
        try:
            with open(combined_csv, encoding="utf-8-sig") as f:
                for row in _csv2.DictReader(f):
                    tid = (row.get("trace_id") or "").strip()
                    if tid:
                        trace_content[tid] = {
                            "user_input":  row.get("user_input", "") or row.get("conversation", ""),
                            "response_a":  row.get("response_a", ""),
                            "response_b":  row.get("llm_output", "") or row.get("response_b", ""),
                        }
        except Exception:
            pass

    ctx["judge_data"] = judge_data
    ctx["trace_content"] = trace_content
    ctx["summary"] = {
        "a_wins": a_wins, "b_wins": b_wins, "ties": ties, "errors": errors, "total": total,
        "a_rate": round(a_wins / total * 100, 1) if total else 0,
        "b_rate": round(b_wins / total * 100, 1) if total else 0,
        "tie_rate": round(ties / total * 100, 1) if total else 0,
    }
    return _render(request, "compare_report.html", **ctx)


# ── Review / Annotation Interface ────────────────────────────────────────────

import csv as _csv
import io as _io
import json as _json

_REVIEW_IMPROVE_SYSTEM_PROMPT = """당신은 AI-사용자 대화에 대한 전문 평가자입니다.
사용자가 작성한 critique 초안을 아래 예시처럼 상세하고 구체적인 critique로 개선해주세요.

[예시]
대화:
사용자: "계정에 로그인할 수 없어요. 비밀번호가 틀렸다고 나옵니다."
AI: "'비밀번호 찾기'를 클릭하여 비밀번호를 재설정하세요."

판정: Fail
Critique: AI는 사용자의 불만을 인지하지 못하고 계정 잠금과 같은 다른 문제도 확인하지 않은 채 일반적인 해결책만 제시했습니다. 공감적인 지원이나 추가적인 도움도 제공하지 못했습니다. 개인 맞춤형 지원의 부족과 열악한 사용자 경험으로 인해 실패입니다.

[개선 기준]
1. AI의 구체적인 성공/실패 근거를 명시
2. 빠진 요소나 문제점을 구체적으로 서술
3. 최종 판정 이유를 명확히 마무리
4. 한국어로 작성
5. critique 텍스트만 출력 (다른 설명 없이)"""


def _review_dir(project, prompt_id: str, version: str) -> Path:
    return project.root / ".pvm" / "prompts" / prompt_id / "versions" / version / "review"


def _review_load_labels(project, prompt_id: str, version: str) -> dict:
    p = _review_dir(project, prompt_id, version) / "labels.json"
    if p.exists():
        try:
            return _json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _review_save_labels(project, prompt_id: str, version: str, labels: dict) -> None:
    p = _review_dir(project, prompt_id, version) / "labels.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_json.dumps(labels, ensure_ascii=False, indent=2), encoding="utf-8")


def _review_load_traces(project, prompt_id: str, version: str) -> list:
    p = _review_dir(project, prompt_id, version) / "traces.json"
    if p.exists():
        try:
            return _json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return []
    return []


def _review_save_traces(project, prompt_id: str, version: str, traces: list) -> None:
    p = _review_dir(project, prompt_id, version) / "traces.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_json.dumps(traces, ensure_ascii=False, indent=2), encoding="utf-8")


def _build_conversation_text(user_input: str, llm_output: str) -> str:
    parts = []
    if user_input.strip():
        parts.append(user_input.strip())
    if llm_output.strip():
        parts.append(f"[AI] {llm_output.strip()}")
    return "\n".join(parts)


def _review_api_base(prompt_id: str, version: str) -> str:
    return f"/prompts/{prompt_id}/version/{version}/review/api"


@app.get("/prompts/{prompt_id}/version/{version}/review", response_class=HTMLResponse)
def review_index(request: Request, prompt_id: str, version: str):
    return _render(request, "review.html",
        prompt_id=prompt_id,
        version=version,
        review_api_base=_review_api_base(prompt_id, version),
    )


@app.post("/prompts/{prompt_id}/version/{version}/review/api/upload")
async def review_upload(request: Request, prompt_id: str, version: str):
    project = get_project()
    data = await request.json()
    rows = data.get("rows", [])
    conversation_col = data.get("conversation_col", "")
    user_input_col = data.get("user_input_col", "")
    llm_output_col = data.get("llm_output_col", "")
    id_col = data.get("id_col", "")
    response_a_col = data.get("response_a_col", "")

    if not rows:
        return JSONResponse({"ok": False, "error": "데이터가 없습니다."}, status_code=400)
    if not conversation_col and not (user_input_col and llm_output_col):
        return JSONResponse({"ok": False, "error": "conversation 또는 (user_input + llm_output) 컬럼을 선택해주세요."}, status_code=400)

    new_traces = []
    for i, row in enumerate(rows):
        trace_id = str(row.get(id_col, "")).strip() if id_col else f"row_{i}"
        scenario_id = str(row.get("scenario_id", "")).strip() or trace_id or f"row_{i}"
        turn_index = str(row.get("turn_index", "")).strip()
        user_input = str(row.get(user_input_col, "")) if user_input_col else ""
        llm_output = str(row.get(llm_output_col, "")) if llm_output_col else ""
        conversation = (
            str(row.get(conversation_col, ""))
            if conversation_col
            else _build_conversation_text(user_input, llm_output)
        )
        trace: dict = {
            "id": i,
            "trace_id": trace_id or f"row_{i}",
            "scenario_id": scenario_id or f"row_{i}",
            "turn_index": turn_index,
            "user_input": user_input,
            "llm_output": llm_output,
            "conversation": conversation,
        }
        if response_a_col:
            trace["response_a"] = str(row.get(response_a_col, ""))
        new_traces.append(trace)

    _review_save_traces(project, prompt_id, version, new_traces)
    return JSONResponse({"ok": True, "count": len(new_traces), "filename": f"{len(new_traces)}개 행"})


@app.get("/prompts/{prompt_id}/version/{version}/review/api/traces")
def review_get_traces(prompt_id: str, version: str):
    project = get_project()
    return JSONResponse(_review_load_traces(project, prompt_id, version))


@app.get("/prompts/{prompt_id}/version/{version}/review/api/labels")
def review_get_labels(prompt_id: str, version: str):
    project = get_project()
    return JSONResponse(_review_load_labels(project, prompt_id, version))


@app.post("/prompts/{prompt_id}/version/{version}/review/api/labels")
async def review_set_label(request: Request, prompt_id: str, version: str):
    project = get_project()
    data = await request.json()
    trace_id = str(data["id"])
    labels = _review_load_labels(project, prompt_id, version)
    labels[trace_id] = {
        "pass_fail": data.get("pass_fail"),
        "critique": data.get("critique", ""),
        "category": data.get("category", ""),
        "few_shot_type": data.get("few_shot_type", ""),
    }
    _review_save_labels(project, prompt_id, version, labels)
    return JSONResponse({"ok": True})


@app.post("/prompts/{prompt_id}/version/{version}/review/api/labels/reset")
def review_reset_labels(prompt_id: str, version: str):
    project = get_project()
    _review_save_labels(project, prompt_id, version, {})
    return JSONResponse({"ok": True})


@app.get("/prompts/{prompt_id}/version/{version}/review/api/categories")
def review_get_categories(prompt_id: str, version: str):
    project = get_project()
    labels = _review_load_labels(project, prompt_id, version)
    cats = sorted(set(
        v.get("category", "")
        for v in labels.values()
        if v.get("category", "")
    ))
    return JSONResponse(cats)


@app.get("/prompts/{prompt_id}/version/{version}/review/api/export")
def review_export(prompt_id: str, version: str):
    from fastapi.responses import Response as _FastAPIResponse
    project = get_project()
    labels = _review_load_labels(project, prompt_id, version)
    traces = _review_load_traces(project, prompt_id, version)
    is_pairwise = any(t.get("response_a") is not None for t in traces)
    rows = []
    for trace in traces:
        label = labels.get(str(trace["id"]), {})
        if is_pairwise:
            rows.append({
                "trace_id": trace.get("trace_id", trace["scenario_id"]),
                "scenario_id": trace["scenario_id"],
                "turn_index": trace.get("turn_index", ""),
                "user_input": trace.get("user_input", ""),
                "response_a": trace.get("response_a", ""),
                "llm_output": trace.get("llm_output", ""),
                "winner": label.get("pass_fail", ""),
                "critique": label.get("critique", ""),
                "category": label.get("category", ""),
                "few_shot_type": label.get("few_shot_type", ""),
            })
        else:
            rows.append({
                "trace_id": trace.get("trace_id", trace["scenario_id"]),
                "scenario_id": trace["scenario_id"],
                "turn_index": trace.get("turn_index", ""),
                "user_input": trace.get("user_input", ""),
                "llm_output": trace.get("llm_output", ""),
                "conversation": trace["conversation"],
                "pass_fail": label.get("pass_fail", ""),
                "critique": label.get("critique", ""),
                "category": label.get("category", ""),
                "few_shot_type": label.get("few_shot_type", ""),
            })
    buf = _io.StringIO()
    if is_pairwise:
        fieldnames = ["trace_id", "scenario_id", "turn_index", "user_input", "response_a", "llm_output", "winner", "critique", "category", "few_shot_type"]
    else:
        fieldnames = ["trace_id", "scenario_id", "turn_index", "user_input", "llm_output", "conversation", "pass_fail", "critique", "category", "few_shot_type"]
    writer = _csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    content = "\ufeff" + buf.getvalue()
    return _FastAPIResponse(
        content=content.encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=labeled_{prompt_id}_v{version}.csv"},
    )


@app.post("/prompts/{prompt_id}/version/{version}/review/api/improve")
async def review_improve(request: Request, prompt_id: str, version: str):
    import urllib.request as _urllib_req
    import urllib.error as _urllib_err
    data = await request.json()
    api_key = data.get("api_key", "").strip()
    model = data.get("model", "gpt-4o-mini")
    conversation = data.get("conversation", "")
    draft = data.get("draft", "")
    pass_fail = data.get("pass_fail", "")

    if not api_key:
        return JSONResponse({"ok": False, "error": "API 키를 입력해주세요."}, status_code=400)
    if not draft.strip():
        return JSONResponse({"ok": False, "error": "개선할 critique를 먼저 입력해주세요."}, status_code=400)

    user_message = (
        f"다음 대화에 대한 critique 초안을 개선해주세요.\n\n"
        f"[대화]\n{conversation}\n\n"
        f"[판정]\n{pass_fail.upper() if pass_fail else '미선택'}\n\n"
        f"[초안 critique]\n{draft}"
    )
    payload = _json.dumps({
        "model": model,
        "messages": [
            {"role": "system", "content": _REVIEW_IMPROVE_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.7,
        "max_completion_tokens": 800,
    }).encode("utf-8")
    req = _urllib_req.Request(
        "https://api.openai.com/v1/chat/completions",
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    try:
        with _urllib_req.urlopen(req, timeout=30) as resp:
            result = _json.loads(resp.read().decode("utf-8"))
        improved = result["choices"][0]["message"]["content"].strip()
        return JSONResponse({"ok": True, "improved": improved})
    except _urllib_err.HTTPError as e:
        body = e.read().decode("utf-8")
        try:
            err = _json.loads(body).get("error", {}).get("message", body)
        except Exception:
            err = body
        return JSONResponse({"ok": False, "error": err}, status_code=400)
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=500)


@app.exception_handler(PVMError)
def pvm_error_handler(request: Request, exc: PVMError):
    return _render(request, "error.html", error=str(exc))


# --- Entry point ---

def _pvm_api_keys_path(project) -> Path:
    return project.root / ".pvm" / "api_keys.env"


def _load_api_keys_env(keys_path: Path) -> None:
    """api_keys.env 파일의 키를 os.environ에 로드 (이미 설정된 키는 덮어쓰지 않음)."""
    if not keys_path.exists():
        return
    for line in keys_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        if k and not os.environ.get(k):
            os.environ[k] = v.strip()


def _get_api_key_status() -> dict:
    return {
        "anthropic": bool(os.environ.get("ANTHROPIC_API_KEY")),
        "openai": bool(os.environ.get("OPENAI_API_KEY")),
        "gemini": bool(os.environ.get("GEMINI_API_KEY")),
    }


# --- Settings ---

@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, saved: str = ""):
    project = get_project()
    key_status = _get_api_key_status()
    return _render(request, "settings.html", key_status=key_status, saved=bool(saved))


@app.post("/settings/api-keys")
async def save_api_keys(
    request: Request,
    anthropic_key: str = Form(""),
    openai_key: str = Form(""),
    gemini_key: str = Form(""),
):
    project = get_project()
    keys_path = _pvm_api_keys_path(project)

    # 기존 키 읽기
    existing: dict[str, str] = {}
    if keys_path.exists():
        for line in keys_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            k, _, v = line.partition("=")
            if k.strip():
                existing[k.strip()] = v.strip()

    # 새 값 반영 (빈 칸이면 변경 안 함)
    if anthropic_key.strip():
        existing["ANTHROPIC_API_KEY"] = anthropic_key.strip()
    if openai_key.strip():
        existing["OPENAI_API_KEY"] = openai_key.strip()
    if gemini_key.strip():
        existing["GEMINI_API_KEY"] = gemini_key.strip()

    keys_path.write_text(
        "\n".join(f"{k}={v}" for k, v in existing.items()) + "\n",
        encoding="utf-8",
    )

    # 현재 프로세스 env에도 즉시 반영
    for k, v in existing.items():
        os.environ[k] = v

    # .gitignore에 api_keys.env 추가 (없으면)
    gitignore = project.root / ".gitignore"
    entry = ".pvm/api_keys.env"
    if not gitignore.exists() or entry not in gitignore.read_text(encoding="utf-8"):
        with open(gitignore, "a", encoding="utf-8") as gf:
            gf.write(f"\n{entry}\n")

    return RedirectResponse("/settings?saved=1", status_code=303)


def run(
    root: str | Path = ".",
    host: str = "127.0.0.1",
    port: int = 8010,
    eval_pipeline_dir: str | Path | None = None,
):
    """Launch the pvm local UI."""
    import uvicorn

    global _project
    _project = PVMProject(root)
    # eval_pipeline_dir 인자는 하위 호환성을 위해 유지하지만 번들된 파이프라인 사용
    print(f"eval pipeline: bundled ({get_pipeline_dir()})")

    # UI에서 저장된 API 키 로드
    _load_api_keys_env(_pvm_api_keys_path(_project))

    url = f"http://{host}:{port}"
    print(f"pvm ui: {url}")
    webbrowser.open(url)
    uvicorn.run(app, host=host, port=port, log_level="warning")
