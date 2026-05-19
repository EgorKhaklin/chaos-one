"""Tests for the HTML audit reel viewer."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

from chaos_backend.audit import (
    AuditLogReader,
    AuditLogVerifier,
    AuditLogWriter,
    render_html,
    render_html_from_path,
)
from chaos_backend.cli import main


def _build_sample_log(path: Path) -> None:
    with AuditLogWriter(path) as writer:
        writer.append("engagement_begin", {"scenario": "peer_salvo"})
        writer.append("mode_changed", {"previous": "Nominal", "current": "SensorDegraded"})
        writer.append("coa_authorized", {"id": "COA-B"})
        writer.append("engagement_end", {})


def test_render_html_contains_status_and_rows(tmp_path: Path) -> None:
    log_path = tmp_path / "engagement.jsonl"
    _build_sample_log(log_path)
    entries = AuditLogReader.load(log_path)
    verification = AuditLogVerifier.verify(entries)

    rendered = render_html(entries, verification, source_path=str(log_path))

    assert "<title>Chaos One — Audit Reel</title>" in rendered
    assert "CHAIN VERIFIED" in rendered
    assert "engagement_begin" in rendered
    assert "coa_authorized" in rendered
    assert "#0001" in rendered
    assert "#0004" in rendered


def test_render_html_reports_broken_chain(tmp_path: Path) -> None:
    log_path = tmp_path / "engagement.jsonl"
    _build_sample_log(log_path)

    # Tamper with a payload to break the chain.
    lines = log_path.read_text().splitlines()
    second = json.loads(lines[1])
    second["payload_json"] = '{"tampered":true}'
    lines[1] = json.dumps(second)
    log_path.write_text("\n".join(lines) + "\n")

    rendered = render_html_from_path(log_path)
    assert "CHAIN BROKEN" in rendered
    assert "seq 2" in rendered


def test_render_html_escapes_user_payload(tmp_path: Path) -> None:
    log_path = tmp_path / "engagement.jsonl"
    with AuditLogWriter(log_path) as writer:
        writer.append("note", {"text": "<script>alert(1)</script>"})

    rendered = render_html_from_path(log_path)
    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered


def test_cli_audit_html_writes_file(tmp_path: Path) -> None:
    log_path = tmp_path / "engagement.jsonl"
    html_path = tmp_path / "out" / "audit.html"
    _build_sample_log(log_path)

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = main(["audit", "html", str(log_path), str(html_path)])

    assert code == 0
    payload = json.loads(buffer.getvalue())
    assert payload["output"].endswith("audit.html")
    assert payload["bytes"] > 1000
    assert html_path.exists()
    assert "AUDIT REEL" in html_path.read_text(encoding="utf-8")


def test_render_html_handles_empty_log(tmp_path: Path) -> None:
    log_path = tmp_path / "empty.jsonl"
    log_path.write_text("")
    rendered = render_html_from_path(log_path)
    assert "CHAIN VERIFIED" in rendered
    assert "0 entries" in rendered


def test_render_html_handles_malformed_payload_field(tmp_path: Path) -> None:
    # payload_json is normally valid JSON but if a future writer ever
    # emits raw text, the renderer must escape it rather than crash.
    log_path = tmp_path / "engagement.jsonl"
    _build_sample_log(log_path)

    lines = log_path.read_text().splitlines()
    first = json.loads(lines[0])
    first["payload_json"] = "not valid json"
    lines[0] = json.dumps(first)
    log_path.write_text("\n".join(lines) + "\n")

    entries = AuditLogReader.load(log_path)
    rendered = render_html(entries, AuditLogVerifier.verify(entries))
    assert "not valid json" in rendered
