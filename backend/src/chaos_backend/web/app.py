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

import tempfile
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, JSONResponse

from chaos_backend import __version__
from chaos_backend.audit import render_html_from_path
from chaos_backend.simulation.scenario_runner import run as run_scenario
from chaos_backend.simulation.scenarios import ScenarioKind, build

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
            max-width: 720px;
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
            background: #C9A961;
            color: #0A1628;
            border: none;
            padding: 10px 22px;
            font-size: 11px;
            font-weight: 700;
            letter-spacing: 3px;
            cursor: pointer;
        }
        button:hover { background: #DCBC74; }
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

    <form method="post" action="/play">
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
        <button type="submit">RUN</button>
    </form>

    <div class="meta">
        <a href="/health">/health</a> &nbsp;·&nbsp;
        <a href="/version">/version</a> &nbsp;·&nbsp;
        <a href="https://github.com/EgorKhaklin/chaos-one" target="_blank">repo</a>
    </div>
</body>
</html>
"""


def _scenario_options() -> str:
    return "\n".join(f'<option value="{k.value}">{k.value}</option>' for k in ScenarioKind)


def build_app() -> FastAPI:
    application = FastAPI(
        title="Chaos One Dashboard",
        version=__version__,
        docs_url="/docs",
        redoc_url=None,
    )

    @application.get("/", response_class=HTMLResponse)
    def landing() -> str:
        return _LANDING_HTML.replace("{version}", __version__).replace(
            "{scenario_options}", _scenario_options()
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

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".jsonl",
            delete=False,
            prefix=f"chaos_{kind.value}_seed{seed}_",
        ) as handle:
            log_path = Path(handle.name)

        run_scenario(scenario_obj, log_path=log_path, realtime=False)
        return HTMLResponse(content=render_html_from_path(log_path))

    @application.exception_handler(404)
    def not_found(_request: Any, _exc: Any) -> JSONResponse:
        return JSONResponse(status_code=404, content={"error": "not found"})

    return application


app = build_app()
