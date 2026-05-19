"""Compare two audit logs.

Scenarios are deterministic given (kind, seed); replaying the same
inputs should produce identical (event_type, payload_json) at each
sequence number. Timestamps and hashes naturally diverge between runs
and are excluded from the comparison — what matters for catching
builder drift is the semantic content of each event.

Output is a DiffResult that the web layer renders as HTML and the CLI
emits as JSON. Both representations highlight the first sequence at
which the two logs disagree, plus the common prefix length.
"""

from __future__ import annotations

import html
import json
from dataclasses import dataclass
from pathlib import Path

from chaos_backend.audit.log import AuditLogEntry, AuditLogReader


@dataclass(frozen=True, slots=True)
class EntryDelta:
    sequence: int
    a_event_type: str | None
    a_payload_json: str | None
    b_event_type: str | None
    b_payload_json: str | None

    @property
    def kind(self) -> str:
        if self.a_event_type is None:
            return "missing_in_a"
        if self.b_event_type is None:
            return "missing_in_b"
        if self.a_event_type != self.b_event_type:
            return "event_type_changed"
        return "payload_changed"


@dataclass(frozen=True, slots=True)
class DiffResult:
    a_label: str
    b_label: str
    a_length: int
    b_length: int
    common_prefix_length: int
    deltas: tuple[EntryDelta, ...]

    @property
    def identical(self) -> bool:
        return not self.deltas and self.a_length == self.b_length

    @property
    def first_divergence_sequence(self) -> int | None:
        return self.deltas[0].sequence if self.deltas else None


def compare(
    a_entries: list[AuditLogEntry],
    b_entries: list[AuditLogEntry],
    *,
    a_label: str = "a",
    b_label: str = "b",
) -> DiffResult:
    deltas: list[EntryDelta] = []
    common = 0
    overlap = min(len(a_entries), len(b_entries))

    for i in range(overlap):
        a = a_entries[i]
        b = b_entries[i]
        if a.event_type == b.event_type and a.payload_json == b.payload_json:
            common += 1
            continue
        deltas.append(
            EntryDelta(
                sequence=a.sequence,
                a_event_type=a.event_type,
                a_payload_json=a.payload_json,
                b_event_type=b.event_type,
                b_payload_json=b.payload_json,
            )
        )

    if len(a_entries) > overlap:
        for extra in a_entries[overlap:]:
            deltas.append(
                EntryDelta(
                    sequence=extra.sequence,
                    a_event_type=extra.event_type,
                    a_payload_json=extra.payload_json,
                    b_event_type=None,
                    b_payload_json=None,
                )
            )

    if len(b_entries) > overlap:
        for extra in b_entries[overlap:]:
            deltas.append(
                EntryDelta(
                    sequence=extra.sequence,
                    a_event_type=None,
                    a_payload_json=None,
                    b_event_type=extra.event_type,
                    b_payload_json=extra.payload_json,
                )
            )

    return DiffResult(
        a_label=a_label,
        b_label=b_label,
        a_length=len(a_entries),
        b_length=len(b_entries),
        common_prefix_length=common,
        deltas=tuple(deltas),
    )


def compare_paths(
    a_path: str | Path,
    b_path: str | Path,
    *,
    a_label: str | None = None,
    b_label: str | None = None,
) -> DiffResult:
    a_entries = AuditLogReader.load(a_path)
    b_entries = AuditLogReader.load(b_path)
    return compare(
        a_entries,
        b_entries,
        a_label=a_label or str(a_path),
        b_label=b_label or str(b_path),
    )


_STYLE = """
body {
    background: #0A1628;
    color: #E8E2D0;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, sans-serif;
    margin: 0;
    padding: 32px 48px;
    font-size: 13px;
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
    margin-bottom: 24px;
}
.status {
    margin: 16px 0 24px 0;
    padding: 10px 16px;
    border-left: 2px solid;
    font-size: 12px;
    letter-spacing: 2px;
    font-weight: 700;
}
.status.identical { border-color: #96DCA0; color: #96DCA0; background: rgba(150, 220, 160, 0.06); }
.status.different { border-color: #DC5050; color: #DC5050; background: rgba(220, 80, 80, 0.06); }
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
table { width: 100%; border-collapse: collapse; font-size: 12px; }
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
    font-family: ui-monospace, "SF Mono", Menlo, monospace;
}
td.seq  { width: 56px; color: rgba(232, 226, 208, 0.55); }
td.kind { width: 180px; color: #C9A961; font-weight: 700; letter-spacing: 1px; }
td.side {
    width: 50%;
    color: rgba(232, 226, 208, 0.78);
    white-space: pre-wrap;
    word-break: break-word;
}
.side--missing { color: rgba(232, 226, 208, 0.30); font-style: italic; }
"""


def render_html(result: DiffResult) -> str:
    status_class = "identical" if result.identical else "different"
    status_text = (
        f"IDENTICAL · {result.common_prefix_length} entries match"
        if result.identical
        else (
            f"DIVERGENT · first delta at sequence "
            f"{result.first_divergence_sequence} · "
            f"{result.common_prefix_length} matching entries before"
        )
    )

    rows = "\n".join(_render_row(delta) for delta in result.deltas)
    if not rows:
        rows = (
            '<tr><td colspan="4" class="side side--missing">'
            "no deltas — the logs are byte-equivalent in their event stream"
            "</td></tr>"
        )

    return f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Chaos One — Engagement Diff</title>
    <style>{_STYLE}</style>
</head>
<body>
    <div class="title">ENGAGEMENT DIFF</div>
    <div class="subtitle">comparing two audit logs by (sequence, event_type, payload)</div>

    <div class="status {status_class}">{status_text}</div>

    <div class="meta">
        <div><div class="meta__key">A</div><div class="meta__value">{html.escape(result.a_label)}</div></div>
        <div><div class="meta__key">B</div><div class="meta__value">{html.escape(result.b_label)}</div></div>
        <div><div class="meta__key">A LEN</div><div class="meta__value">{result.a_length}</div></div>
        <div><div class="meta__key">B LEN</div><div class="meta__value">{result.b_length}</div></div>
    </div>

    <table>
        <thead>
            <tr>
                <th>SEQ</th>
                <th>KIND</th>
                <th>A</th>
                <th>B</th>
            </tr>
        </thead>
        <tbody>
            {rows}
        </tbody>
    </table>
</body>
</html>
"""


def _render_row(delta: EntryDelta) -> str:
    return (
        "<tr>"
        f'<td class="seq">#{delta.sequence:04d}</td>'
        f'<td class="kind">{html.escape(delta.kind)}</td>'
        f'<td class="side {_side_class(delta.a_event_type)}">{_pretty(delta.a_event_type, delta.a_payload_json)}</td>'
        f'<td class="side {_side_class(delta.b_event_type)}">{_pretty(delta.b_event_type, delta.b_payload_json)}</td>'
        "</tr>"
    )


def _side_class(event_type: str | None) -> str:
    return "side--missing" if event_type is None else ""


def _pretty(event_type: str | None, payload_json: str | None) -> str:
    if event_type is None:
        return "(absent)"
    payload = payload_json or ""
    try:
        parsed = json.loads(payload) if payload else {}
        formatted = json.dumps(parsed, indent=2, sort_keys=True)
    except json.JSONDecodeError:
        formatted = payload
    return f"{html.escape(event_type)}\n{html.escape(formatted)}"
