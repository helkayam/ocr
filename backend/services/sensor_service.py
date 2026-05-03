from typing import Dict, List, Optional
from uuid import uuid4

from db import get_db, db_available

_mem: Dict[str, dict] = {}


def create_sensor(
    workspace_id: str,
    name: str,
    sensor_type: str,
    endpoint: Optional[str] = None,
) -> dict:
    sensor_id = str(uuid4())
    sensor = dict(
        sensor_id=sensor_id,
        workspace_id=workspace_id,
        name=name,
        sensor_type=sensor_type,
        endpoint=endpoint,
        status="active",
        linked_file_id=None,
    )
    if db_available():
        with get_db() as cur:
            cur.execute(
                """
                INSERT INTO sensors
                    (sensor_id, workspace_id, name, sensor_type, endpoint, status)
                VALUES (%s, %s, %s, %s, %s, 'active')
                """,
                (sensor_id, workspace_id, name, sensor_type, endpoint),
            )
    else:
        _mem[sensor_id] = sensor
    return sensor


def list_sensors(workspace_id: str) -> List[dict]:
    if db_available():
        with get_db() as cur:
            cur.execute(
                "SELECT * FROM sensors WHERE workspace_id = %s ORDER BY created_at DESC",
                (workspace_id,),
            )
            return [dict(r) for r in cur.fetchall()]
    return [s for s in _mem.values() if s["workspace_id"] == workspace_id]


def delete_sensor(sensor_id: str) -> None:
    if db_available():
        with get_db() as cur:
            cur.execute("DELETE FROM sensors WHERE sensor_id = %s", (sensor_id,))
    else:
        _mem.pop(sensor_id, None)


def link_sensor(sensor_id: str, file_id: str) -> Optional[dict]:
    if db_available():
        with get_db() as cur:
            cur.execute(
                "UPDATE sensors SET linked_file_id = %s WHERE sensor_id = %s",
                (file_id, sensor_id),
            )
            cur.execute("SELECT * FROM sensors WHERE sensor_id = %s", (sensor_id,))
            row = cur.fetchone()
            return dict(row) if row else None
    s = _mem.get(sensor_id)
    if s:
        s["linked_file_id"] = file_id
    return s
