"""FastAPI dashboard for the Chaos One backend.

Endpoints
---------
GET  /         landing page with a scenario picker form
POST /play     run a scenario into an audit log and return rendered HTML
GET  /health   liveness probe
GET  /version  version + capability snapshot

The body of the rendered audit log is the same self-contained navy/gold
HTML that the CLI's `audit html` subcommand produces.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncIterator
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from chaos_backend import __version__
from chaos_backend.audit import (
    AuditLogReader,
    AuditLogVerifier,
    compare_log_paths,
    render_diff_html,
    render_html_from_path,
)
from chaos_backend.simulation.scenario_runner import run as run_scenario
from chaos_backend.simulation.scenario_runner import stream_scenario
from chaos_backend.simulation.scenarios import ScenarioKind, build
from chaos_backend.storage import EngagementRepository, default_database_path

_LANDING_HTML = """<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Chaos One — Dashboard</title>
    <style>
        body {
            background: #0A1628;
            color: #E8E2D0;
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, sans-serif;
            margin: 0;
            padding: 64px 48px;
        }
        h1 {
            color: #C9A961;
            font-size: 22px;
            font-weight: 700;
            letter-spacing: 6px;
            margin: 0 0 6px 0;
        }
        .subtitle {
            color: rgba(232, 226, 208, 0.55);
            font-size: 12px;
            letter-spacing: 2px;
            margin-bottom: 36px;
        }
        form {
            display: flex;
            gap: 16px;
            align-items: flex-end;
            padding: 20px;
            background: rgba(16, 28, 48, 0.55);
            border-left: 2px solid #C9A961;
            max-width: 760px;
        }
        .field { display: flex; flex-direction: column; gap: 6px; }
        label {
            color: rgba(232, 226, 208, 0.55);
            font-size: 10px;
            letter-spacing: 2px;
            font-weight: 700;
        }
        select, input {
            background: rgba(10, 22, 40, 0.92);
            color: #E8E2D0;
            border: 1px solid rgba(201, 169, 97, 0.4);
            padding: 8px 12px;
            font-size: 13px;
            font-family: ui-monospace, "SF Mono", Menlo, monospace;
        }
        button {
            border: none;
            padding: 10px 22px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 3px;
            cursor: pointer;
        }
        .btn-primary { background: #C9A961; color: #0A1628; }
        .btn-primary:hover { background: #DCBC74; }
        .btn-secondary {
            background: rgba(232, 226, 208, 0.04);
            color: rgba(232, 226, 208, 0.85);
            border: 1px solid rgba(232, 226, 208, 0.25);
        }
        .btn-secondary:hover { background: rgba(232, 226, 208, 0.10); }

        .stream {
            margin-top: 36px;
            max-width: 1200px;
        }
        .stream__status {
            padding: 10px 16px;
            font-size: 11px;
            letter-spacing: 2px;
            font-weight: 700;
            margin-bottom: 12px;
            border-left: 2px solid;
        }
        .stream__status.idle      { border-color: rgba(232, 226, 208, 0.25); color: rgba(232, 226, 208, 0.55); }
        .stream__status.streaming { border-color: #C9A961; color: #C9A961; }
        .stream__status.done      { border-color: #96DCA0; color: #96DCA0; }
        .stream__status.error     { border-color: #DC5050; color: #DC5050; }

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
        }
        td.seq { width: 56px; color: rgba(232, 226, 208, 0.55); font-family: ui-monospace, "SF Mono", Menlo, monospace; }
        td.t   { width: 100px; color: rgba(232, 226, 208, 0.78); font-family: ui-monospace, "SF Mono", Menlo, monospace; }
        td.type { width: 240px; color: #C9A961; font-weight: 700; letter-spacing: 1px; }
        td.payload { color: rgba(232, 226, 208, 0.78); font-family: ui-monospace, "SF Mono", Menlo, monospace; white-space: pre-wrap; word-break: break-word; }

        @keyframes flash { from { background: rgba(201, 169, 97, 0.18); } to { background: transparent; } }
        tr.fresh { animation: flash 800ms ease-out; }

        .engagements {
            margin-top: 36px;
            max-width: 1200px;
            padding: 16px;
            background: rgba(16, 28, 48, 0.55);
            border-left: 2px solid rgba(201, 169, 97, 0.55);
        }
        .engagements__title {
            color: #C9A961;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 4px;
            margin-bottom: 12px;
        }
        .engagements__empty {
            margin-top: 24px;
            color: rgba(232, 226, 208, 0.50);
            font-size: 11px;
            letter-spacing: 1px;
        }

        .meta {
            margin-top: 36px;
            color: rgba(232, 226, 208, 0.40);
            font-size: 11px;
            letter-spacing: 1px;
        }
        a { color: #C9A961; text-decoration: none; }
        a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <h1>CHAOS ONE</h1>
    <div class="subtitle">post-engagement audit dashboard · v{version}</div>

    <form id="run-form" method="post" action="/play">
        <div class="field">
            <label for="scenario">SCENARIO</label>
            <select id="scenario" name="scenario">
                {scenario_options}
            </select>
        </div>
        <div class="field">
            <label for="seed">SEED</label>
            <input id="seed" name="seed" type="number" value="42" min="0" />
        </div>
        <div class="field">
            <label for="speed">SPEED (live)</label>
            <input id="speed" type="number" value="8" min="1" step="1" />
        </div>
        <button class="btn-primary" type="submit">RUN</button>
        <button class="btn-secondary" type="button" id="stream-btn">STREAM</button>
    </form>

    <div class="stream">
        <div id="status" class="stream__status idle">IDLE</div>
        <table>
            <thead>
                <tr>
                    <th>SEQ</th>
                    <th>T (s)</th>
                    <th>EVENT</th>
                    <th>PAYLOAD</th>
                </tr>
            </thead>
            <tbody id="rows"></tbody>
        </table>
    </div>

    {recent_engagements}

    <div class="meta">
        <a href="/health">/health</a> &nbsp;·&nbsp;
        <a href="/version">/version</a> &nbsp;·&nbsp;
        <a href="/engagements">/engagements</a> &nbsp;·&nbsp;
        <a href="/docs">/docs</a> &nbsp;·&nbsp;
        <a href="https://github.com/EgorKhaklin/chaos-one" target="_blank">repo</a>
    </div>

    <script>
    (() => {
        const status = document.getElementById('status');
        const rows = document.getElementById('rows');
        let source = null;

        function setStatus(text, cls) {
            status.textContent = text;
            status.className = 'stream__status ' + cls;
        }

        function escape(s) {
            return String(s).replace(/[&<>"']/g, (c) => ({
                '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
            })[c]);
        }

        function appendRow(evt) {
            const tr = document.createElement('tr');
            tr.className = 'fresh';
            const payload = JSON.stringify(evt.payload, null, 2);
            tr.innerHTML = (
                '<td class="seq">#' + String(evt.sequence).padStart(4, '0') + '</td>' +
                '<td class="t">' + evt.scenario_t.toFixed(2) + '</td>' +
                '<td class="type">' + escape(evt.event_type) + '</td>' +
                '<td class="payload">' + escape(payload) + '</td>'
            );
            rows.appendChild(tr);
        }

        document.getElementById('stream-btn').addEventListener('click', () => {
            if (source) { source.close(); source = null; }
            rows.innerHTML = '';

            const scenario = document.getElementById('scenario').value;
            const seed = document.getElementById('seed').value;
            const speed = document.getElementById('speed').value;

            const url = '/play/stream?scenario=' + encodeURIComponent(scenario)
                      + '&seed=' + encodeURIComponent(seed)
                      + '&speed=' + encodeURIComponent(speed);

            source = new EventSource(url);
            setStatus('STREAMING ' + scenario + ' (seed ' + seed + ', ' + speed + 'x)', 'streaming');

            source.addEventListener('audit', (e) => {
                appendRow(JSON.parse(e.data));
            });
            source.addEventListener('done', (e) => {
                const summary = JSON.parse(e.data);
                setStatus('DONE · ' + summary.events + ' events', 'done');
                source.close();
                source = null;
            });
            source.addEventListener('error', () => {
                setStatus('STREAM ERROR', 'error');
                source.close();
                source = null;
            });
        });
    })();
    </script>
</body>
</html>
"""


def _scenario_options() -> str:
    return "\n".join(f'<option value="{k.value}">{k.value}</option>' for k in ScenarioKind)


def build_app(
    *,
    repository: EngagementRepository | None = None,
    log_directory: Path | None = None,
) -> FastAPI:
    application = FastAPI(
        title="Chaos One Dashboard",
        version=__version__,
        docs_url="/docs",
        redoc_url=None,
    )

    repo = repository or EngagementRepository(
        database_path=Path(os.environ.get("CHAOS_DB_PATH") or default_database_path())
    )
    repo.init()

    logs_dir = log_directory or Path(
        os.environ.get("CHAOS_LOG_DIR") or (Path.home() / ".chaos-one" / "audit")
    )
    logs_dir.mkdir(parents=True, exist_ok=True)

    @application.get("/", response_class=HTMLResponse)
    def landing() -> str:
        return (
            _LANDING_HTML.replace("{version}", __version__)
            .replace("{scenario_options}", _scenario_options())
            .replace("{recent_engagements}", _render_recent_engagements(repo))
        )

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @application.get("/version")
    def version() -> dict[str, Any]:
        return {
            "version": __version__,
            "scenarios": [k.value for k in ScenarioKind],
        }

    @application.get("/play/stream")
    async def play_stream(
        scenario: str,
        seed: int = 42,
        speed: float = 8.0,
    ) -> StreamingResponse:
        try:
            kind = ScenarioKind(scenario)
        except ValueError:
            return StreamingResponse(
                _sse_error(f"unknown scenario: {scenario}"),
                media_type="text/event-stream",
                status_code=400,
            )

        scenario_obj = build(kind, seed=seed)

        async def event_source() -> AsyncIterator[bytes]:
            async for streamed in stream_scenario(scenario_obj, speed=speed, realtime=True):
                yield _sse_frame("audit", asdict(streamed))
            yield _sse_frame("done", {"events": scenario_obj.events.__len__() + 2})

        return StreamingResponse(
            event_source(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @application.post("/play", response_class=HTMLResponse)
    def play(scenario: str = Form(...), seed: int = Form(42)) -> HTMLResponse:
        try:
            kind = ScenarioKind(scenario)
        except ValueError:
            return HTMLResponse(
                content=f"unknown scenario: {scenario}",
                status_code=400,
            )

        scenario_obj = build(kind, seed=seed)
        log_path = logs_dir / _engagement_filename(kind.value, seed)

        started_at = datetime.now(UTC)
        result = run_scenario(scenario_obj, log_path=log_path, realtime=False)
        ended_at = datetime.now(UTC)

        verification = AuditLogVerifier.verify(AuditLogReader.load(log_path))
        repo.insert(
            scenario=kind.value,
            seed=seed,
            started_at=started_at,
            ended_at=ended_at,
            events=result.events_emitted,
            verified=verification.valid,
            log_path=str(log_path),
        )
        return HTMLResponse(content=render_html_from_path(log_path))

    @application.get("/engagements")
    def engagements(limit: int = 20) -> dict[str, Any]:
        records = repo.recent(limit=limit)
        return {
            "count": len(records),
            "engagements": [asdict(r) for r in records],
        }

    @application.get("/engagements/{engagement_id}")
    def engagement_detail(engagement_id: str) -> dict[str, Any]:
        record = repo.get(engagement_id)
        if record is None:
            raise HTTPException(status_code=404, detail="engagement not found")
        return asdict(record)

    @application.get("/engagements/{engagement_id}/audit.html", response_class=HTMLResponse)
    def engagement_audit_html(engagement_id: str) -> HTMLResponse:
        record = repo.get(engagement_id)
        if record is None:
            raise HTTPException(status_code=404, detail="engagement not found")
        if not Path(record.log_path).exists():
            raise HTTPException(status_code=410, detail="log file no longer on disk")
        return HTMLResponse(content=render_html_from_path(record.log_path))

    @application.get("/engagements/{a_id}/diff/{b_id}", response_class=HTMLResponse)
    def engagement_diff(a_id: str, b_id: str) -> HTMLResponse:
        record_a = repo.get(a_id)
        record_b = repo.get(b_id)
        if record_a is None or record_b is None:
            raise HTTPException(status_code=404, detail="engagement not found")
        if not Path(record_a.log_path).exists() or not Path(record_b.log_path).exists():
            raise HTTPException(status_code=410, detail="log file no longer on disk")
        result = compare_log_paths(
            record_a.log_path,
            record_b.log_path,
            a_label=f"{record_a.id} · {record_a.scenario}#{record_a.seed}",
            b_label=f"{record_b.id} · {record_b.scenario}#{record_b.seed}",
        )
        return HTMLResponse(content=render_diff_html(result))

    @application.exception_handler(404)
    def not_found(_request: Any, _exc: Any) -> JSONResponse:
        return JSONResponse(status_code=404, content={"error": "not found"})

    return application


def _sse_frame(event: str, payload: dict[str, Any]) -> bytes:
    return f"event: {event}\ndata: {json.dumps(payload)}\n\n".encode()


async def _sse_error(message: str) -> AsyncIterator[bytes]:
    yield _sse_frame("error", {"message": message})


def _engagement_filename(scenario: str, seed: int) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
    return f"{stamp}_{scenario}_seed{seed}.jsonl"


def _render_recent_engagements(repo: EngagementRepository) -> str:
    records = repo.recent(limit=10)
    if not records:
        return '<div class="engagements__empty">no engagements yet — run one above</div>'
    rows = "\n".join(
        f"""<tr>
            <td class="seq"><a href="/engagements/{r.id}/audit.html">{r.id}</a></td>
            <td class="t">{r.scenario}</td>
            <td class="t">{r.seed}</td>
            <td class="t">{r.events}</td>
            <td class="t">{"OK" if r.verified else "BROKEN"}</td>
            <td class="t">{r.started_at}</td>
        </tr>"""
        for r in records
    )
    return f"""
<div class="engagements">
    <div class="engagements__title">RECENT ENGAGEMENTS</div>
    <table>
        <thead>
            <tr>
                <th>ID</th>
                <th>SCENARIO</th>
                <th>SEED</th>
                <th>EVENTS</th>
                <th>CHAIN</th>
                <th>STARTED (UTC)</th>
            </tr>
        </thead>
        <tbody>
            {rows}
        </tbody>
    </table>
</div>
"""


app = build_app()
