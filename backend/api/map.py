from fastapi import APIRouter
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

from services.geo_service import get_layers, get_tags, add_tag, delete_tag

router = APIRouter(prefix="/map", tags=["map"])


class MapTagCreate(BaseModel):
    workspace_id: str
    label: str
    lat: float
    lng: float
    tag_type: str = "point"
    color: str = "#ef4444"
    file_id: Optional[str] = None


class MapTagOut(BaseModel):
    tag_id: str
    workspace_id: str
    label: str
    lat: float
    lng: float
    tag_type: str
    color: str
    file_id: Optional[str] = None


@router.get("/layers/{workspace_id}")
def get_map_layers(workspace_id: str) -> List[Dict[str, Any]]:
    return get_layers(workspace_id)


@router.get("/tags/{workspace_id}", response_model=List[MapTagOut])
def get_map_tags(workspace_id: str):
    return [MapTagOut(**t) for t in get_tags(workspace_id)]


@router.post("/tags", response_model=MapTagOut)
def create_tag(body: MapTagCreate):
    tag = add_tag(
        workspace_id=body.workspace_id,
        label=body.label,
        lat=body.lat,
        lng=body.lng,
        tag_type=body.tag_type,
        color=body.color,
        file_id=body.file_id,
    )
    return MapTagOut(**tag)


@router.delete("/tags/{tag_id}", status_code=204)
def remove_tag(tag_id: str):
    delete_tag(tag_id)
