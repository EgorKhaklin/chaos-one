"""Tests for the Python audit log writer / reader / verifier."""

from __future__ import annotations

import json
from pathlib import Path

from chaos_backend.audit import (
    AuditLogReader,
    AuditLogVerifier,
    AuditLogWriter,
)


def test_writer_creates_chained_entries(tmp_path: Path) -> None:
    log_path = tmp_path / "engagement.jsonl"
    with AuditLogWriter(log_path) as writer:
        a = writer.append("alpha", {"k": 1})
        b = writer.append("bravo", {"k": 2})
        c = writer.append("charlie", {"k": 3})

    entries = AuditLogReader.load(log_path)
    assert [e.sequence for e in entries] == [1, 2, 3]
    assert entries[0].previous_hash == ""
    assert entries[1].previous_hash == a.hash
    assert entries[2].previous_hash == b.hash
    assert entries[2].hash == c.hash


def test_verifier_accepts_a_clean_chain(tmp_path: Path) -> None:
    log_path = tmp_path / "engagement.jsonl"
    with AuditLogWriter(log_path) as writer:
        for i in range(5):
            writer.append("tick", {"i": i})

    entries = AuditLogReader.load(log_path)
    result = AuditLogVerifier.verify(entries)
    assert result.valid is True
    assert result.failed_at_sequence == 0


def test_verifier_rejects_tampered_payload(tmp_path: Path) -> None:
    log_path = tmp_path / "engagement.jsonl"
    with AuditLogWriter(log_path) as writer:
        writer.append("alpha", {"k": 1})
        writer.append("bravo", {"k": 2})

    # Tamper with the second entry's payload but leave the recorded hash
    # intact: verifier must catch the mismatch.
    raw_lines = log_path.read_text().splitlines()
    second = json.loads(raw_lines[1])
    second["payload_json"] = '{"k":999}'
    raw_lines[1] = json.dumps(second)
    log_path.write_text("\n".join(raw_lines) + "\n")

    entries = AuditLogReader.load(log_path)
    result = AuditLogVerifier.verify(entries)
    assert result.valid is False
    assert result.failed_at_sequence == 2


def test_verifier_rejects_sequence_gap(tmp_path: Path) -> None:
    log_path = tmp_path / "engagement.jsonl"
    with AuditLogWriter(log_path) as writer:
        writer.append("a", {})
        writer.append("b", {})
        writer.append("c", {})

    lines = log_path.read_text().splitlines()
    # Drop the middle entry.
    log_path.write_text(lines[0] + "\n" + lines[2] + "\n")

    entries = AuditLogReader.load(log_path)
    result = AuditLogVerifier.verify(entries)
    assert result.valid is False
    assert "sequence gap" in result.failure_reason


def test_empty_log_verifies_ok(tmp_path: Path) -> None:
    log_path = tmp_path / "empty.jsonl"
    log_path.write_text("")
    entries = AuditLogReader.load(log_path)
    result = AuditLogVerifier.verify(entries)
    assert result.valid is True


def test_writer_threads_request_id_through_entries(tmp_path: Path) -> None:
    log_path = tmp_path / "engagement.jsonl"
    with AuditLogWriter(log_path, request_id="rq_abc12345") as writer:
        writer.append("alpha", {})
        writer.append("bravo", {})

    entries = AuditLogReader.load(log_path)
    assert all(e.request_id == "rq_abc12345" for e in entries)


def test_chain_with_request_id_verifies(tmp_path: Path) -> None:
    log_path = tmp_path / "engagement.jsonl"
    with AuditLogWriter(log_path, request_id="rq_observer_01") as writer:
        for i in range(4):
            writer.append("tick", {"i": i})

    entries = AuditLogReader.load(log_path)
    assert AuditLogVerifier.verify(entries).valid is True


def test_tampered_request_id_breaks_chain(tmp_path: Path) -> None:
    log_path = tmp_path / "engagement.jsonl"
    with AuditLogWriter(log_path, request_id="rq_real") as writer:
        writer.append("alpha", {})
        writer.append("bravo", {})

    lines = log_path.read_text().splitlines()
    second = json.loads(lines[1])
    second["request_id"] = "rq_evil"
    lines[1] = json.dumps(second)
    log_path.write_text("\n".join(lines) + "\n")

    entries = AuditLogReader.load(log_path)
    result = AuditLogVerifier.verify(entries)
    assert result.valid is False
    assert result.failed_at_sequence == 2


def test_legacy_log_without_request_id_still_verifies(tmp_path: Path) -> None:
    # Logs written before request_id existed have no request_id field;
    # AuditLogEntry defaults to empty string, the canonical hash form
    # excludes the trailing |request_id segment, and verification still
    # passes.
    log_path = tmp_path / "engagement.jsonl"
    with AuditLogWriter(log_path) as writer:
        writer.append("alpha", {})
        writer.append("bravo", {})

    entries = AuditLogReader.load(log_path)
    assert all(e.request_id == "" for e in entries)
    assert AuditLogVerifier.verify(entries).valid is True


def test_writer_close_is_idempotent(tmp_path: Path) -> None:
    log_path = tmp_path / "engagement.jsonl"
    writer = AuditLogWriter(log_path)
    writer.append("hello", {})
    writer.close()
    writer.close()  # second close is a no-op


def test_cli_audit_demo_writes_and_verifies(tmp_path: Path) -> None:
    import io
    import json
    from contextlib import redirect_stdout

    from chaos_backend.cli import main

    log_path = tmp_path / "demo.jsonl"
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = main(["audit", "demo", str(log_path)])
    assert code == 0

    payload = json.loads(buffer.getvalue())
    assert payload["verified"] is True
    assert payload["entries"] == 5
    assert log_path.exists()


def test_cli_audit_verify_returns_zero_on_clean_log(tmp_path: Path) -> None:
    import io
    import json
    from contextlib import redirect_stdout

    from chaos_backend.cli import main

    log_path = tmp_path / "engagement.jsonl"
    with AuditLogWriter(log_path) as writer:
        writer.append("alpha", {"k": 1})
        writer.append("bravo", {"k": 2})

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = main(["audit", "verify", str(log_path)])
    assert code == 0
    payload = json.loads(buffer.getvalue())
    assert payload["valid"] is True
    assert payload["entry_count"] == 2


def test_cli_audit_query_filters_by_event_type(tmp_path: Path) -> None:
    import io
    import json
    from contextlib import redirect_stdout

    from chaos_backend.cli import main

    log_path = tmp_path / "engagement.jsonl"
    with AuditLogWriter(log_path) as writer:
        writer.append("alpha", {})
        writer.append("bravo", {})
        writer.append("alpha", {})

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = main(["audit", "query", str(log_path), "--event-type", "alpha"])
    assert code == 0
    payload = json.loads(buffer.getvalue())
    assert payload["matches"] == 2
    assert payload["total_entries"] == 3
    assert all(entry["event_type"] == "alpha" for entry in payload["entries"])
