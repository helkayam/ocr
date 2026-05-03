from datetime import datetime
from typing import List, Optional, Dict
from uuid import uuid4

from api.schemas import Workspace, WorkspaceCreateRequest
from db import get_db, db_available

# In-memory fallback when no DB
_workspaces_mem: Dict[str, dict] = {}


def create_workspace(request: WorkspaceCreateRequest) -> Workspace:
    workspace_id = str(uuid4())
    now = datetime.utcnow()

    data = dict(
        workspace_id=workspace_id,
        name=request.name,
        description=request.description,
        file_count=0,
        total_size=0,
        created_at=now,
        updated_at=now,
    )

    if db_available():
        with get_db() as cur:
            cur.execute(
                """
                INSERT INTO workspaces
                    (workspace_id, name, description, file_count, total_size, created_at, updated_at)
                VALUES (%s, %s, %s, 0, 0, %s, %s)
                """,
                (workspace_id, request.name, request.description, now, now),
            )
    else:
        _workspaces_mem[workspace_id] = data

    return _dict_to_workspace(data)


def list_workspaces() -> List[Workspace]:
    if db_available():
        with get_db() as cur:
            cur.execute("SELECT * FROM workspaces ORDER BY created_at DESC")
            rows = cur.fetchall()
        return [_dict_to_workspace(dict(r)) for r in rows]
    return [_dict_to_workspace(w) for w in _workspaces_mem.values()]


def get_workspace(workspace_id: str) -> Optional[Workspace]:
    if db_available():
        with get_db() as cur:
            cur.execute("SELECT * FROM workspaces WHERE workspace_id = %s", (workspace_id,))
            row = cur.fetchone()
        return _dict_to_workspace(dict(row)) if row else None
    d = _workspaces_mem.get(workspace_id)
    return _dict_to_workspace(d) if d else None


def increment_file_stats(workspace_id: str, file_size: int) -> None:
    if db_available():
        with get_db() as cur:
            cur.execute(
                """
                UPDATE workspaces
                SET file_count = file_count + 1,
                    total_size = total_size + %s,
                    updated_at  = CURRENT_TIMESTAMP
                WHERE workspace_id = %s
                """,
                (file_size, workspace_id),
            )
    else:
        w = _workspaces_mem.get(workspace_id)
        if w:
            w["file_count"] += 1
            w["total_size"] += file_size
            w["updated_at"] = datetime.utcnow()


def _dict_to_workspace(d: dict) -> Workspace:
    return Workspace(
        id=d["workspace_id"],
        name=d["name"],
        description=d.get("description"),
        createdAt=d["created_at"],
        updatedAt=d["updated_at"],
        fileCount=d["file_count"],
        totalSize=d["total_size"],
    )
