from fastapi import FastAPI
from api import workspaces, files
import os
import psycopg2

app = FastAPI()

app.include_router(workspaces.router)
app.include_router(files.router)


@app.get("/health")
def health():
    return {"status": "ok"}

def init_db():
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        print("DATABASE_URL not set, skipping DB init")
        return

    conn = psycopg2.connect(db_url)
    conn.autocommit = True
    cur = conn.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS workspaces (
        workspace_id TEXT PRIMARY KEY,
        created_at TIMESTAMP DEFAULT NOW()
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS files (
        file_id UUID PRIMARY KEY,
        workspace_id TEXT NOT NULL,
        filename TEXT NOT NULL,
        content_type TEXT,
        file_size BIGINT,
        object_name TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT NOW()
    );
    """)

    cur.close()
    conn.close()

@app.on_event("startup")
def startup():
    init_db()