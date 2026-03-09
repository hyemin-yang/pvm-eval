from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from pvm.core.errors import InvalidPromptTemplateError, PromptNotFoundError, VersionNotFoundError
from server.dependencies import get_prompt_service
from server.schemas.prompts import AddPromptRequest, DeployRequest
from server.services.project_service import ProjectNotFoundError
from server.services.prompt_service import PromptService

router = APIRouter(prefix="/api/projects/{project_id}/prompts", tags=["prompts"])

_NOT_FOUND = (ProjectNotFoundError, PromptNotFoundError, VersionNotFoundError)


@router.get("")
def list_prompts(project_id: str, svc: PromptService = Depends(get_prompt_service)):
    try:
        return svc.list_ids(project_id)
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("", status_code=201)
def add_prompt(
    project_id: str,
    body: AddPromptRequest,
    svc: PromptService = Depends(get_prompt_service),
):
    try:
        result = svc.add(project_id, body.yaml_content, body.bump_level)
        if not result.get("changed"):
            return {"changed": False, "message": "No changes"}
        return result
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except InvalidPromptTemplateError as e:
        raise HTTPException(status_code=422, detail=str(e))


@router.get("/{prompt_id}/info")
def get_prompt_info(project_id: str, prompt_id: str, svc: PromptService = Depends(get_prompt_service)):
    try:
        return svc.get_info(project_id, prompt_id)
    except _NOT_FOUND as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{prompt_id}/versions")
def list_versions(project_id: str, prompt_id: str, svc: PromptService = Depends(get_prompt_service)):
    try:
        return svc.list_versions(project_id, prompt_id)
    except _NOT_FOUND as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{prompt_id}/versions/{version}")
def get_version(
    project_id: str,
    prompt_id: str,
    version: str,
    svc: PromptService = Depends(get_prompt_service),
):
    try:
        return svc.get(project_id, prompt_id, version)
    except _NOT_FOUND as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{prompt_id}/deploy")
def deploy(
    project_id: str,
    prompt_id: str,
    body: DeployRequest,
    svc: PromptService = Depends(get_prompt_service),
):
    try:
        result = svc.deploy(project_id, prompt_id, body.version)
        if not result.get("changed"):
            return {"changed": False, "message": result.get("reason", "already_deployed")}
        return result
    except _NOT_FOUND as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{prompt_id}/rollback")
def rollback(project_id: str, prompt_id: str, svc: PromptService = Depends(get_prompt_service)):
    try:
        result = svc.rollback(project_id, prompt_id)
        if not result.get("changed"):
            return {"changed": False, "message": "No rollback target"}
        return result
    except _NOT_FOUND as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{prompt_id}/diff")
def diff(
    project_id: str,
    prompt_id: str,
    from_version: str = Query(...),
    to_version: str = Query(...),
    svc: PromptService = Depends(get_prompt_service),
):
    try:
        return svc.diff(project_id, prompt_id, from_version, to_version)
    except _NOT_FOUND as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{prompt_id}/log")
def get_log(project_id: str, prompt_id: str, svc: PromptService = Depends(get_prompt_service)):
    try:
        return svc.get_log(project_id, prompt_id)
    except _NOT_FOUND as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{prompt_id}")
def get_prompt(
    project_id: str,
    prompt_id: str,
    version: str | None = Query(None),
    svc: PromptService = Depends(get_prompt_service),
):
    try:
        return svc.get(project_id, prompt_id, version)
    except _NOT_FOUND as e:
        raise HTTPException(status_code=404, detail=str(e))
