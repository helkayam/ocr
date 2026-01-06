from fastapi import APIRouter
from datetime import datetime
from typing import List
from .schemas import Workspace, WorkspaceCreateRequest

 

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


@router.post("", response_model=Workspace)
def create_workspace(request: WorkspaceCreateRequest):
    """Create workspace"""
    # Stub implementation - no persistence yet
    now = datetime.now()
    return Workspace(
        id="stub-id-1",
        name=request.name,
        description=request.description,
        createdAt=now,
        updatedAt=now,
        fileCount=0,
        totalSize=0
    )


@router.get("", response_model=List[Workspace])
def list_workspaces():
    """List workspaces"""
    # Stub implementation - no persistence yet
    return []


@router.get("/{id}", response_model=Workspace)
def get_workspace(id: str):
    """Get workspace details"""
    # Stub implementation - no persistence yet
    now = datetime.now()
    return Workspace(
        id=id,
        name="Stub Workspace",
        description="This is a stub workspace",
        createdAt=now,
        updatedAt=now,
        fileCount=0,
        totalSize=0
    )

