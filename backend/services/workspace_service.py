from datetime import datetime
from typing import List, Optional, Dict
from uuid import uuid4

from loguru import logger

from api.schemas import Workspace, WorkspaceCreateRequest
from db import get_db, db_available

# In-memory fallback when no DB
_workspaces_mem: Dict[str, dict] = {}

# ─── Live-count SQL helpers ────────────────────────────────────────────────────
# Always compute file_count and total_size from the files table so that
# deletes are immediately reflected without a separate counter update.

_SELECT_ONE = """
    SELECT w.workspace_id, w.name, w.description,
           COALESCE(COUNT(f.file_id),       0) AS file_count,
           COALESCE(SUM(f.file_size),       0) AS total_size,
           w.created_at, w.updated_at
    FROM   workspaces w
    LEFT JOIN files f ON f.workspace_id = w.workspace_id
    WHERE  w.workspace_id = %s
    GROUP BY w.workspace_id, w.name, w.description, w.created_at, w.updated_at
"""

_SELECT_ALL = """
    SELECT w.workspace_id, w.name, w.description,
           COALESCE(COUNT(f.file_id),       0) AS file_count,
           COALESCE(SUM(f.file_size),       0) AS total_size,
           w.created_at, w.updated_at
    FROM   workspaces w
    LEFT JOIN files f ON f.workspace_id = w.workspace_id
    GROUP BY w.workspace_id, w.name, w.description, w.created_at, w.updated_at
    ORDER BY w.created_at DESC
"""


def create_workspace(request: WorkspaceCreateRequest) -> Workspace:
    # Short 8-char hex ID — unique enough for workspace URLs, much nicer than a
    # full UUID in the browser address bar.
    workspace_id = uuid4().hex[:8]
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
            cur.execute(_SELECT_ALL)
            rows = cur.fetchall()
        return [_dict_to_workspace(dict(r)) for r in rows]
    return [_dict_to_workspace(w) for w in _workspaces_mem.values()]


def get_workspace(workspace_id: str) -> Optional[Workspace]:
    if db_available():
        with get_db() as cur:
            cur.execute(_SELECT_ONE, (workspace_id,))
            row = cur.fetchone()
        return _dict_to_workspace(dict(row)) if row else None
    d = _workspaces_mem.get(workspace_id)
    return _dict_to_workspace(d) if d else None


def delete_workspace(workspace_id: str) -> bool:
    """Deep delete: per-file teardown (vectors + disk + geo + SQL) then workspace row."""
    if not db_available():
        if workspace_id in _workspaces_mem:
            del _workspaces_mem[workspace_id]
            return True
        return False

    with get_db() as cur:
        cur.execute("SELECT 1 FROM workspaces WHERE workspace_id = %s", (workspace_id,))
        if not cur.fetchone():
            return False
        # Snapshot files before any deletes so deep_delete_file can act on each one
        cur.execute(
            "SELECT file_id, file_type, object_name FROM files WHERE workspace_id = %s",
            (workspace_id,),
        )
        file_records = [dict(r) for r in cur.fetchall()]

    # Deep-delete every file: ChromaDB vectors, disk artifacts, geo entities,
    # SQL rows (files + document_chunks), and object storage.
    from services import file_service
    for file_rec in file_records:
        try:
            file_service.deep_delete_file(file_rec)
        except Exception as exc:
            logger.error(
                "[workspace_delete] file teardown failed for {}: {}",
                file_rec.get("file_id"), exc,
            )

    # Sweep remaining workspace-scoped rows not handled by per-file cleanup
    # (sensors, emergency events, and any orphaned map tags).
    with get_db() as cur:
        cur.execute("DELETE FROM emergency_events WHERE workspace_id = %s", (workspace_id,))
        cur.execute("DELETE FROM sensors         WHERE workspace_id = %s", (workspace_id,))
        cur.execute("DELETE FROM map_tags        WHERE workspace_id = %s", (workspace_id,))
        cur.execute("DELETE FROM workspaces      WHERE workspace_id = %s", (workspace_id,))

    return True


def increment_file_stats(workspace_id: str, file_size: int) -> None:
    # Still update the cached columns so they stay roughly accurate for
    # read paths that bypass the live-count query (e.g. in-memory fallback).
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
