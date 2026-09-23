"""Durable, DuckDB-backed buffer for recording and querying system interaction history."""

import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import duckdb

from config import Config

_SCHEMA = """
CREATE SEQUENCE IF NOT EXISTS history_id_seq START 1;

CREATE TABLE IF NOT EXISTS query_history (
    id BIGINT PRIMARY KEY DEFAULT nextval('history_id_seq'),
    ts TIMESTAMP NOT NULL DEFAULT current_timestamp,
    query_text VARCHAR NOT NULL,
    status VARCHAR NOT NULL,
    duration_ms DOUBLE,
    rows_affected BIGINT,
    source VARCHAR,
    username VARCHAR,
    error_message VARCHAR
);

CREATE INDEX IF NOT EXISTS idx_query_history_ts ON query_history(ts);
CREATE INDEX IF NOT EXISTS idx_query_history_status ON query_history(status);
"""


class HistoryBuffer:
    """Wraps a DuckDB connection and exposes the query-history buffer operations."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or Config.from_env()
        storage_dir = os.path.dirname(self.config.duckdb_storage_path)
        if storage_dir:
            os.makedirs(storage_dir, exist_ok=True)
        self.conn = duckdb.connect(self.config.duckdb_storage_path)
        self._init_schema()

    def _init_schema(self) -> None:
        self.conn.execute(_SCHEMA)

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "HistoryBuffer":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()

    def log(
        self,
        query_text: str,
        status: str = "success",
        duration_ms: Optional[float] = None,
        rows_affected: Optional[int] = None,
        source: Optional[str] = None,
        username: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> int:
        """Insert a new history record and return its generated id."""
        result = self.conn.execute(
            """
            INSERT INTO query_history
                (query_text, status, duration_ms, rows_affected, source, username, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            RETURNING id
            """,
            [query_text, status, duration_ms, rows_affected, source, username, error_message],
        ).fetchone()
        return result[0]

    def list(
        self,
        limit: int = 20,
        status: Optional[str] = None,
        username: Optional[str] = None,
        since: Optional[datetime] = None,
        search: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Return the most recent history records, newest first, honoring optional filters."""
        clauses = []
        params: list[Any] = []

        if status:
            clauses.append("status = ?")
            params.append(status)
        if username:
            clauses.append("username = ?")
            params.append(username)
        if since:
            clauses.append("ts >= ?")
            params.append(since)
        if search:
            clauses.append("query_text ILIKE ?")
            params.append(f"%{search}%")

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)

        rows = self.conn.execute(
            f"""
            SELECT id, ts, query_text, status, duration_ms, rows_affected, source, username, error_message
            FROM query_history
            {where}
            ORDER BY ts DESC
            LIMIT ?
            """,
            params,
        ).fetchall()
        columns = [d[0] for d in self.conn.description]
        return [dict(zip(columns, row)) for row in rows]

    def stats(self) -> dict[str, Any]:
        """Return aggregate statistics over the entire buffer."""
        total, avg_duration, p95_duration, error_count = self.conn.execute(
            """
            SELECT
                count(*),
                avg(duration_ms),
                quantile_cont(duration_ms, 0.95),
                count(*) FILTER (WHERE status != 'success')
            FROM query_history
            """
        ).fetchone()

        by_status = self.conn.execute(
            """
            SELECT status, count(*) AS count
            FROM query_history
            GROUP BY status
            ORDER BY count DESC
            """
        ).fetchall()

        slowest = self.conn.execute(
            """
            SELECT id, ts, query_text, duration_ms
            FROM query_history
            WHERE duration_ms IS NOT NULL
            ORDER BY duration_ms DESC
            LIMIT 5
            """
        ).fetchall()

        return {
            "total_records": total or 0,
            "avg_duration_ms": avg_duration,
            "p95_duration_ms": p95_duration,
            "error_count": error_count or 0,
            "by_status": [{"status": s, "count": c} for s, c in by_status],
            "slowest_queries": [
                {"id": i, "ts": t, "query_text": q, "duration_ms": d} for i, t, q, d in slowest
            ],
        }

    def purge(self, retention_days: Optional[int] = None) -> int:
        """Delete records older than the retention window and return the number removed."""
        days = retention_days if retention_days is not None else self.config.max_history_retention_days
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = self.conn.execute(
            "DELETE FROM query_history WHERE ts < ? RETURNING id", [cutoff]
        ).fetchall()
        return len(result)
