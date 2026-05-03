from fastapi import APIRouter, HTTPException
from typing import List
from .schemas import Workspace, WorkspaceCreateRequest
from services import workspace_service


router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.post("", response_model=Workspace)
def create_workspace(request: WorkspaceCreateRequest):
    return workspace_service.create_workspace(request)


@router.get("", response_model=List[Workspace])
def list_workspaces():
    return workspace_service.list_workspaces()


@router.get("/{id}", response_model=Workspace)
def get_workspace(id: str):
    workspace = workspace_service.get_workspace(id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace
