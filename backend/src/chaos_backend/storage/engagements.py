"""SQLite engagement catalog.

A single `engagements` table indexed by started_at. Connections are
opened per call rather than pooled: SQLite handles concurrent reads
itself, writes serialize at the database file, and the dashboard's
traffic is two-digits-per-second at most.

Schema migrations: just one `CREATE TABLE IF NOT EXISTS`. When the
schema grows, add explicit migration steps that read PRAGMA user_version
and bump it.
"""

from __future__ import annotations

import secrets
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS engagements (
    id          TEXT PRIMARY KEY,
    scenario    TEXT NOT NULL,
    seed        INTEGER NOT NULL,
    started_at  TEXT NOT NULL,
    ended_at    TEXT NOT NULL,
    events      INTEGER NOT NULL,
    verified    INTEGER NOT NULL,
    log_path    TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS engagements_started_at
    ON engagements(started_at DESC);
"""


def default_database_path() -> Path:
    """Where the dashboard stores its engagement catalog by default.

    `~/.chaos-one/engagements.db` keeps the persistent state alongside
    audit logs and out of the working directory.
    """
    return Path.home() / ".chaos-one" / "engagements.db"


@dataclass(frozen=True, slots=True)
class EngagementRecord:
    id: str
    scenario: str
    seed: int
    started_at: str  # ISO UTC
    ended_at: str  # ISO UTC
    events: int
    verified: bool
    log_path: str


@dataclass(slots=True)
class EngagementRepository:
    """SQLite-backed engagement catalog.

    Construct once per process; the repo is cheap and stateless beyond
    the database path. Call init() once at startup; subsequent reads
    and writes open fresh connections.
    """

    database_path: Path

    def __post_init__(self) -> None:
        self.database_path = Path(self.database_path)

    def init(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(_SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.database_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def insert(
        self,
        *,
        scenario: str,
        seed: int,
        started_at: datetime,
        ended_at: datetime,
        events: int,
        verified: bool,
        log_path: str | Path,
    ) -> EngagementRecord:
        record = EngagementRecord(
            id=_new_id(),
            scenario=scenario,
            seed=seed,
            started_at=_iso(started_at),
            ended_at=_iso(ended_at),
            events=events,
            verified=verified,
            log_path=str(log_path),
        )
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO engagements (
                    id, scenario, seed, started_at, ended_at,
                    events, verified, log_path
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.scenario,
                    record.seed,
                    record.started_at,
                    record.ended_at,
                    record.events,
                    1 if record.verified else 0,
                    record.log_path,
                ),
            )
        return record

    def get(self, engagement_id: str) -> EngagementRecord | None:
        with self._connect() as conn:
            cursor = conn.execute("SELECT * FROM engagements WHERE id = ?", (engagement_id,))
            row = cursor.fetchone()
            return _row_to_record(row) if row is not None else None

    def recent(self, limit: int = 20) -> list[EngagementRecord]:
        with self._connect() as conn:
            cursor = conn.execute(
                "SELECT * FROM engagements ORDER BY started_at DESC LIMIT ?",
                (max(0, int(limit)),),
            )
            return [_row_to_record(row) for row in cursor.fetchall()]

    def count(self) -> int:
        with self._connect() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM engagements")
            (n,) = cursor.fetchone()
            return int(n)

    def delete(self, engagement_id: str) -> bool:
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM engagements WHERE id = ?", (engagement_id,))
            return bool(cursor.rowcount)


def _row_to_record(row: sqlite3.Row) -> EngagementRecord:
    return EngagementRecord(
        id=row["id"],
        scenario=row["scenario"],
        seed=int(row["seed"]),
        started_at=row["started_at"],
        ended_at=row["ended_at"],
        events=int(row["events"]),
        verified=bool(row["verified"]),
        log_path=row["log_path"],
    )


def _new_id() -> str:
    return "eng_" + secrets.token_hex(6)


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat(timespec="seconds")
