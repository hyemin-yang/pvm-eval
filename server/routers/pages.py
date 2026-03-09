from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from pvm.core.errors import PromptNotFoundError, VersionNotFoundError
from server.db.session import get_db
from server.services.project_service import ProjectNotFoundError, ProjectService
from server.services.prompt_service import PromptService
from server.services.snapshot_service import SnapshotService

router = APIRouter(tags=["ui"])

_TEMPLATES_DIR = Path(__file__).parent.parent / "ui" / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


def _ps(db: Session = Depends(get_db)) -> ProjectService:
    return ProjectService(db)


def _prs(db: Session = Depends(get_db)) -> PromptService:
    return PromptService(ProjectService(db))


def _ss(db: Session = Depends(get_db)) -> SnapshotService:
    return SnapshotService(ProjectService(db))


# ── Dashboard ────────────────────────────────────────────────────────────────


@router.get("/", response_class=HTMLResponse)
def index(request: Request, svc: ProjectService = Depends(_ps)):
    return templates.TemplateResponse(
        "index.html", {"request": request, "projects": svc.list()}
    )


# ── Project form actions ──────────────────────────────────────────────────────


@router.post("/projects")
async def create_project_form(request: Request, db: Session = Depends(get_db)):
    form = await request.form()
    name = str(form.get("name", "my-project")).strip() or "my-project"
    result = ProjectService(db).create(name)
    return RedirectResponse(f"/projects/{result['server_project_id']}", status_code=303)


@router.post("/projects/{project_id}/delete")
def delete_project_form(project_id: str, db: Session = Depends(get_db)):
    try:
        ProjectService(db).delete(project_id)
    except ProjectNotFoundError:
        pass
    return RedirectResponse("/", status_code=303)


# ── Project pages ─────────────────────────────────────────────────────────────


@router.get("/projects/{project_id}", response_class=HTMLResponse)
def project_detail(request: Request, project_id: str, svc: ProjectService = Depends(_ps)):
    try:
        project = svc.get(project_id)
    except ProjectNotFoundError:
        return templates.TemplateResponse("404.html", {"request": request}, status_code=404)
    return templates.TemplateResponse(
        "project.html", {"request": request, "project": project}
    )


# ── Prompt form actions ───────────────────────────────────────────────────────


@router.post("/projects/{project_id}/prompts")
async def add_prompt_form(
    request: Request,
    project_id: str,
    svc: PromptService = Depends(_prs),
):
    form = await request.form()
    yaml_content = str(form.get("yaml_content", ""))
    bump_level = str(form.get("bump_level", "patch"))
    try:
        result = svc.add(project_id, yaml_content, bump_level)
        prompt_id = result.get("id", "")
    except Exception:
        prompt_id = ""
    return RedirectResponse(
        f"/projects/{project_id}/prompts/{prompt_id}" if prompt_id else f"/projects/{project_id}",
        status_code=303,
    )


@router.post("/projects/{project_id}/prompts/{prompt_id}/deploy")
async def deploy_form(
    request: Request,
    project_id: str,
    prompt_id: str,
    svc: PromptService = Depends(_prs),
):
    form = await request.form()
    version = str(form.get("version", "")).strip() or None
    try:
        svc.deploy(project_id, prompt_id, version)
    except Exception:
        pass
    return RedirectResponse(
        f"/projects/{project_id}/prompts/{prompt_id}", status_code=303
    )


@router.post("/projects/{project_id}/prompts/{prompt_id}/rollback")
def rollback_form(
    project_id: str,
    prompt_id: str,
    svc: PromptService = Depends(_prs),
):
    try:
        svc.rollback(project_id, prompt_id)
    except Exception:
        pass
    return RedirectResponse(
        f"/projects/{project_id}/prompts/{prompt_id}", status_code=303
    )


# ── Prompt pages ──────────────────────────────────────────────────────────────


