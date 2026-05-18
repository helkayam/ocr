import os
import sys

# Ensure backend/ internals resolve correctly regardless of working directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI
from loguru import logger
from fastapi.middleware.cors import CORSMiddleware
from api import workspaces, files
from api import search, sensors, map as map_router
from api.rag_router import documents_router, query_router
from api.emergency_router import router as emergency_router
from db import init_pool, get_db, db_available
from services.storage_service import ensure_bucket

app = FastAPI(title="Protocol Genesis API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(workspaces.router)
app.include_router(files.router)
app.include_router(search.router)
app.include_router(sensors.router)
app.include_router(map_router.router)
app.include_router(documents_router)
app.include_router(query_router)
app.include_router(emergency_router)


@app.get("/")
def root():
    return {"status": "ok", "service": "Protocol Genesis API"}


@app.get("/health")
def health():
    from db import get_mode
    from services.storage_service import storage_mode
    return {
        "status": "ok",
        "database": get_mode() or "unavailable",
        "storage": storage_mode(),
    }


# ─── Schema (works for both PostgreSQL and SQLite) ───────────────────────────
# Uses CURRENT_TIMESTAMP (SQL standard, not PostgreSQL-only NOW()).
# Uses TEXT for JSON columns so SQLite stores them as plain strings.

_SCHEMA = """
CREATE TABLE IF NOT EXISTS workspaces (
    workspace_id TEXT      PRIMARY KEY,
    name         TEXT      NOT NULL,
    description  TEXT,
    file_count   INTEGER   DEFAULT 0,
    total_size   INTEGER   DEFAULT 0,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS files (
    file_id           TEXT      PRIMARY KEY,
    workspace_id      TEXT      NOT NULL,
    filename          TEXT      NOT NULL,
    file_type         TEXT      NOT NULL,
    content_type      TEXT,
    file_size         INTEGER   DEFAULT 0,
    object_name       TEXT      NOT NULL,
    status            TEXT      DEFAULT 'completed',
    processing_status TEXT      DEFAULT 'pending',
    created_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS document_chunks (
    chunk_id     TEXT      PRIMARY KEY,
    file_id      TEXT      NOT NULL,
    workspace_id TEXT      NOT NULL,
    content      TEXT      NOT NULL,
    chunk_index  INTEGER   NOT NULL,
    embedding    TEXT,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS sensors (
    sensor_id      TEXT      PRIMARY KEY,
    workspace_id   TEXT      NOT NULL,
    name           TEXT      NOT NULL,
    sensor_type    TEXT      NOT NULL,
    endpoint       TEXT,
    status         TEXT      DEFAULT 'active',
    linked_file_id TEXT,
    lat            REAL,
    lng            REAL,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS geo_features (
    feature_id   TEXT      PRIMARY KEY,
    workspace_id TEXT      NOT NULL,
    feature_type TEXT      NOT NULL,
    label        TEXT      NOT NULL,
    lat          REAL      NOT NULL,
    lng          REAL      NOT NULL,
    floor        TEXT,
    metadata     TEXT      DEFAULT '{}',
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS emergency_events (
    event_id              TEXT      PRIMARY KEY,
    workspace_id          TEXT      NOT NULL,
    sensor_id             TEXT,
    sensor_name           TEXT,
    sensor_type           TEXT,
    alert_level           TEXT      DEFAULT 'high',
    rag_query             TEXT,
    rag_answer            TEXT,
    intent_action         TEXT,
    intent_target         TEXT,
    intent_urgency        TEXT,
    nearest_feature_id    TEXT,
    nearest_feature_type  TEXT,
    nearest_feature_label TEXT,
    nearest_distance_m    REAL,
    directive             TEXT,
    status                TEXT      DEFAULT 'simulated',
    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS geo_layers (
    layer_id      TEXT      PRIMARY KEY,
    file_id       TEXT      UNIQUE NOT NULL,
    workspace_id  TEXT      NOT NULL,
    geojson_data  TEXT,
    feature_count INTEGER   DEFAULT 0,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS map_tags (
    tag_id       TEXT             PRIMARY KEY,
    workspace_id TEXT             NOT NULL,
    file_id      TEXT,
    label        TEXT             NOT NULL,
    lat          REAL             NOT NULL,
    lng          REAL             NOT NULL,
    tag_type     TEXT             DEFAULT 'point',
    color        TEXT             DEFAULT '#ef4444',
    created_at   TIMESTAMP        DEFAULT CURRENT_TIMESTAMP
);
"""


def init_db():
    if not db_available():
        return
    # SQLite doesn't support multiple statements in a single execute call
    with get_db() as cur:
        for stmt in _SCHEMA.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                cur.execute(stmt)
    _migrate_db()
    logger.info("Database schema ready")


def _migrate_db():
    """Idempotent column additions for existing deployments (safe on both PG and SQLite)."""
    if not db_available():
        return
    migrations = [
        "ALTER TABLE sensors ADD COLUMN lat REAL",
        "ALTER TABLE sensors ADD COLUMN lng REAL",
        "ALTER TABLE geo_layers ADD COLUMN geo_category TEXT",
        "ALTER TABLE geo_features ADD COLUMN file_id TEXT",
    ]
    with get_db() as cur:
        for sql in migrations:
            try:
                cur.execute(sql)
            except Exception:
                pass  # column already exists (PG: DuplicateColumn, SQLite: OperationalError)


@app.on_event("startup")
def startup():
    init_pool()
    init_db()
    ensure_bucket()
    _init_rag_dirs()
    _preload_embedding_model()


def _init_rag_dirs():
    from pathlib import Path
    for d in ("data/raw", "data/ocr", "data/chunks", "data/index"):
        Path(d).mkdir(parents=True, exist_ok=True)


def _preload_embedding_model():
    try:
        from app.indexing import embedder
        logger.info("RAG: pre-loading E5 embedding model…")
        embedder.get_model()
        logger.info("RAG: embedding model ready")
    except Exception as e:
        logger.warning("RAG: embedding model preload failed ({}) — will load on first request", e)
