from __future__ import annotations

import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pvm.core.errors import PVMError
from pvm.project import PVMProject
from pvm.storage.history import read_history
from pvm.storage.yaml_io import dump_yaml

UI_DIR = Path(__file__).parent
app = FastAPI(title="pvm ui")
app.mount("/static", StaticFiles(directory=UI_DIR / "static"), name="static")
templates = Jinja2Templates(directory=UI_DIR / "templates")

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


@app.get("/prompts/{prompt_id}", response_class=HTMLResponse)
def prompt_detail(request: Request, prompt_id: str):
    project = get_project()
    info = project.get_prompt_info(prompt_id)
    versions = project.list_prompt_versions(prompt_id)

    current_version = None
    if info["production"]:
        current_version = info["production"]["version"]
    elif versions:
        current_version = versions[-1]

    prompt_data = None
    if current_version:
        prompt_data = project.get_prompt(prompt_id, version=current_version)

    return _render(request, "prompt_detail.html",
        info=info,
        versions=versions,
        current_version=current_version,
        prompt_data=prompt_data,
    )


@app.get("/prompts/{prompt_id}/version/{version}", response_class=HTMLResponse)
def prompt_version_detail(request: Request, prompt_id: str, version: str):
    project = get_project()
    info = project.get_prompt_info(prompt_id)
    versions = project.list_prompt_versions(prompt_id)
    prompt_data = project.get_prompt(prompt_id, version=version)

    return _render(request, "prompt_detail.html",
        info=info,
        versions=versions,
        current_version=version,
        prompt_data=prompt_data,
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



# --- History ---

@app.get("/history", response_class=HTMLResponse)
def history(request: Request, id: str | None = Query(None)):
    from pvm.storage.history import read_history

    project = get_project()
    prompt_ids = project.list_prompt_ids()

    if id:
        history_file = project.paths.prompt_history_file(id)
    else:
        history_file = project.paths.snapshot_history_file

    entries = read_history(history_file) if history_file.exists() else []

    return _render(request, "history.html",
        prompt_ids=prompt_ids,
        selected_id=id or "",
        history_entries=entries,
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

@app.exception_handler(PVMError)
def pvm_error_handler(request: Request, exc: PVMError):
    return _render(request, "error.html", error=str(exc))


# --- Entry point ---

def run(root: str | Path = ".", host: str = "127.0.0.1", port: int = 8001):
    """Launch the pvm local UI."""
    import uvicorn

    global _project
    _project = PVMProject(root)

    url = f"http://{host}:{port}"
    print(f"pvm ui: {url}")
    webbrowser.open(url)
    uvicorn.run(app, host=host, port=port, log_level="warning")
