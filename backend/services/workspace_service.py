from datetime import datetime
from typing import List, Dict
from uuid import uuid4

from api.schemas import Workspace, WorkspaceCreateRequest


# In-memory storage
_workspaces: Dict[str, Workspace] = {}


def create_workspace(request: WorkspaceCreateRequest) -> Workspace:
    now = datetime.now()
    workspace_id = str(uuid4())

    workspace = Workspace(
        id=workspace_id,
        name=request.name,
        description=request.description,
        createdAt=now,
        updatedAt=now,
        fileCount=0,
        totalSize=0
    )

    _workspaces[workspace_id] = workspace
    return workspace


def list_workspaces() -> List[Workspace]:
    return list(_workspaces.values())


def get_workspace(workspace_id: str) -> Workspace | None:
    return _workspaces.get(workspace_id)


def increment_file_stats(workspace_id: str, file_size: int) -> None:
    """
    Update workspace counters when a file is added
    """
    workspace = _workspaces.get(workspace_id)
    if not workspace:
        return

    workspace.fileCount += 1
    workspace.totalSize += file_size
    workspace.updatedAt = datetime.now()
