from __future__ import annotations

import webbrowser
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from pvm.core.errors import PVMError
from pvm.project import PVMProject

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
    snapshots = project.list_snapshots()

    prompts_summary = []
    for pid in prompt_ids:
        info = project.get_prompt_info(pid)
        prompts_summary.append(info)

    return _render(request, "dashboard.html",
        config=config,
        integrity=integrity,
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


@app.post("/prompts/{prompt_id}/deploy")
def prompt_deploy(prompt_id: str, version: str = Form(...)):
    project = get_project()
    project.deploy(prompt_id, version)
    return RedirectResponse(f"/prompts/{prompt_id}", status_code=303)


@app.post("/prompts/{prompt_id}/rollback")
def prompt_rollback(prompt_id: str):
    project = get_project()
    project.rollback(prompt_id)
    return RedirectResponse(f"/prompts/{prompt_id}", status_code=303)


@app.post("/prompts/{prompt_id}/delete")
def prompt_delete(prompt_id: str):
    project = get_project()
    project.delete_prompt(prompt_id)
    return RedirectResponse("/prompts", status_code=303)


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


# --- Snapshots ---

@app.get("/snapshots", response_class=HTMLResponse)
def snapshot_list(request: Request):
    project = get_project()
    snapshots = project.list_snapshots()
    snapshots_summary = []
    for ver in snapshots:
        manifest = project.get_snapshot(ver)
        snapshots_summary.append(manifest)
    return _render(request, "snapshots.html",
        snapshots_summary=snapshots_summary,
    )


@app.post("/snapshots/create")
def snapshot_create(bump_level: str = Form("patch")):
    project = get_project()
    project.create_snapshot(bump_level=bump_level)
    return RedirectResponse("/snapshots", status_code=303)


@app.get("/snapshots/{version}", response_class=HTMLResponse)
def snapshot_detail(request: Request, version: str):
    project = get_project()
    manifest = project.get_snapshot(version)
    snapshot_data = project.read_snapshot(version)
    return _render(request, "snapshot_detail.html",
        manifest=manifest,
        snapshot_data=snapshot_data,
    )


@app.get("/snapshots/{version}/export")
def snapshot_export(version: str):
    project = get_project()
    result = project.export_snapshot(version)
    return FileResponse(
        result["output_path"],
        filename=f"snapshot-{version}.zip",
        media_type="application/zip",
    )


@app.get("/snapshots/diff/compare", response_class=HTMLResponse)
def snapshot_diff(
    request: Request,
    from_version: str = Query(..., alias="from"),
    to_version: str = Query(..., alias="to"),
):
    project = get_project()
    diff_result = project.diff_snapshot(from_version, to_version)
    snapshots = project.list_snapshots()
    return _render(request, "snapshot_diff.html",
        diff_result=diff_result,
        snapshots=snapshots,
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
def project_init(name: str = Form("my-project")):
    project = get_project()
    project.init(name)
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