@router.get("/projects/{project_id}/prompts/{prompt_id}", response_class=HTMLResponse)
def prompt_detail(
    request: Request,
    project_id: str,
    prompt_id: str,
    version: str | None = None,
    svc: PromptService = Depends(_prs),
    ps: ProjectService = Depends(_ps),
):
    try:
        project = ps.get(project_id)
        info = svc.get_info(project_id, prompt_id)
        versions = svc.list_versions(project_id, prompt_id)
        production_version = (info.get("production") or {}).get("version")
        current_version = version or production_version or (versions[-1] if versions else None)
        current_prompt = svc.get(project_id, prompt_id, current_version) if current_version else None
        log = svc.get_log(project_id, prompt_id)
    except (ProjectNotFoundError, PromptNotFoundError):
        return templates.TemplateResponse("404.html", {"request": request}, status_code=404)

    return templates.TemplateResponse(
        "prompt.html",
        {
            "request": request,
            "project": project,
            "info": info,
            "versions": versions,
            "production_version": production_version,
            "current_version": current_version,
            "current_prompt": current_prompt,
            "log": log,
        },
    )


@router.get("/projects/{project_id}/prompts/{prompt_id}/diff", response_class=HTMLResponse)
def prompt_diff(
    request: Request,
    project_id: str,
    prompt_id: str,
    from_version: str = "",
    to_version: str = "",
    svc: PromptService = Depends(_prs),
    ps: ProjectService = Depends(_ps),
):
    try:
        project = ps.get(project_id)
        versions = svc.list_versions(project_id, prompt_id)
    except (ProjectNotFoundError, PromptNotFoundError):
        return templates.TemplateResponse("404.html", {"request": request}, status_code=404)

    diff_result = None
    from_prompt = None
    to_prompt = None
    error = None
    if from_version and to_version:
        try:
            diff_result = svc.diff(project_id, prompt_id, from_version, to_version)
            from_prompt = svc.get(project_id, prompt_id, from_version)
            to_prompt   = svc.get(project_id, prompt_id, to_version)
        except (VersionNotFoundError, Exception) as e:
            error = str(e)

    return templates.TemplateResponse(
        "diff.html",
        {
            "request": request,
            "project": project,
            "prompt_id": prompt_id,
            "versions": versions,
            "from_version": from_version,
            "to_version": to_version,
            "diff": diff_result,
            "from_prompt": from_prompt,
            "to_prompt": to_prompt,
            "error": error,
        },
    )


# ── Snapshot form actions ────────────────────────────────────────────────────


@router.post("/projects/{project_id}/snapshots")
async def create_snapshot_form(
    request: Request,
    project_id: str,
    svc: SnapshotService = Depends(_ss),
):
    form = await request.form()
    bump_level = str(form.get("bump_level", "patch"))
    try:
        svc.create(project_id, bump_level)
    except Exception:
        pass
    return RedirectResponse(f"/projects/{project_id}", status_code=303)


# ── Snapshot pages ────────────────────────────────────────────────────────────


@router.get("/projects/{project_id}/snapshots/{version}", response_class=HTMLResponse)
def snapshot_detail(
    request: Request,
    project_id: str,
    version: str,
    svc: SnapshotService = Depends(_ss),
    ps: ProjectService = Depends(_ps),
):
    try:
        project = ps.get(project_id)
        manifest = svc.get(project_id, version)
        expanded = svc.read(project_id, version)
        all_versions = svc.list(project_id)
        version_index = all_versions.index(version) if version in all_versions else -1
        prev_version = all_versions[version_index - 1] if version_index > 0 else None
        diff_result = svc.diff(project_id, prev_version, version) if prev_version else None
    except (ProjectNotFoundError, VersionNotFoundError):
        return templates.TemplateResponse("404.html", {"request": request}, status_code=404)

    return templates.TemplateResponse(
        "snapshot.html",
        {
            "request": request,
            "project": project,
            "version": version,
            "manifest": manifest,
            "expanded": expanded,
            "prev_version": prev_version,
            "diff": diff_result,
        },
    )
