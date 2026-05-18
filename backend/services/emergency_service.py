"""
EmergencySimulationService — orchestrates the full sensor-alert pipeline:
  sensor coords → RAG query → LLM intent extraction → Haversine geo routing → directive
"""
from __future__ import annotations

import json as _json
import sys
import os
from datetime import date as _date, datetime
from typing import Generator, Optional
from uuid import uuid4

from loguru import logger

# Ensure app/ is on the Python path when running from backend/
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

from db import get_db, db_available
from services import sensor_service, geo_service

# app/ imports (RAG pipeline)
from app import pipeline
from app.emergency.intent_extractor import extract_intent, IntentResult

_SENSOR_TYPE_LABELS: dict[str, str] = {
    "SIREN":     "אזעקה",
    "TERRORIST": "חדירת מחבלים",
    "HAZMAT":    "אירוע חומרים מסוכנים",
}

_RAG_MISSING_MARKER = "המידע המבוקש לא נמצא"
_DIRECTIVE_NO_PROTOCOL = "אין פרוטוקול חירום מוגדר במערכת עבור תרחיש זה."


def _json_default(obj: object) -> str:
    """Allow json.dumps to handle datetime/date objects from SQLite rows."""
    if isinstance(obj, (datetime, _date)):
        return obj.isoformat()
    raise TypeError(f"Not JSON serialisable: {type(obj)}")


