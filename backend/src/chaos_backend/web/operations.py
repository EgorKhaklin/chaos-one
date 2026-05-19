"""FastAPI routes for the live operator dashboard.

GET  /ops               navy/gold M2 surfaces (Mode HUD, Decisions
                        Panel, Adversary Mirror). Subscribes to the
                        SSE feed via EventSource on the client.
GET  /ops/stream        text/event-stream of OperationsState changes.
POST /ops/coa/{id}/authorize
POST /ops/coa/{id}/object?reason=...
                        Operator actions; broadcast to all connected
                        clients as SSE events.

The page is intentionally JS-only-where-it-must-be: form-friendly
authorize/object posts back when JS is disabled, with the SSE feed
upgrading the UI when it is.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse

from chaos_backend.operations.state import OperationsEvent, OperationsState


def build_router(state: OperationsState) -> APIRouter:
    router = APIRouter(prefix="/ops", tags=["operations"])

    @router.get("", response_class=HTMLResponse)
    def landing() -> str:
        return _OPS_HTML

    @router.get("/stream")
    async def stream(request: Request) -> StreamingResponse:
        queue = await state.subscribe()

        async def gen() -> AsyncIterator[bytes]:
            try:
                while True:
                    if await request.is_disconnected():
                        return
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=15.0)
                    except TimeoutError:
                        yield b": keep-alive\n\n"
                        continue
                    yield _sse_frame(event)
            finally:
                await state.unsubscribe(queue)

        return StreamingResponse(
            gen(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @router.post("/coa/{coa_id}/authorize")
    async def authorize(coa_id: str) -> JSONResponse:
        ok = await state.authorize_coa(coa_id)
        if not ok:
            raise HTTPException(status_code=404, detail="coa not active")
        return JSONResponse({"authorized": coa_id})

    @router.post("/coa/{coa_id}/object")
    async def object_coa(coa_id: str, reason: str = Form("operator dissent")) -> JSONResponse:
        ok = await state.object_coa(coa_id, reason=reason)
        if not ok:
            raise HTTPException(status_code=404, detail="coa not active")
        return JSONResponse({"objected": coa_id, "reason": reason})

    @router.post("/coa/{coa_id}/authorize-form")
    async def authorize_form(coa_id: str) -> RedirectResponse:
        await state.authorize_coa(coa_id)
        return RedirectResponse(url="/ops", status_code=303)

    @router.post("/coa/{coa_id}/object-form")
    async def object_form(coa_id: str) -> RedirectResponse:
        await state.object_coa(coa_id, reason="operator dissent")
        return RedirectResponse(url="/ops", status_code=303)

    return router


def _sse_frame(event: OperationsEvent) -> bytes:
    payload = {"timestamp_s": event.timestamp_s, **event.payload}
    return f"event: {event.event_type}\ndata: {json.dumps(payload, default=_json_default)}\n\n".encode()


def _json_default(obj: object) -> object:
    as_dict = getattr(obj, "as_dict", None)
    if callable(as_dict):
        return as_dict()
    return str(obj)


_OPS_HTML = r"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Chaos One — Operations</title>
    <style>
        :root {
            --navy: #0A1628;
            --navy-2: #101C30;
            --text: #E8E2D0;
            --gold: #C9A961;
            --gold-dim: rgba(201, 169, 97, 0.40);
            --amber: #DCA03C;
            --red: #DC5050;
            --green: #96DCA0;
        }
        body {
            background: var(--navy);
            color: var(--text);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Inter, sans-serif;
            margin: 0;
            padding: 0;
        }
        .mode-hud {
            position: sticky; top: 0;
            display: flex; align-items: center; gap: 18px;
            padding: 10px 24px;
            background: rgba(10, 22, 40, 0.96);
            border-bottom: 1px solid var(--gold-dim);
            font-family: ui-monospace, "SF Mono", Menlo, monospace;
            font-size: 12px;
            z-index: 10;
        }
        .mode-hud[data-mode="sensor_degraded"]   { border-bottom-color: rgba(220, 160, 60, 0.65); }
        .mode-hud[data-mode="comms_degraded"]    { border-bottom-color: rgba(220, 160, 60, 0.65); }
        .mode-hud[data-mode="advisory_only"]     { border-bottom-color: rgba(220, 160, 60, 0.65); }
        .mode-hud[data-mode="cyber_suspect"]     { border-bottom-color: var(--red); }
        .mode-hud[data-mode="autonomous_fire"]   { border-bottom-color: var(--red); }
        .mode-hud__letter {
            width: 28px; text-align: center;
            color: var(--gold); font-weight: 700; font-size: 16px;
        }
        .mode-hud[data-mode="cyber_suspect"]   .mode-hud__letter,
        .mode-hud[data-mode="autonomous_fire"] .mode-hud__letter { color: var(--red); }
        .mode-hud[data-mode="sensor_degraded"] .mode-hud__letter,
        .mode-hud[data-mode="comms_degraded"]  .mode-hud__letter,
        .mode-hud[data-mode="advisory_only"]   .mode-hud__letter { color: var(--amber); }
        .mode-hud__sep { width: 1px; height: 14px; background: var(--gold-dim); }
        .mode-hud__name { letter-spacing: 3px; font-weight: 700; }
        .mode-hud__metric { color: rgba(232, 226, 208, 0.72); letter-spacing: 1px; }

        .grid {
            display: grid;
            grid-template-columns: 1fr 460px;
            gap: 24px;
            padding: 24px;
        }
        @media (max-width: 1100px) { .grid { grid-template-columns: 1fr; } }

        .panel {
            background: rgba(16, 28, 48, 0.55);
            border-left: 2px solid var(--gold);
            padding: 18px;
        }
        .panel__title {
            color: var(--gold); font-size: 12px; font-weight: 700;
            letter-spacing: 5px; margin-bottom: 14px;
        }

        .coa { padding: 12px 14px; margin-bottom: 12px; background: rgba(10, 22, 40, 0.6); border-left: 2px solid rgba(201, 169, 97, 0.45); }
        .coa--recommended { border-left-color: var(--gold); background: rgba(22, 34, 56, 0.85); }
        .coa__top { display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 6px; }
        .coa__id { color: rgba(232, 226, 208, 0.62); font-family: ui-monospace, monospace; font-size: 11px; letter-spacing: 2px; }
        .coa__badge { background: var(--gold); color: var(--navy); padding: 2px 8px; font-size: 9px; font-weight: 700; letter-spacing: 2px; }
        .coa__headline { font-size: 14px; font-weight: 700; margin: 4px 0 4px 0; }
        .coa__why { color: rgba(232, 226, 208, 0.72); font-size: 11px; margin-bottom: 10px; }
        .coa__metrics { display: flex; gap: 14px; color: rgba(232, 226, 208, 0.78); font-size: 10px; letter-spacing: 1px; font-weight: 700; margin-bottom: 10px; }
        .coa__countdown { height: 4px; background: rgba(232, 226, 208, 0.10); margin-bottom: 10px; }
        .coa__countdown-fill { height: 100%; background: var(--gold); width: 100%; transition: width 0.3s linear; }
        .coa__countdown-fill.low { background: var(--amber); }
        .coa__actions { display: flex; gap: 8px; }
        .coa__btn {
            flex: 1; height: 28px; border: 1px solid var(--gold-dim); background: rgba(232, 226, 208, 0.04);
            color: var(--text); font-size: 10px; font-weight: 700; letter-spacing: 2px; cursor: pointer;
        }
        .coa__btn--primary { background: var(--gold); color: var(--navy); border-color: var(--gold); }
        .coa__btn--primary:hover { background: #DCBC74; }
        .coa__btn--secondary:hover { background: rgba(232, 226, 208, 0.10); }

        .hypothesis { display: flex; align-items: center; gap: 8px; margin-bottom: 6px; }
        .hypothesis__weight { width: 44px; font-weight: 700; }
        .hypothesis__name { flex: 1; color: rgba(232, 226, 208, 0.85); font-size: 11px; }
        .hypothesis__delta { width: 18px; text-align: center; color: var(--gold); }
        .hypothesis__bar { width: 64px; height: 4px; background: rgba(232, 226, 208, 0.10); }
        .hypothesis__bar-fill { height: 100%; background: var(--gold); }
        .sparkline { display: flex; align-items: flex-end; gap: 2px; height: 28px; margin-top: 8px; }
        .sparkline__bar { flex: 1; background: rgba(201, 169, 97, 0.6); min-width: 2px; }

        .empty { color: rgba(232, 226, 208, 0.42); font-size: 11px; letter-spacing: 1px; }

        .calm {
            position: sticky; bottom: 0;
            background: rgba(10, 22, 40, 0.96);
            border-top: 1px solid var(--gold-dim);
            padding: 8px 24px;
            display: flex; align-items: center; gap: 12px;
            font-family: ui-monospace, "SF Mono", Menlo, monospace;
            font-size: 11px;
            overflow: hidden;
        }
        .calm__label { color: var(--gold); font-weight: 700; letter-spacing: 3px; }
        .calm__sep { width: 1px; height: 12px; background: var(--gold-dim); }
        .calm__feed { display: flex; gap: 24px; overflow: hidden; }
        .calm__entry { color: rgba(232, 226, 208, 0.62); white-space: nowrap; }
        .calm__entry--mode { color: var(--amber); }
        .calm__entry--auth { color: var(--green); }
        .calm__entry--obj  { color: rgba(232, 226, 208, 0.85); }
        .calm__entry--exp  { color: rgba(232, 226, 208, 0.45); }
        .calm__entry--new  { color: var(--gold); }

        .footer { padding: 16px 24px 56px 24px; color: rgba(232, 226, 208, 0.32); font-size: 10px; letter-spacing: 1px; }
        a { color: var(--gold); text-decoration: none; }
        a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <div id="mode-hud" class="mode-hud" data-mode="nominal">
        <span class="mode-hud__letter" id="mode-letter">A</span>
        <span class="mode-hud__name" id="mode-name">NOMINAL</span>
        <span class="mode-hud__sep"></span>
        <span class="mode-hud__metric">ROE-2</span>
        <span class="mode-hud__sep"></span>
        <span class="mode-hud__metric" id="cost-metric">COST IMPOSITION +0%</span>
        <span class="mode-hud__sep"></span>
        <span class="mode-hud__metric" id="subscriber-metric">live</span>
    </div>

    <div class="grid">
        <div class="panel">
            <div class="panel__title">DECISIONS</div>
            <div id="coa-stack"></div>
            <div class="empty" id="coa-empty">awaiting first proposal...</div>
        </div>

        <div class="panel">
            <div class="panel__title">ADVERSARY MIRROR</div>
            <div id="hypothesis-stack"></div>
            <div class="sparkline" id="sparkline"></div>
        </div>
    </div>

    <div class="footer">
        <a href="/">/</a> &nbsp;·&nbsp;
        <a href="/engagements">/engagements</a> &nbsp;·&nbsp;
        <a href="/health">/health</a> &nbsp;·&nbsp;
        <a href="/docs">/docs</a>
    </div>

    <div class="calm">
        <span class="calm__label">LOG</span>
        <span class="calm__sep"></span>
        <div class="calm__feed" id="calm-feed"></div>
    </div>

    <script>
    (() => {
        const modeHud = document.getElementById('mode-hud');
        const modeLetter = document.getElementById('mode-letter');
        const modeName = document.getElementById('mode-name');
        const costMetric = document.getElementById('cost-metric');
        const coaStack = document.getElementById('coa-stack');
        const coaEmpty = document.getElementById('coa-empty');
        const hypothesisStack = document.getElementById('hypothesis-stack');
        const sparkline = document.getElementById('sparkline');

        const modeMeta = {
            nominal:           { letter: 'A', name: 'NOMINAL' },
            sensor_degraded:   { letter: 'B', name: 'SENSOR DEGRADED' },
            comms_degraded:    { letter: 'C', name: 'COMMS DEGRADED' },
            cyber_suspect:     { letter: 'D', name: 'CYBER-SUSPECT' },
            advisory_only:     { letter: 'E', name: 'ADVISORY ONLY' },
            autonomous_fire:   { letter: 'F', name: 'AUTONOMOUS FIRE' },
        };

        const escapeHtml = s => String(s).replace(/[&<>"']/g, c => ({
            '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
        })[c]);

        const coaMap = new Map();
        const costHistory = [];

        function renderMode(mode) {
            modeHud.dataset.mode = mode;
            const meta = modeMeta[mode] || { letter: '?', name: mode };
            modeLetter.textContent = meta.letter;
            modeName.textContent = meta.name;
        }

        function renderCoaCard(coa) {
            const recommended = coa.is_recommended;
            const fraction = coa.countdown_seconds_initial > 0
                ? Math.max(0, Math.min(1, coa.countdown_seconds_remaining / coa.countdown_seconds_initial))
                : 0;
            const low = fraction < 0.25;
            return `
                <div class="coa ${recommended ? 'coa--recommended' : ''}" data-coa-id="${escapeHtml(coa.id)}">
                    <div class="coa__top">
                        <span class="coa__id">${escapeHtml(coa.id)}</span>
                        ${recommended ? '<span class="coa__badge">RECOMMENDED</span>' : ''}
                    </div>
                    <div class="coa__headline">${escapeHtml(coa.headline)}</div>
                    <div class="coa__why">${escapeHtml(coa.why)}</div>
                    <div class="coa__metrics">
                        <span>LEAK ${coa.expected_leakage.toFixed(2)} ±${(coa.expected_leakage_band/2).toFixed(2)}</span>
                        <span>${escapeHtml(coa.escalation)}</span>
                        <span>${escapeHtml(coa.releasability)}</span>
                    </div>
                    <div class="coa__countdown">
                        <div class="coa__countdown-fill ${low ? 'low' : ''}" style="width: ${(fraction*100).toFixed(0)}%"></div>
                    </div>
                    <div class="coa__actions">
                        <button class="coa__btn coa__btn--primary" data-act="authorize" data-id="${escapeHtml(coa.id)}">AUTHORIZE</button>
                        <button class="coa__btn coa__btn--secondary" data-act="object" data-id="${escapeHtml(coa.id)}">OBJECT</button>
                    </div>
                </div>
            `;
        }

        function rerenderCoas() {
            coaEmpty.style.display = coaMap.size === 0 ? '' : 'none';
            coaStack.innerHTML = Array.from(coaMap.values()).map(renderCoaCard).join('');
        }

        function renderAdversary(payload) {
            const hypotheses = payload.hypotheses || [];
            hypothesisStack.innerHTML = hypotheses.map(h => {
                const arrow = Math.abs(h.delta_30s) < 0.005 ? '→' : (h.delta_30s > 0 ? '↑' : '↓');
                return `
                    <div class="hypothesis">
                        <span class="hypothesis__weight">${Math.round(h.weight*100)}%</span>
                        <span class="hypothesis__name">${escapeHtml(h.display_name)}</span>
                        <span class="hypothesis__delta">${arrow}</span>
                        <div class="hypothesis__bar"><div class="hypothesis__bar-fill" style="width: ${Math.round(h.weight*100)}%"></div></div>
                    </div>
                `;
            }).join('');

            const cost = payload.cost_imposition_index ?? 1.0;
            const pct = Math.round((cost - 1.0) * 100);
            costMetric.textContent = `COST IMPOSITION ${pct >= 0 ? '+' : ''}${pct}%`;

            costHistory.push(cost);
            if (costHistory.length > 24) costHistory.shift();
            const min = Math.min(...costHistory), max = Math.max(...costHistory);
            const range = Math.max(0.05, max - min);
            sparkline.innerHTML = costHistory.map(v => {
                const h = 15 + 85 * ((v - min) / range);
                return `<div class="sparkline__bar" style="height: ${h.toFixed(0)}%"></div>`;
            }).join('');
        }

        function applySnapshot(payload) {
            renderMode(payload.mode);
            coaMap.clear();
            for (const coa of payload.coas) coaMap.set(coa.id, coa);
            rerenderCoas();
            renderAdversary(payload.adversary);
        }

        function tickCountdowns(remaining) {
            for (const [id, secs] of Object.entries(remaining)) {
                const coa = coaMap.get(id);
                if (coa) coa.countdown_seconds_remaining = secs;
            }
            rerenderCoas();
        }

        const calmFeed = document.getElementById('calm-feed');
        const CALM_MAX = 12;

        function calmAppend(text, cls) {
            const entry = document.createElement('span');
            entry.className = `calm__entry ${cls || ''}`;
            const stamp = new Date().toISOString().substring(11, 19);
            entry.textContent = `${stamp} · ${text}`;
            calmFeed.appendChild(entry);
            while (calmFeed.children.length > CALM_MAX) {
                calmFeed.removeChild(calmFeed.firstChild);
            }
        }

        const source = new EventSource('/ops/stream');

        source.addEventListener('snapshot', e => applySnapshot(JSON.parse(e.data)));
        source.addEventListener('mode_changed', e => {
            const data = JSON.parse(e.data);
            renderMode(data.current);
            calmAppend(`mode ${data.previous} → ${data.current}`, 'calm__entry--mode');
        });
        source.addEventListener('coa_proposed', e => {
            const coa = JSON.parse(e.data).coa;
            coaMap.set(coa.id, coa);
            rerenderCoas();
            const tag = coa.is_recommended ? 'recommended' : 'alternative';
            calmAppend(`coa proposed ${coa.id} (${tag})`, 'calm__entry--new');
        });
        source.addEventListener('coa_authorized', e => {
            const data = JSON.parse(e.data);
            coaMap.delete(data.id);
            rerenderCoas();
            calmAppend(`coa authorized ${data.id} via ${data.source || 'operator'}`, 'calm__entry--auth');
        });
        source.addEventListener('coa_objected',  e => {
            const data = JSON.parse(e.data);
            coaMap.delete(data.id);
            rerenderCoas();
            calmAppend(`coa objected ${data.id} — ${data.reason || 'no reason'}`, 'calm__entry--obj');
        });
        source.addEventListener('coa_expired',   e => {
            const data = JSON.parse(e.data);
            coaMap.delete(data.id);
            rerenderCoas();
            const note = data.auto_authorized ? 'auto-authorized on expiry' : 'expired without action';
            calmAppend(`coa expired ${data.id} — ${note}`, 'calm__entry--exp');
        });
        source.addEventListener('coa_tick',      e => tickCountdowns(JSON.parse(e.data).remaining));
        source.addEventListener('adversary_updated', e => renderAdversary(JSON.parse(e.data)));

        coaStack.addEventListener('click', async (e) => {
            const button = e.target.closest('button');
            if (!button) return;
            const id = button.dataset.id;
            const act = button.dataset.act;
            if (!id || !act) return;
            const url = act === 'authorize'
                ? `/ops/coa/${encodeURIComponent(id)}/authorize`
                : `/ops/coa/${encodeURIComponent(id)}/object`;
            const body = act === 'object' ? new URLSearchParams({reason: 'operator dissent'}) : null;
            try {
                await fetch(url, {
                    method: 'POST',
                    headers: body ? {'Content-Type': 'application/x-www-form-urlencoded'} : undefined,
                    body,
                });
            } catch (err) {
                console.error('action failed', err);
            }
        });
    })();
    </script>
</body>
</html>
"""
