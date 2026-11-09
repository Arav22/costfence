"""SQLite usage logging for persistent cost tracking."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from threading import Lock
from typing import Optional


DEFAULT_DB_PATH = Path.home() / ".costfence" / "usage.db"


class UsageDB:
    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = path or DEFAULT_DB_PATH
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._conn = sqlite3.connect(str(self._path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                input_tokens INTEGER NOT NULL DEFAULT 0,
                output_tokens INTEGER NOT NULL DEFAULT 0,
                cost REAL NOT NULL DEFAULT 0.0,
                project TEXT,
                session_id TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_usage_timestamp ON usage(timestamp);
            CREATE INDEX IF NOT EXISTS idx_usage_project ON usage(project);
        """)

    def log(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        project: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO usage (timestamp, provider, model, input_tokens, output_tokens, cost, project, session_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (time.time(), provider, model, input_tokens, output_tokens, cost, project, session_id),
            )
            self._conn.commit()

    def get_total_cost(self, since: Optional[float] = None) -> float:
        with self._lock:
            if since:
                row = self._conn.execute("SELECT COALESCE(SUM(cost), 0) FROM usage WHERE timestamp >= ?", (since,)).fetchone()
            else:
                row = self._conn.execute("SELECT COALESCE(SUM(cost), 0) FROM usage").fetchone()
            return row[0]

    def get_cost_by_provider(self, since: Optional[float] = None) -> dict[str, float]:
        with self._lock:
            if since:
                rows = self._conn.execute(
                    "SELECT provider, COALESCE(SUM(cost), 0) as total FROM usage WHERE timestamp >= ? GROUP BY provider",
                    (since,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT provider, COALESCE(SUM(cost), 0) as total FROM usage GROUP BY provider"
                ).fetchall()
            return {r["provider"]: r["total"] for r in rows}

    def get_cost_by_model(self, since: Optional[float] = None) -> dict[str, float]:
        with self._lock:
            if since:
                rows = self._conn.execute(
                    "SELECT model, COALESCE(SUM(cost), 0) as total FROM usage WHERE timestamp >= ? GROUP BY model",
                    (since,),
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT model, COALESCE(SUM(cost), 0) as total FROM usage GROUP BY model"
                ).fetchall()
            return {r["model"]: r["total"] for r in rows}

    def get_recent(self, limit: int = 20) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM usage ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_token_totals(self, since: Optional[float] = None) -> dict[str, int]:
        with self._lock:
            if since:
                row = self._conn.execute(
                    "SELECT COALESCE(SUM(input_tokens), 0), COALESCE(SUM(output_tokens), 0) FROM usage WHERE timestamp >= ?",
                    (since,),
                ).fetchone()
            else:
                row = self._conn.execute(
                    "SELECT COALESCE(SUM(input_tokens), 0), COALESCE(SUM(output_tokens), 0) FROM usage"
                ).fetchone()
            return {"input": row[0], "output": row[1]}

    def close(self) -> None:
        self._conn.close()