def simulate(
    workspace_id: str,
    sensor_id: str,
    alert_level: str = "high",
    override_query: Optional[str] = None,
    origin_lat: Optional[float] = None,
    origin_lng: Optional[float] = None,
) -> dict:
    """
    Full emergency simulation pipeline.
    Returns a dict containing: event_id, sensor, alert_level, rag_query,
    rag_answer, rag_sources, intent, nearest_feature, directive.
    """
    logger.info(
        "EmergencySim: START workspace={} sensor={} level={}",
        workspace_id, sensor_id, alert_level,
    )

    # ── 1. Fetch sensor ───────────────────────────────────────────────────────
    sensor = sensor_service.get_sensor(sensor_id)
    if not sensor:
        raise ValueError(f"Sensor not found: {sensor_id}")

    sensor_lat: Optional[float] = sensor.get("lat")
    sensor_lng: Optional[float] = sensor.get("lng")

    # ── 2. Build Hebrew RAG query ─────────────────────────────────────────────
    type_label = _SENSOR_TYPE_LABELS.get(sensor.get("sensor_type", ""), "אירוע חירום")
    rag_query = override_query or (
        f"חיישן {type_label} בשם '{sensor['name']}' הפעיל התרעה. "
        "מה פרוטוקול הפעולה הנדרש? אילו צעדים יש לנקוט?"
    )
    logger.debug("EmergencySim: query={!r}", rag_query)

    # ── 3. RAG pipeline ───────────────────────────────────────────────────────
    rag_answer = "המידע המבוקש לא נמצא במסמכים שסופקו."
    rag_sources: list = []
    try:
        rag_resp = pipeline.ask_pipeline(rag_query, top_k=5, workspace_id=workspace_id)
        rag_answer = rag_resp.answer
        rag_sources = [
            {
                "document_id": s.document_id,
                "file_name": getattr(s, "file_name", ""),
                "page_num": s.page_num,
                "chunk_id": s.chunk_id,
                "text_snippet": s.text_snippet,
            }
            for s in rag_resp.sources
        ]
    except Exception as exc:
        logger.error("EmergencySim: RAG pipeline failed — {}", exc)

    # ── 4. Guard: no protocol in RAG → skip intent + geo ─────────────────────
    if _RAG_MISSING_MARKER in rag_answer:
        logger.info("EmergencySim: RAG returned no-protocol — skipping intent + geo")
        intent = IntentResult(action="no_protocol", target_type="none", urgency="low")
        nearest: Optional[dict] = None
        directive = _DIRECTIVE_NO_PROTOCOL
        event_id = str(uuid4())
        _log_event(
            event_id=event_id,
            workspace_id=workspace_id,
            sensor=sensor,
            alert_level=alert_level,
            rag_query=rag_query,
            rag_answer=rag_answer,
            intent=intent,
            nearest=nearest,
            directive=directive,
        )
        logger.info("EmergencySim: COMPLETE (no-protocol) event_id={}", event_id)
        return {
            "event_id": event_id,
            "sensor": sensor,
            "alert_level": alert_level,
            "rag_query": rag_query,
            "rag_answer": rag_answer,
            "rag_sources": rag_sources,
            "intent": intent.model_dump(),
            "nearest_feature": nearest,
            "directive": directive,
        }

    # ── 5. LLM intent extraction ──────────────────────────────────────────────
    try:
        intent: IntentResult = extract_intent(rag_answer)
    except Exception as exc:
        logger.error("EmergencySim: intent extraction failed — {}", exc)
        intent = IntentResult(action="proceed_to_shelter", target_type="shelter", urgency="critical")

    logger.info(
        "EmergencySim: intent action={} target={} urgency={}",
        intent.action, intent.target_type, intent.urgency,
    )

    # ── 6. Haversine geo routing ──────────────────────────────────────────────
    # Prefer the user-supplied origin; fall back to sensor coords.
    route_lat = origin_lat if origin_lat is not None else sensor_lat
    route_lng = origin_lng if origin_lng is not None else sensor_lng

    nearest: Optional[dict] = None
    if route_lat is not None and route_lng is not None and intent.target_type != "none":
        nearest = geo_service.find_nearest_feature(
            workspace_id=workspace_id,
            feature_type=intent.target_type,
            lat=route_lat,
            lng=route_lng,
        )
        if nearest:
            dist_m = nearest["distance_m"]
            nearest["distance_display"] = (
                f"{dist_m / 1000:.1f} km" if dist_m > 1000 else f"{int(dist_m)} m"
            )

    # ── 7. Build directive ────────────────────────────────────────────────────
    directive = _build_directive(intent, nearest, sensor)

    # ── 8. Persist event ──────────────────────────────────────────────────────
    event_id = str(uuid4())
    _log_event(
        event_id=event_id,
        workspace_id=workspace_id,
        sensor=sensor,
        alert_level=alert_level,
        rag_query=rag_query,
        rag_answer=rag_answer,
        intent=intent,
        nearest=nearest,
        directive=directive,
    )

    logger.info("EmergencySim: COMPLETE event_id={}", event_id)

    return {
        "event_id": event_id,
        "sensor": sensor,
        "alert_level": alert_level,
        "rag_query": rag_query,
        "rag_answer": rag_answer,
        "rag_sources": rag_sources,
        "intent": intent.model_dump(),
        "nearest_feature": nearest,
        "directive": directive,
    }


def list_events(workspace_id: str) -> list:
    if not db_available():
        return []
    with get_db() as cur:
        cur.execute(
            "SELECT * FROM emergency_events WHERE workspace_id = %s ORDER BY created_at DESC",
            (workspace_id,),
        )
        return [dict(r) for r in cur.fetchall()]


def _build_directive(
    intent: IntentResult, nearest: Optional[dict], sensor: dict
) -> str:
    parts = [f"פעולה: {intent.action} | דחיפות: {intent.urgency}"]
    if nearest:
        display = nearest.get("distance_display", f"{nearest.get('distance_m', '?')} m")
        parts.append(f"יעד: {nearest['label']} (מרחק: {display})")
    elif intent.target_type != "none":
        parts.append("אין נקודת פינוי רשומה — יש לפעול לפי פרוטוקול פינוי כללי")
    parts.append(f"הופעל על ידי: {sensor.get('name', sensor.get('sensor_id'))}")
    return " | ".join(parts)


