"""Render an audit log to a self-contained HTML page.

The output matches the in-browser operator surfaces' styling: deep navy canvas,
muted gold accents, monospace timestamps and event types, a banner at
the top showing whether the chain verified. No external assets — the
CSS is embedded so the file can be opened from disk or attached to an
email without breaking.
"""

from __future__ import annotations

import html
import json
from datetime import datetime
from pathlib import Path

from chaos_backend.audit.log import AuditLogEntry, VerificationResult

_STYLE = """
body {
    background: #0A1628;
    color: #E8E2D0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, sans-serif;
    margin: 0;
    padding: 32px 48px;
    font-size: 13px;
    line-height: 1.5;
}
.header {
    border-left: 2px solid #C9A961;
    padding: 6px 16px 6px 14px;
    margin-bottom: 24px;
}
.title {
    color: #C9A961;
    font-size: 18px;
    font-weight: 700;
    letter-spacing: 5px;
    margin-bottom: 4px;
}
.subtitle {
    color: rgba(232, 226, 208, 0.55);
    font-size: 11px;
    letter-spacing: 1px;
}
.status {
    margin: 16px 0 24px 0;
    padding: 10px 16px;
    border-left: 2px solid;
    font-size: 12px;
    letter-spacing: 2px;
    font-weight: 700;
}
.status.ok       { border-color: #96DCA0; color: #96DCA0; background: rgba(150, 220, 160, 0.06); }
.status.broken   { border-color: #DC5050; color: #DC5050; background: rgba(220, 80, 80, 0.06); }
.meta {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 12px 24px;
    margin-bottom: 28px;
    padding: 14px 16px;
    background: rgba(16, 28, 48, 0.55);
    border-left: 2px solid rgba(201, 169, 97, 0.5);
}
.meta__key   { color: rgba(232, 226, 208, 0.5); font-size: 9px; letter-spacing: 2px; font-weight: 700; }
.meta__value { color: #E8E2D0; font-size: 13px; font-weight: 700; }
table {
    width: 100%;
    border-collapse: collapse;
    font-size: 12px;
}
th {
    text-align: left;
    color: #C9A961;
    font-size: 9px;
    letter-spacing: 2px;
    padding: 8px 12px;
    border-bottom: 1px solid rgba(201, 169, 97, 0.4);
}
td {
    padding: 8px 12px;
    border-bottom: 1px solid rgba(232, 226, 208, 0.08);
    vertical-align: top;
}
td.seq      { width: 56px; color: rgba(232, 226, 208, 0.55); font-family: ui-monospace, "SF Mono", Menlo, monospace; }
td.time     { width: 240px; color: rgba(232, 226, 208, 0.82); font-family: ui-monospace, "SF Mono", Menlo, monospace; }
td.type     { width: 220px; color: #C9A961; font-weight: 700; letter-spacing: 1px; }
td.payload  { color: rgba(232, 226, 208, 0.78); font-family: ui-monospace, "SF Mono", Menlo, monospace; white-space: pre-wrap; word-break: break-word; }
td.hash     { color: rgba(232, 226, 208, 0.32); font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 10px; }
.footer {
    margin-top: 32px;
    padding-top: 14px;
    border-top: 1px solid rgba(201, 169, 97, 0.2);
    color: rgba(232, 226, 208, 0.42);
    font-size: 10px;
    letter-spacing: 1px;
}
"""


def _escape(value: str) -> str:
    return html.escape(value, quote=True)


def _pretty_payload(payload_json: str) -> str:
    try:
        parsed = json.loads(payload_json)
    except json.JSONDecodeError:
        return _escape(payload_json)
    return _escape(json.dumps(parsed, indent=2, sort_keys=True))


def render(
    entries: list[AuditLogEntry],
    verification: VerificationResult,
    *,
    source_path: str | None = None,
) -> str:
    status_class = "ok" if verification.valid else "broken"
    status_text = (
        f"CHAIN VERIFIED · {len(entries)} entries"
        if verification.valid
        else (
            f"CHAIN BROKEN at seq {verification.failed_at_sequence}: "
            f"{_escape(verification.failure_reason)}"
        )
    )

    earliest = entries[0].utc_iso if entries else "--"
    latest = entries[-1].utc_iso if entries else "--"

    request_ids = {e.request_id for e in entries if e.request_id}
    request_id_meta = (
        f"""<div>
            <div class="meta__key">REQUEST ID</div>
            <div class="meta__value">{_escape(next(iter(request_ids)))}</div>
        </div>"""
        if len(request_ids) == 1
        else ""
    )

    rows = "\n".join(
        f"""<tr>
            <td class="seq">#{entry.sequence:04d}</td>
            <td class="time">{_escape(entry.utc_iso)}</td>
            <td class="type">{_escape(entry.event_type)}</td>
            <td class="payload">{_pretty_payload(entry.payload_json)}</td>
            <td class="hash">{_escape(entry.hash[:12])}</td>
        </tr>"""
        for entry in entries
    )

    source_meta = f'<div class="meta__value">{_escape(source_path)}</div>' if source_path else ""
    source_block = (
        f"""<div>
            <div class="meta__key">SOURCE</div>
            {source_meta}
        </div>"""
        if source_path
        else ""
    )

    return f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Chaos One — Audit Reel</title>
    <style>{_STYLE}</style>
</head>
<body>
    <div class="header">
        <div class="title">AUDIT REEL</div>
        <div class="subtitle">post-engagement record · sha-256 merkle chain</div>
    </div>

    <div class="status {status_class}">{status_text}</div>

    <div class="meta">
        <div>
            <div class="meta__key">ENTRIES</div>
            <div class="meta__value">{len(entries)}</div>
        </div>
        <div>
            <div class="meta__key">EARLIEST</div>
            <div class="meta__value">{_escape(earliest)}</div>
        </div>
        <div>
            <div class="meta__key">LATEST</div>
            <div class="meta__value">{_escape(latest)}</div>
        </div>
        {source_block}
        {request_id_meta}
    </div>

    <table>
        <thead>
            <tr>
                <th>SEQ</th>
                <th>UTC</th>
                <th>EVENT</th>
                <th>PAYLOAD</th>
                <th>HASH</th>
            </tr>
        </thead>
        <tbody>
            {rows}
        </tbody>
    </table>

    <div class="footer">
        rendered {_escape(datetime.now().isoformat(timespec="seconds"))} · chaos-backend audit html_viewer
    </div>
</body>
</html>
"""


def render_from_path(path: str | Path) -> str:
    from chaos_backend.audit.log import AuditLogReader, AuditLogVerifier

    entries = AuditLogReader.load(path)
    verification = AuditLogVerifier.verify(entries)
    return render(entries, verification, source_path=str(path))
