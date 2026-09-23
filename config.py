"""Environment-driven configuration for the query history buffer."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    duckdb_storage_path: str
    max_history_retention_days: int

    @classmethod
    def from_env(cls) -> "Config":
        storage_path = os.getenv("DUCKDB_STORAGE_PATH", "./data/query_history.duckdb")
        retention_raw = os.getenv("MAX_HISTORY_RETENTION_DAYS", "30")
        try:
            retention_days = int(retention_raw)
        except ValueError as exc:
            raise ValueError(
                f"MAX_HISTORY_RETENTION_DAYS must be an integer, got {retention_raw!r}"
            ) from exc
        if retention_days <= 0:
            raise ValueError("MAX_HISTORY_RETENTION_DAYS must be a positive integer")
        return cls(
            duckdb_storage_path=storage_path,
            max_history_retention_days=retention_days,
        )
