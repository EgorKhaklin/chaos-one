"""Tests for the audit-log diff layer."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

from chaos_backend.audit import (
    AuditLogReader,
    AuditLogWriter,
    compare_log_paths,
    compare_logs,
    render_diff_html,
)
from chaos_backend.cli import main


def _write(path: Path, events: list[tuple[str, dict[str, object]]]) -> None:
    with AuditLogWriter(path) as writer:
        for event_type, payload in events:
            writer.append(event_type, payload)


def test_identical_event_streams_diff_clean(tmp_path: Path) -> None:
    a_path = tmp_path / "a.jsonl"
    b_path = tmp_path / "b.jsonl"
    events = [("alpha", {"k": 1}), ("bravo", {"k": 2}), ("charlie", {"k": 3})]
    _write(a_path, events)
    _write(b_path, events)

    result = compare_log_paths(a_path, b_path)
    assert result.identical is True
    assert result.common_prefix_length == 3
    assert result.deltas == ()
    assert result.first_divergence_sequence is None


def test_payload_divergence_pinpoints_sequence(tmp_path: Path) -> None:
    a_path = tmp_path / "a.jsonl"
    b_path = tmp_path / "b.jsonl"
    _write(a_path, [("alpha", {"k": 1}), ("bravo", {"k": 2})])
    _write(b_path, [("alpha", {"k": 1}), ("bravo", {"k": 99})])

    result = compare_log_paths(a_path, b_path)
    assert result.identical is False
    assert result.common_prefix_length == 1
    assert result.first_divergence_sequence == 2
    assert result.deltas[0].kind == "payload_changed"


def test_event_type_change_classified_correctly(tmp_path: Path) -> None:
    a_path = tmp_path / "a.jsonl"
    b_path = tmp_path / "b.jsonl"
    _write(a_path, [("alpha", {})])
    _write(b_path, [("zebra", {})])

    result = compare_log_paths(a_path, b_path)
    assert result.deltas[0].kind == "event_type_changed"


def test_extra_entries_in_one_log_flagged_as_missing(tmp_path: Path) -> None:
    a_path = tmp_path / "a.jsonl"
    b_path = tmp_path / "b.jsonl"
    _write(a_path, [("alpha", {}), ("bravo", {}), ("charlie", {})])
    _write(b_path, [("alpha", {})])

    result = compare_log_paths(a_path, b_path)
    assert result.a_length == 3
    assert result.b_length == 1
    kinds = [d.kind for d in result.deltas]
    assert kinds == ["missing_in_b", "missing_in_b"]


def test_compare_logs_with_in_memory_entries(tmp_path: Path) -> None:
    path = tmp_path / "log.jsonl"
    _write(path, [("alpha", {}), ("bravo", {})])
    entries = AuditLogReader.load(path)

    result = compare_logs(entries, entries, a_label="self", b_label="self")
    assert result.identical is True


def test_render_html_marks_status_correctly(tmp_path: Path) -> None:
    a_path = tmp_path / "a.jsonl"
    b_path = tmp_path / "b.jsonl"
    _write(a_path, [("alpha", {"k": 1})])
    _write(b_path, [("alpha", {"k": 2})])

    rendered = render_diff_html(compare_log_paths(a_path, b_path))
    assert "DIVERGENT" in rendered
    assert "ENGAGEMENT DIFF" in rendered


def test_render_html_when_identical(tmp_path: Path) -> None:
    a_path = tmp_path / "a.jsonl"
    b_path = tmp_path / "b.jsonl"
    events = [("alpha", {"k": 1}), ("bravo", {"k": 2})]
    _write(a_path, events)
    _write(b_path, events)

    rendered = render_diff_html(compare_log_paths(a_path, b_path))
    assert "IDENTICAL" in rendered


def test_cli_audit_diff_emits_json_and_optional_html(tmp_path: Path) -> None:
    a_path = tmp_path / "a.jsonl"
    b_path = tmp_path / "b.jsonl"
    html_path = tmp_path / "diff.html"
    _write(a_path, [("alpha", {"k": 1})])
    _write(b_path, [("alpha", {"k": 2})])

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = main(["audit", "diff", str(a_path), str(b_path), "--html", str(html_path)])
    assert code == 1  # divergent
    payload = json.loads(buffer.getvalue())
    assert payload["identical"] is False
    assert payload["first_divergence_sequence"] == 1
    assert html_path.exists()
    assert "ENGAGEMENT DIFF" in html_path.read_text(encoding="utf-8")


def test_cli_audit_diff_returns_zero_when_identical(tmp_path: Path) -> None:
    a_path = tmp_path / "a.jsonl"
    b_path = tmp_path / "b.jsonl"
    events = [("alpha", {"k": 1})]
    _write(a_path, events)
    _write(b_path, events)

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = main(["audit", "diff", str(a_path), str(b_path)])
    assert code == 0
    payload = json.loads(buffer.getvalue())
    assert payload["identical"] is True
