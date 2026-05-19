"""Audit log writer, reader, and verifier.

Each entry is one JSONL line carrying its sequence number, monotonic
timestamp, UTC ISO timestamp, event type, payload (already-serialized
JSON string), and a SHA-256 hash chaining it to the previous entry.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import IO


@dataclass(frozen=True, slots=True)
class AuditLogEntry:
    sequence: int
    monotonic_ts: float
    utc_iso: str
    event_type: str
    payload_json: str
    previous_hash: str
    hash: str


@dataclass(slots=True)
class VerificationResult:
    valid: bool
    failed_at_sequence: int = 0
    failure_reason: str = ""

    @classmethod
    def ok(cls) -> VerificationResult:
        return cls(valid=True)

    @classmethod
    def failed(cls, sequence: int, reason: str) -> VerificationResult:
        return cls(valid=False, failed_at_sequence=sequence, failure_reason=reason)


def _canonical_string(
    previous_hash: str,
    sequence: int,
    monotonic_ts: float,
    event_type: str,
    payload_json: str,
) -> str:
    return f"{previous_hash}|{sequence}|{monotonic_ts!r}|{event_type}|{payload_json}"


def _hash(
    previous_hash: str,
    sequence: int,
    monotonic_ts: float,
    event_type: str,
    payload_json: str,
) -> str:
    canonical = _canonical_string(previous_hash, sequence, monotonic_ts, event_type, payload_json)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(slots=True)
class AuditLogWriter:
    """Append events to a JSONL audit log, maintaining a SHA-256 chain.

    The writer is purposely synchronous and small: the audit reel is a
    correctness surface, not a hot path. One log file per engagement.
    """

    path: Path
    _previous_hash: str = field(default="")
    _sequence: int = field(default=0)
    _started_at: float = field(default_factory=time.perf_counter)
    _stream: IO[str] | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        # Open in append mode but truncate first; one log per engagement
        # boot, so existing content is intentional only when continuing.
        self.path.write_text("")
        self._stream = self.path.open("a", encoding="utf-8")

    def append(self, event_type: str, payload: object) -> AuditLogEntry:
        if self._stream is None:
            raise RuntimeError("audit log writer is closed")

        self._sequence += 1
        monotonic = time.perf_counter() - self._started_at
        utc_iso = datetime.now(UTC).isoformat()
        payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True)

        digest = _hash(self._previous_hash, self._sequence, monotonic, event_type, payload_json)

        entry = AuditLogEntry(
            sequence=self._sequence,
            monotonic_ts=monotonic,
            utc_iso=utc_iso,
            event_type=event_type,
            payload_json=payload_json,
            previous_hash=self._previous_hash,
            hash=digest,
        )

        self._stream.write(json.dumps(asdict(entry)) + "\n")
        self._stream.flush()
        self._previous_hash = digest
        return entry

    def close(self) -> None:
        if self._stream is not None:
            self._stream.close()
            self._stream = None

    def __enter__(self) -> AuditLogWriter:
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()


class AuditLogReader:
    @staticmethod
    def load(path: str | Path) -> list[AuditLogEntry]:
        target = Path(path)
        entries: list[AuditLogEntry] = []
        for line in target.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            data = json.loads(stripped)
            entries.append(AuditLogEntry(**data))
        return entries


class AuditLogVerifier:
    @staticmethod
    def verify(entries: list[AuditLogEntry]) -> VerificationResult:
        expected_previous = ""
        expected_sequence = 0

        for entry in entries:
            expected_sequence += 1

            if entry.sequence != expected_sequence:
                return VerificationResult.failed(
                    entry.sequence,
                    f"sequence gap: expected {expected_sequence}, got {entry.sequence}",
                )

            if entry.previous_hash != expected_previous:
                return VerificationResult.failed(
                    entry.sequence,
                    "previous_hash does not match the prior entry's hash",
                )

            recomputed = _hash(
                entry.previous_hash,
                entry.sequence,
                entry.monotonic_ts,
                entry.event_type,
                entry.payload_json,
            )
            if entry.hash != recomputed:
                return VerificationResult.failed(
                    entry.sequence,
                    "hash does not match recomputed digest",
                )

            expected_previous = entry.hash

        return VerificationResult.ok()
