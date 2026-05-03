"""
Database abstraction layer.

Auto-detects what's available:
  1. PostgreSQL  — if DATABASE_URL is set AND the server responds
  2. SQLite      — automatic fallback, stored at local_data/protocol_genesis.db

All service code uses get_db() / db_available() unchanged.
The _DBCursor wrapper translates psycopg2-style %s params → ? for SQLite.
"""

import os
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime

# ─── Module state ────────────────────────────────────────────────────────────

_mode: str | None = None          # 'postgres' | 'sqlite'
_pg_pool = None                   # psycopg2 ThreadedConnectionPool
_sqlite_path: str | None = None
_sqlite_local = threading.local() # per-thread SQLite connections

# Register adapters so Python datetime ↔ SQLite TEXT round-trips cleanly
sqlite3.register_adapter(datetime, lambda d: d.isoformat(sep=" "))
sqlite3.register_converter(
    "TIMESTAMP",
    lambda b: datetime.fromisoformat(b.decode().replace(" ", "T")),
)


# ─── Cursor wrapper ───────────────────────────────────────────────────────────

class _DBCursor:
    """
    Uniform cursor for both backends.

    Translates:
      %s  →  ? (SQLite parameter style)
    """

    def __init__(self, raw, mode: str):
        self._raw = raw
        self._sqlite = mode == "sqlite"

    def execute(self, sql: str, params=None):
        if self._sqlite:
            sql = sql.replace("%s", "?")
        if params is not None:
            self._raw.execute(sql, params)
        else:
            self._raw.execute(sql)
        return self

    def fetchone(self) -> dict | None:
        row = self._raw.fetchone()
        return dict(row) if row is not None else None

    def fetchall(self) -> list[dict]:
        return [dict(r) for r in self._raw.fetchall()]

    def close(self):
        self._raw.close()


# ─── Initialisation ───────────────────────────────────────────────────────────

def init_pool() -> bool:
    """
    Try PostgreSQL first (if DATABASE_URL is set), then fall back to SQLite.
    Always returns True — SQLite is always available.
    """
    global _mode, _pg_pool, _sqlite_path

    db_url = os.getenv("DATABASE_URL")
    if db_url:
        try:
            from psycopg2 import pool as _pg
            _pg_pool = _pg.ThreadedConnectionPool(1, 20, db_url)
            _mode = "postgres"
            print("Database: PostgreSQL connected")
            return True
        except Exception as e:
            print(f"Database: PostgreSQL unavailable ({e}) — falling back to SQLite")

    # SQLite fallback
    base = os.path.dirname(os.path.abspath(__file__))
    data_dir = os.path.join(base, "local_data")
    os.makedirs(data_dir, exist_ok=True)
    _sqlite_path = os.path.join(data_dir, "protocol_genesis.db")
    _mode = "sqlite"
    print(f"Database: SQLite at {_sqlite_path}")
    return True


def db_available() -> bool:
    return _mode is not None


def get_mode() -> str | None:
    return _mode


# ─── Context manager ─────────────────────────────────────────────────────────

def _sqlite_conn() -> sqlite3.Connection:
    if not hasattr(_sqlite_local, "conn") or _sqlite_local.conn is None:
        conn = sqlite3.connect(
            _sqlite_path,
            detect_types=sqlite3.PARSE_DECLTYPES,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _sqlite_local.conn = conn
    return _sqlite_local.conn


@contextmanager
def get_db():
    if _mode is None:
        raise RuntimeError("Call init_pool() before using the database.")

    if _mode == "postgres":
        conn = _pg_pool.getconn()
        try:
            from psycopg2.extras import RealDictCursor
            raw = conn.cursor(cursor_factory=RealDictCursor)
            cur = _DBCursor(raw, "postgres")
            try:
                yield cur
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                raw.close()
        finally:
            _pg_pool.putconn(conn)

    else:  # sqlite
        conn = _sqlite_conn()
        raw = conn.cursor()
        cur = _DBCursor(raw, "sqlite")
        try:
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            raw.close()
