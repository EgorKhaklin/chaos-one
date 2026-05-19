"""Persistent storage for engagement records.

A small SQLite-backed catalog of past dashboard runs. Each record points
at the on-disk JSONL audit log; the log itself stays the source of
truth, the catalog just lets the UI browse it.
"""

from chaos_backend.storage.engagements import (
    EngagementRecord,
    EngagementRepository,
    default_database_path,
)

__all__ = [
    "EngagementRecord",
    "EngagementRepository",
    "default_database_path",
]