def _sse(event: str, data: str) -> str:
    """Format a single Server-Sent Event string."""
    return f"event: {event}\ndata: {data}\n\n"


def simulate_stream(
    workspace_id: str,
    sensor_id: str,
    alert_level: str = "high",
    override_query: Optional[str] = None,
    origin_lat: Optional[float] = None,
    origin_lng: Optional[float] = None,
) -> Generator[str, None, None]:
    """
    SSE generator for the full emergency simulation pipeline.

    Yields SSE-formatted strings in this order:
      status("connecting")      — immediately on entry
      status("retrieving")      — before hybrid retrieval
      status("streaming")       — before the first LLM token
      token(<text chunk>)       — one per Groq streaming delta
      status("analyzing")       — before intent extraction
      status("routing")         — before Haversine geo lookup
      result(<json payload>)    — final complete result dict
      error(<json message>)     — only on unrecoverable failure

    All data values are JSON-encoded strings so special characters (including
    Hebrew and newlines) are safely transported over the SSE wire format.
    """
    # Lazy imports — limits circular-import surface to the streaming path.
    from app.retrieval.search import hybrid_search
    from app.rag.generator import stream_tokens

    yield _sse("status", _json.dumps("connecting"))

    # ── 1. Fetch sensor ───────────────────────────────────────────────────────
    sensor = sensor_service.get_sensor(sensor_id)
    if not sensor:
        yield _sse("error", _json.dumps({"detail": f"Sensor not found: {sensor_id}"}))
        return

    sensor_lat: Optional[float] = sensor.get("lat")
    sensor_lng: Optional[float] = sensor.get("lng")

    # ── 2. Build Hebrew RAG query ─────────────────────────────────────────────
    type_label = _SENSOR_TYPE_LABELS.get(sensor.get("sensor_type", ""), "אירוע חירום")
    rag_query = override_query or (
        f"חיישן {type_label} בשם '{sensor['name']}' הפעיל התרעה. "
        "מה פרוטוקול הפעולה הנדרש? אילו צעדים יש לנקוט?"
    )
    logger.debug("EmergencyStream: query={!r}", rag_query)

    # ── 3. Hybrid retrieval ───────────────────────────────────────────────────
    yield _sse("status", _json.dumps("retrieving"))
    context = []
    rag_sources: list = []
    try:
        context = hybrid_search(rag_query, top_k=5, workspace_id=workspace_id)
        rag_sources = [
            {
                "document_id": r.document_id,
                "file_name": getattr(r, "file_name", ""),
                "page_num": r.page_num,
                "chunk_id": r.chunk_id,
                "text_snippet": r.text[:300],
            }
            for r in context
        ]
    except Exception as exc:
        logger.error("EmergencyStream: retrieval failed — {}", exc)

    # ── 4. Stream LLM generation ──────────────────────────────────────────────
    yield _sse("status", _json.dumps("streaming"))
    rag_answer = ""
    try:
        for delta in stream_tokens(rag_query, context):
            rag_answer += delta
            yield _sse("token", _json.dumps(delta))
    except Exception as exc:
        logger.error("EmergencyStream: LLM streaming failed — {}", exc)
        fallback = "המידע המבוקש לא נמצא במסמכים שסופקו."
        rag_answer = fallback
        yield _sse("token", _json.dumps(fallback))

    # ── 5. Guard: no protocol in RAG ──────────────────────────────────────────
    if _RAG_MISSING_MARKER in rag_answer:
        logger.info("EmergencyStream: RAG returned no-protocol — skipping intent + geo")
        intent = IntentResult(action="no_protocol", target_type="none", urgency="low")
        directive = _DIRECTIVE_NO_PROTOCOL
        event_id = str(uuid4())
        try:
            _log_event(
                event_id=event_id, workspace_id=workspace_id, sensor=sensor,
                alert_level=alert_level, rag_query=rag_query, rag_answer=rag_answer,
                intent=intent, nearest=None, directive=directive,
            )
        except Exception as exc:
            logger.error("EmergencyStream: event persistence failed (no-protocol) — {}", exc)
        yield _sse("result", _json.dumps({
            "event_id": event_id, "sensor": sensor, "alert_level": alert_level,
            "rag_query": rag_query, "rag_answer": rag_answer, "rag_sources": rag_sources,
            "intent": intent.model_dump(), "nearest_feature": None, "directive": directive,
        }, default=_json_default))
        return

    # ── 6. Intent extraction ──────────────────────────────────────────────────
    yield _sse("status", _json.dumps("analyzing"))
    try:
        intent: IntentResult = extract_intent(rag_answer)
    except Exception as exc:
        logger.error("EmergencyStream: intent extraction failed — {}", exc)
        intent = IntentResult(action="proceed_to_shelter", target_type="shelter", urgency="critical")

    logger.info(
        "EmergencyStream: intent action={} target={} urgency={}",
        intent.action, intent.target_type, intent.urgency,
    )

    # ── 7. Haversine geo routing ──────────────────────────────────────────────
    yield _sse("status", _json.dumps("routing"))
    route_lat = origin_lat if origin_lat is not None else sensor_lat
    route_lng = origin_lng if origin_lng is not None else sensor_lng

    nearest: Optional[dict] = None
    if route_lat is not None and route_lng is not None and intent.target_type != "none":
        try:
            nearest = geo_service.find_nearest_feature(
                workspace_id=workspace_id,
                feature_type=intent.target_type,
                lat=route_lat,
                lng=route_lng,
            )
            if nearest:
                dist_m = nearest["distance_m"]
                nearest["distance_display"] = (
                    f"{dist_m / 1000:.1f} km" if dist_m > 1000 else f"{int(dist_m)} m"
                )
        except Exception as exc:
            logger.error("EmergencyStream: geo routing failed — {}", exc)

    # ── 8. Build directive + persist event ───────────────────────────────────
    directive = _build_directive(intent, nearest, sensor)
    event_id = str(uuid4())
    try:
        _log_event(
            event_id=event_id, workspace_id=workspace_id, sensor=sensor,
            alert_level=alert_level, rag_query=rag_query, rag_answer=rag_answer,
            intent=intent, nearest=nearest, directive=directive,
        )
    except Exception as exc:
        logger.error("EmergencyStream: event persistence failed — {}", exc)

    logger.info("EmergencyStream: COMPLETE event_id={}", event_id)

    yield _sse("result", _json.dumps({
        "event_id": event_id, "sensor": sensor, "alert_level": alert_level,
        "rag_query": rag_query, "rag_answer": rag_answer, "rag_sources": rag_sources,
        "intent": intent.model_dump(), "nearest_feature": nearest, "directive": directive,
    }, default=_json_default))


def _log_event(
    event_id: str,
    workspace_id: str,
    sensor: dict,
    alert_level: str,
    rag_query: str,
    rag_answer: str,
    intent: IntentResult,
    nearest: Optional[dict],
    directive: str,
) -> None:
    if not db_available():
        return
    with get_db() as cur:
        cur.execute(
            """
            INSERT INTO emergency_events (
                event_id, workspace_id, sensor_id, sensor_name, sensor_type,
                alert_level, rag_query, rag_answer,
                intent_action, intent_target, intent_urgency,
                nearest_feature_id, nearest_feature_type, nearest_feature_label,
                nearest_distance_m, directive, created_at
            ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            """,
            (
                event_id, workspace_id,
                sensor.get("sensor_id"), sensor.get("name"), sensor.get("sensor_type"),
                alert_level, rag_query, rag_answer,
                intent.action, intent.target_type, intent.urgency,
                nearest.get("feature_id") if nearest else None,
                nearest.get("feature_type") if nearest else None,
                nearest.get("label") if nearest else None,
                nearest.get("distance_m") if nearest else None,
                directive, datetime.utcnow(),
            ),
        )
