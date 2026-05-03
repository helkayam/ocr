from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from services import sensor_service

router = APIRouter(prefix="/sensors", tags=["sensors"])


class SensorCreate(BaseModel):
    workspace_id: str
    name: str
    sensor_type: str
    endpoint: Optional[str] = None


class SensorLink(BaseModel):
    file_id: str


class SensorOut(BaseModel):
    sensor_id: str
    workspace_id: str
    name: str
    sensor_type: str
    endpoint: Optional[str]
    status: str
    linked_file_id: Optional[str]


@router.post("", response_model=SensorOut)
def create_sensor(body: SensorCreate):
    s = sensor_service.create_sensor(
        body.workspace_id, body.name, body.sensor_type, body.endpoint
    )
    return SensorOut(**s)


@router.get("", response_model=List[SensorOut])
def list_sensors(workspace_id: str):
    return [SensorOut(**s) for s in sensor_service.list_sensors(workspace_id)]


@router.delete("/{sensor_id}", status_code=204)
def delete_sensor(sensor_id: str):
    sensor_service.delete_sensor(sensor_id)


@router.post("/{sensor_id}/link", response_model=SensorOut)
def link_sensor(sensor_id: str, body: SensorLink):
    s = sensor_service.link_sensor(sensor_id, body.file_id)
    if not s:
        raise HTTPException(status_code=404, detail="Sensor not found")
    return SensorOut(**s)
