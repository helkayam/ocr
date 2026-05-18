"""
Emergency Simulation API endpoints:
  - Geo features CRUD (typed emergency POIs)
  - Sensor location update
  - Simulation trigger (streaming SSE)
  - Event history
"""
from __future__ import annotations

import json
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from api.schemas import (
    GeoFeatureCreate,
    GeoFeatureOut,
    SensorLocationUpdate,
    EmergencySimRequest,
    EmergencyEventOut,
)
from services import emergency_service, geo_service, sensor_service

router = APIRouter(prefix="/emergency", tags=["emergency"])


# ── Geo Features ──────────────────────────────────────────────────────────────

@router.post("/features", response_model=GeoFeatureOut, status_code=status.HTTP_201_CREATED)
def create_geo_feature(body: GeoFeatureCreate):
    feat = geo_service.add_geo_feature(
        workspace_id=body.workspace_id,
        feature_type=body.feature_type,
        label=body.label,
        lat=body.lat,
        lng=body.lng,
        floor=body.floor,
        metadata=body.metadata,
    )
    return GeoFeatureOut(**feat)


@router.get("/features/{workspace_id}", response_model=List[GeoFeatureOut])
def list_geo_features(workspace_id: str, feature_type: Optional[str] = None):
    return [
        GeoFeatureOut(**f)
        for f in geo_service.list_geo_features(workspace_id, feature_type)
    ]


@router.delete("/features/{feature_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_geo_feature(feature_id: str):
    geo_service.delete_geo_feature(feature_id)


# ── Sensor location ───────────────────────────────────────────────────────────

@router.patch("/sensors/{sensor_id}/location")
def update_sensor_location(sensor_id: str, body: SensorLocationUpdate):
    s = sensor_service.update_sensor_location(sensor_id, body.lat, body.lng)
    if not s:
        raise HTTPException(status_code=404, detail="Sensor not found")
    return s


# ── Simulation (SSE streaming) ────────────────────────────────────────────────

@router.post("/simulate")
def simulate_emergency(req: EmergencySimRequest) -> StreamingResponse:
    """
    Stream the emergency simulation as Server-Sent Events.

    Event types emitted (all data values are JSON-encoded strings):
      status  — one of: connecting | retrieving | streaming | analyzing | routing
      token   — a single incremental text chunk from the LLM RAG generation
      result  — final JSON payload with the complete EmergencySimResult structure
      error   — unrecoverable error message; stream ends immediately after
    """
    def gen():
        try:
            yield from emergency_service.simulate_stream(
                workspace_id=req.workspace_id,
                sensor_id=req.sensor_id,
                alert_level=req.alert_level,
                override_query=req.override_query,
                origin_lat=req.origin_lat,
                origin_lng=req.origin_lng,
            )
        except Exception as exc:
            yield f"event: error\ndata: {json.dumps({'detail': str(exc)})}\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


# ── Event history ─────────────────────────────────────────────────────────────

@router.get("/events/{workspace_id}", response_model=List[EmergencyEventOut])
def list_emergency_events(workspace_id: str):
    events = emergency_service.list_events(workspace_id)
    return [
        EmergencyEventOut(
            event_id=e["event_id"],
            workspace_id=e["workspace_id"],
            sensor_name=e.get("sensor_name"),
            sensor_type=e.get("sensor_type"),
            alert_level=e.get("alert_level", "high"),
            intent_action=e.get("intent_action"),
            intent_target=e.get("intent_target"),
            intent_urgency=e.get("intent_urgency"),
            nearest_feature_label=e.get("nearest_feature_label"),
            nearest_distance_m=e.get("nearest_distance_m"),
            directive=e.get("directive"),
            status=e.get("status", "simulated"),
            created_at=e.get("created_at"),
        )
        for e in events
    ]
