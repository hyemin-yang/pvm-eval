from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from pvm.core.errors import VersionNotFoundError
from server.dependencies import get_snapshot_service
from server.schemas.snapshots import CreateSnapshotRequest
from server.services.project_service import ProjectNotFoundError
from server.services.snapshot_service import SnapshotService

router = APIRouter(prefix="/api/projects/{project_id}/snapshots", tags=["snapshots"])

_NOT_FOUND = (ProjectNotFoundError, VersionNotFoundError)


@router.get("")
def list_snapshots(project_id: str, svc: SnapshotService = Depends(get_snapshot_service)):
    try:
        return svc.list(project_id)
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("", status_code=201)
def create_snapshot(
    project_id: str,
    body: CreateSnapshotRequest,
    svc: SnapshotService = Depends(get_snapshot_service),
):
    try:
        return svc.create(project_id, body.bump_level)
    except ProjectNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/diff")
def diff_snapshots(
    project_id: str,
    from_version: str = Query(...),
    to_version: str = Query(...),
    svc: SnapshotService = Depends(get_snapshot_service),
):
    try:
        return svc.diff(project_id, from_version, to_version)
    except _NOT_FOUND as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{version}/read")
def read_snapshot(project_id: str, version: str, svc: SnapshotService = Depends(get_snapshot_service)):
    try:
        return svc.read(project_id, version)
    except _NOT_FOUND as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{version}")
def get_snapshot(project_id: str, version: str, svc: SnapshotService = Depends(get_snapshot_service)):
    try:
        return svc.get(project_id, version)
    except _NOT_FOUND as e:
        raise HTTPException(status_code=404, detail=str(e))
