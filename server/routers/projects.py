from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from server.dependencies import get_project_service
from server.schemas.projects import CreateProjectRequest
from server.services.project_service import ProjectNotFoundError, ProjectService

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("")
def list_projects(svc: ProjectService = Depends(get_project_service)):
    return svc.list()


@router.post("", status_code=201)
def create_project(body: CreateProjectRequest, svc: ProjectService = Depends(get_project_service)):
    return svc.create(body.name)


@router.get("/{project_id}")
def get_project(project_id: str, svc: ProjectService = Depends(get_project_service)):
    try:
        return svc.get(project_id)
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, svc: ProjectService = Depends(get_project_service)):
    try:
        svc.delete(project_id)
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
