"""Battlespace visualization — a Canvas-rendered, self-contained scene.

Geometry is computed in the browser with explicit 4×4 view/projection
matrices: worldPos -> view * worldPos -> projection * viewPos, then
homogeneous-divide and map normalized device coordinates to CSS pixels.
Trails are interpolated with a Catmull-Rom spline so the rendered curve
is C¹-continuous regardless of the sampling rate, and every line stroke
is pixel-snapped (0.5-offset) for crisp single-pixel lines on retina.

The page is self-contained — no external assets — so iteration cycles
don't depend on Unity rebuilds and the scene renders deterministically
in any browser. A small harness (`window.__chaos`) lets an automated
browser pin the demo to a chosen frame for reproducible verification.
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from chaos_backend import __version__


_BATTLESPACE_HTML = r"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Chaos One — Battlespace</title>
    <style>
        :root {
            --gold:        #C9A961;
            --gold-dim:    #8E7843;
            --bone:        #E8E2D0;
            --bone-dim:    rgba(232, 226, 208, 0.55);
            --bone-dimmer: rgba(232, 226, 208, 0.30);
            --bg-deep:     #04091A;
            --bg-mid:      #0A1628;
            --bg-panel:    rgba(10, 22, 40, 0.84);
            --rule:        rgba(201, 169, 97, 0.32);
            --amber:       #DC9A3C;
            --crimson:     #DC5050;
            --mint:        #96DCA0;

            /* Universal timings — fast snappy reveals, no slow tweens. */
            --t-fast:      90ms cubic-bezier(0.22, 1, 0.36, 1);
            --t-bar:       0ms linear;
        }
        * { box-sizing: border-box; }
        html, body {
            margin: 0; padding: 0;
            width: 100%; height: 100%;
            background: var(--bg-deep);
            color: var(--bone);
            font-family: -apple-system, "SF Pro Display", BlinkMacSystemFont, "Segoe UI", Inter, sans-serif;
            overflow: hidden;
            -webkit-font-smoothing: antialiased;
        }
        #stage {
            position: fixed; inset: 0;
            display: block;
            width: 100vw; height: 100vh;
        }

        /* ─────────── overlay scaffolding ─────────── */
        .overlay { position: fixed; pointer-events: none; }

        /* ─── Mode HUD (top strip) ─── */
        .mode-hud {
            top: 0; left: 0; right: 0;
            height: 38px;
            display: flex; align-items: center;
            padding: 0 24px;
            background: rgba(8, 18, 32, 0.94);
            border-bottom: 1px solid var(--rule);
            font-size: 11px;
            letter-spacing: 2.5px;
            backdrop-filter: blur(6px);
        }
        .mode-hud__letter {
            color: var(--gold);
            font-weight: 800;
            font-size: 16px;
            width: 24px;
            transition: color var(--t-fast);
        }
        .mode-hud__name {
            color: var(--bone);
            font-weight: 700;
            margin-right: 18px;
            transition: color var(--t-fast);
        }
        .mode-hud__cell {
            color: var(--bone-dim);
            font-weight: 700;
            margin-right: 18px;
        }
        .mode-hud__sep {
            width: 1px; height: 14px;
            background: var(--rule);
            margin-right: 18px;
        }
        .mode-hud__mag {
            margin-left: auto;
            color: var(--bone-dim);
            font-weight: 700;
            font-variant-numeric: tabular-nums;
        }

        /* ─── Classification banner ─── */
        .classbar {
            top: 38px; left: 0; right: 0;
            height: 18px;
            display: flex; align-items: center; justify-content: center;
            color: rgba(150, 220, 160, 0.85);
            background: rgba(8, 18, 30, 0.55);
            font-size: 9px;
            letter-spacing: 4px;
            font-weight: 800;
            border-bottom: 1px solid rgba(150, 220, 160, 0.18);
        }

        /* ─── Decisions Panel (right) ─── */
        .decisions {
            top: 70px; right: 24px;
            width: 360px;
            padding: 16px 16px 14px;
            background: var(--bg-panel);
            border-left: 2px solid rgba(201, 169, 97, 0.65);
            border-top: 1px solid var(--rule);
            border-right: 1px solid var(--rule);
            border-bottom: 1px solid var(--rule);
            pointer-events: auto;
            backdrop-filter: blur(8px);
        }
        .decisions__head {
            display: flex; align-items: center; justify-content: space-between;
            margin-bottom: 10px;
        }
        .decisions__title {
            color: var(--gold);
            font-size: 11px;
            letter-spacing: 5px;
            font-weight: 800;
        }
        .decisions__rule {
            height: 1px;
            background: var(--rule);
            margin-bottom: 12px;
        }

        /* AUTO-ENGAGE toggle — switches between operator-in-loop and
           ROE weapons-free auto-authorization. */
        .auto-toggle {
            display: flex; align-items: center; gap: 8px;
            padding: 3px 8px 3px 10px;
            background: rgba(232, 226, 208, 0.04);
            border: 1px solid rgba(232, 226, 208, 0.20);
            border-radius: 2px;
            cursor: pointer;
            user-select: none;
            color: rgba(232, 226, 208, 0.62);
            font-size: 9px;
            letter-spacing: 2.5px;
            font-weight: 800;
            transition: background var(--t-fast), border-color var(--t-fast), color var(--t-fast);
        }
        .auto-toggle:hover {
            background: rgba(232, 226, 208, 0.08);
            border-color: rgba(232, 226, 208, 0.30);
        }
        .auto-toggle__dot {
            width: 8px; height: 8px; border-radius: 50%;
            background: rgba(232, 226, 208, 0.32);
            box-shadow: 0 0 0 0 rgba(150, 220, 160, 0);
            transition: background var(--t-fast), box-shadow 240ms ease-out;
        }
        .auto-toggle--on {
            background: rgba(150, 220, 160, 0.10);
            border-color: rgba(150, 220, 160, 0.55);
            color: rgb(150, 220, 160);
        }
        .auto-toggle--on .auto-toggle__dot {
            background: rgb(150, 220, 160);
            box-shadow: 0 0 0 4px rgba(150, 220, 160, 0.20);
        }
        .auto-toggle__hint {
            color: rgba(232, 226, 208, 0.32);
            letter-spacing: 1px;
            font-weight: 700;
            margin-left: 2px;
        }
        .coa {
            padding: 12px;
            margin-bottom: 10px;
            background: rgba(16, 28, 48, 0.92);
            border-left: 2px solid rgba(201, 169, 97, 0.45);
            border-top: 1px solid rgba(232, 226, 208, 0.08);
            border-right: 1px solid rgba(232, 226, 208, 0.08);
            border-bottom: 1px solid rgba(232, 226, 208, 0.08);
            opacity: 0;
            transform: translateY(2px);
            animation: coa-in 110ms cubic-bezier(0.22, 1, 0.36, 1) forwards;
        }
        .coa:nth-child(2) { animation-delay: 25ms; }
        .coa:nth-child(3) { animation-delay: 50ms; }
        @keyframes coa-in {
            to { opacity: 1; transform: translateY(0); }
        }
        .coa--rec {
            border-left-color: var(--gold);
            background: rgba(22, 34, 56, 0.96);
        }
        .coa--authorized {
            border-left-color: rgb(150, 220, 160);
            background: rgba(16, 38, 30, 0.96);
        }
        .coa__badge--ok {
            background: rgb(150, 220, 160);
            color: var(--bg-mid);
        }
        .coa__status {
            margin-top: 4px;
            padding: 8px 10px;
            text-align: center;
            color: rgb(150, 220, 160);
            background: rgba(150, 220, 160, 0.08);
            border: 1px solid rgba(150, 220, 160, 0.32);
            font-size: 10px;
            font-weight: 800;
            letter-spacing: 2.5px;
        }
        .coa__top {
            display: flex; align-items: center; justify-content: space-between;
            margin-bottom: 6px;
        }
        .coa__id {
            color: var(--bone-dim);
            font-size: 10px;
            letter-spacing: 3px;
            font-weight: 700;
        }
        .coa__badge {
            background: var(--gold);
            color: var(--bg-mid);
            font-size: 9px;
            letter-spacing: 2px;
            font-weight: 800;
            padding: 2px 7px;
        }
        .coa__head {
            color: var(--bone);
            font-size: 13px;
            font-weight: 700;
            margin-bottom: 4px;
        }
        .coa__why {
            color: rgba(232, 226, 208, 0.72);
            font-size: 10.5px;
            line-height: 1.45;
            margin-bottom: 9px;
        }
        .coa__metrics {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 4px 12px;
            margin-bottom: 9px;
            font-size: 9.5px;
            letter-spacing: 1px;
            font-weight: 700;
            color: rgba(232, 226, 208, 0.78);
        }
        .coa__bar {
            height: 3px;
            background: rgba(232, 226, 208, 0.10);
            margin-bottom: 9px;
        }
        .coa__bar-fill {
            height: 100%;
            background: var(--gold);
            transition: width var(--t-bar);
            will-change: width;
        }
        .coa__btns {
            display: flex; gap: 6px;
        }
        .coa__btn {
            flex: 1;
            padding: 7px;
            font-size: 10px;
            letter-spacing: 2px;
            font-weight: 800;
            border: none;
            cursor: pointer;
            transition: background var(--t-fast), border-color var(--t-fast);
        }
        .coa__btn--p {
            background: var(--gold);
            color: var(--bg-mid);
        }
        .coa__btn--p:hover { background: rgb(220, 188, 116); }
        .coa__btn--s {
            background: rgba(232, 226, 208, 0.06);
            color: rgba(232, 226, 208, 0.85);
            border: 1px solid rgba(232, 226, 208, 0.18);
        }
        .coa__btn--s:hover { background: rgba(232, 226, 208, 0.12); }
        .decisions__hint {
            margin-top: 8px;
            padding-top: 8px;
            border-top: 1px solid rgba(201, 169, 97, 0.18);
            color: rgba(232, 226, 208, 0.42);
            font-size: 9px;
            letter-spacing: 1px;
        }
        .decisions__empty {
            color: var(--bone-dim);
            font-size: 11px;
            letter-spacing: 2px;
            padding: 22px 4px;
            text-align: center;
        }

        /* ─── Adversary Mirror (bottom-left) ─── */
        .adv {
            bottom: 64px; left: 24px;
            width: 360px;
            padding: 14px 16px;
            background: var(--bg-panel);
            border-left: 2px solid rgba(201, 169, 97, 0.55);
            border-top: 1px solid var(--rule);
            border-right: 1px solid var(--rule);
            border-bottom: 1px solid var(--rule);
            backdrop-filter: blur(8px);
        }
        .adv__title {
            color: var(--gold);
            font-size: 11px;
            letter-spacing: 4.5px;
            font-weight: 800;
            margin-bottom: 8px;
        }
        .adv__rule { height: 1px; background: var(--rule); margin-bottom: 12px; }
        .hyp {
            display: grid;
            grid-template-columns: 40px 1fr 20px 64px;
            align-items: center;
            margin-bottom: 7px;
            font-size: 10px;
            letter-spacing: 0.5px;
        }
        .hyp__w {
            color: var(--bone);
            font-size: 12px;
            font-weight: 800;
            font-variant-numeric: tabular-nums;
        }
        .hyp__n {
            color: rgba(232, 226, 208, 0.82);
            margin-left: 4px;
        }
        .hyp__d {
            color: rgba(201, 169, 97, 0.85);
            text-align: center;
            font-size: 12px;
        }
        .hyp__bar {
            height: 4px;
            background: rgba(232, 226, 208, 0.10);
        }
        .hyp__bar-fill {
            height: 100%;
            background: var(--gold);
            transition: width 110ms cubic-bezier(0.22, 1, 0.36, 1);
            will-change: width;
        }
        .cost {
            margin-top: 10px;
            padding-top: 10px;
            border-top: 1px solid rgba(201, 169, 97, 0.22);
        }
        .cost__lbl {
            color: rgba(232, 226, 208, 0.78);
            font-size: 9.5px;
            letter-spacing: 2px;
            font-weight: 700;
            margin-bottom: 6px;
        }
        .cost__spark {
            display: flex; align-items: flex-end; gap: 2px;
            height: 30px;
        }
        .cost__spark > div {
            flex: 1;
            background: rgba(201, 169, 97, 0.65);
            min-width: 2px;
            transition: height var(--t-fast);
        }

        /* ─── Calm Channel (bottom strip) ─── */
        .calm {
            bottom: 0; left: 0; right: 0;
            height: 32px;
            display: flex; align-items: center;
            padding: 0 24px;
            background: rgba(8, 18, 32, 0.94);
            border-top: 1px solid var(--rule);
            font-size: 10px;
            letter-spacing: 0.5px;
            overflow: hidden;
            backdrop-filter: blur(6px);
        }
        .calm__label {
            color: var(--gold);
            font-size: 9px;
            letter-spacing: 3px;
            font-weight: 800;
            margin-right: 14px;
        }
        .calm__sep {
            width: 1px; height: 14px;
            background: var(--rule);
            margin-right: 14px;
        }
        .calm__list {
            display: flex; gap: 28px;
            color: rgba(232, 226, 208, 0.62);
            white-space: nowrap;
            overflow: hidden;
            mask-image: linear-gradient(to right, #000 88%, transparent);
        }
        .calm__list em {
            font-style: normal;
            color: rgba(232, 226, 208, 0.88);
            font-weight: 600;
        }

        /* ─── Track callouts (positioned via JS) ─── */
        .callouts {
            inset: 0;
            pointer-events: none;
        }
        .callout {
            position: absolute;
            font-size: 10px;
            letter-spacing: 1px;
            color: var(--bone);
            transform: translate(8px, -50%);
            background: rgba(10, 22, 40, 0.78);
            border: 1px solid rgba(201, 169, 97, 0.45);
            border-left-width: 2px;
            padding: 4px 8px 4px 8px;
            font-variant-numeric: tabular-nums;
            transition: left var(--t-fast), top var(--t-fast);
            will-change: left, top;
        }
        .callout__id {
            color: var(--gold);
            font-weight: 800;
            letter-spacing: 1.5px;
            font-size: 9.5px;
            display: block;
            margin-bottom: 1px;
        }

        /* ─── Stats block (lower-right) ─── */
        .stats {
            bottom: 110px; right: 24px;
            width: 280px;
            padding: 12px 14px;
            background: var(--bg-panel);
            border-left: 2px solid rgba(150, 220, 160, 0.55);
            border-top: 1px solid var(--rule);
            border-right: 1px solid var(--rule);
            border-bottom: 1px solid var(--rule);
            font-size: 10px;
            letter-spacing: 1px;
            backdrop-filter: blur(8px);
        }
        .stats__title {
            color: rgb(150, 220, 160);
            font-size: 10px;
            letter-spacing: 4px;
            font-weight: 800;
            margin-bottom: 6px;
        }
        .stats__rule {
            height: 1px;
            background: rgba(150, 220, 160, 0.30);
            margin-bottom: 10px;
        }
        .stats__row {
            display: grid;
            grid-template-columns: 110px 1fr;
            margin-bottom: 5px;
            font-variant-numeric: tabular-nums;
        }
        .stats__k {
            color: rgba(232, 226, 208, 0.55);
            font-weight: 700;
            letter-spacing: 1.5px;
        }
        .stats__v {
            color: var(--bone);
            font-weight: 700;
            text-align: right;
            letter-spacing: 0.5px;
            transition: color var(--t-fast);
        }
        .stats__v--ok   { color: rgb(150, 220, 160); }
        .stats__v--warn { color: rgb(220, 160, 60); }

        /* ─── Weapons bay (above calm channel) ─── */
        .bay {
            bottom: 32px; left: 50%;
            transform: translateX(-50%);
            display: flex; gap: 10px;
            padding: 8px 14px;
            background: rgba(8, 18, 32, 0.86);
            border-top: 1px solid var(--rule);
            border-left: 1px solid var(--rule);
            border-right: 1px solid var(--rule);
            backdrop-filter: blur(6px);
        }
        .bay__slot {
            min-width: 96px;
            padding: 4px 8px 6px;
            border-left: 2px solid var(--bone-dimmer);
        }
        .bay__slot--depleted { border-left-color: rgba(220, 80, 80, 0.65); }
        .bay__slot--firing   { border-left-color: var(--amber); }
        .bay__row {
            display: flex; justify-content: space-between; align-items: baseline;
            font-size: 9px;
            letter-spacing: 1.5px;
            font-variant-numeric: tabular-nums;
        }
        .bay__id {
            color: var(--gold);
            font-weight: 800;
        }
        .bay__count {
            color: var(--bone);
            font-weight: 800;
            font-size: 12px;
            transition: color var(--t-fast);
        }
        .bay__bar {
            height: 3px;
            margin-top: 4px;
            background: rgba(232, 226, 208, 0.10);
        }
        .bay__bar-fill {
            height: 100%;
            background: var(--gold);
            transition: width var(--t-fast);
        }

        /* ─── Watermark ─── */
        .wm {
            bottom: 44px; right: 320px;
            color: rgba(201, 169, 97, 0.32);
            font-size: 9px;
            letter-spacing: 4px;
            font-weight: 700;
            text-align: right;
        }
        .wm__big {
            color: rgba(201, 169, 97, 0.45);
            font-size: 11px;
            letter-spacing: 6px;
            margin-bottom: 2px;
        }
    </style>
</head>
<body>
    <canvas id="stage"></canvas>

    <div class="callouts overlay" id="callouts"></div>

    <div class="overlay mode-hud" id="modeHud">
        <span class="mode-hud__letter" id="modeLetter">A</span>
        <span class="mode-hud__name" id="modeName">NOMINAL</span>
        <span class="mode-hud__sep"></span>
        <span class="mode-hud__cell">ROE-2</span>
        <span class="mode-hud__sep"></span>
        <span class="mode-hud__cell">COMMS 98%</span>
        <span class="mode-hud__sep"></span>
        <span class="mode-hud__cell">PQC-HYBRID</span>
        <span class="mode-hud__mag" id="modeMag">MAG 22 NGI / 48 SM-3 / 320 PAC-3 / HEL 1.2MJ</span>
    </div>

    <div class="overlay classbar">UNCLASSIFIED // DEMO // FOR EVALUATION</div>

    <div class="overlay decisions">
        <div class="decisions__head">
            <span class="decisions__title">DECISIONS</span>
            <button class="auto-toggle" id="autoToggle" type="button" title="Toggle auto-engage (T)">
                <span class="auto-toggle__dot"></span>
                <span class="auto-toggle__label">AUTO</span>
                <span class="auto-toggle__hint">T</span>
            </button>
        </div>
        <div class="decisions__rule"></div>
        <div id="coaStack"></div>
        <div class="decisions__hint">ENTER AUTHORIZE · O OBJECT · T AUTO-ENGAGE</div>
    </div>

    <div class="overlay adv">
        <div class="adv__title">ADVERSARY MIRROR</div>
        <div class="adv__rule"></div>
        <div id="hypStack"></div>
        <div class="cost">
            <div class="cost__lbl" id="costLabel">COST IMPOSITION +13% ADV</div>
            <div class="cost__spark" id="costSpark"></div>
        </div>
    </div>

    <div class="overlay bay">
        <div class="bay__slot" data-eff="NGI">
            <div class="bay__row"><span class="bay__id">NGI</span><span class="bay__count">22</span></div>
            <div class="bay__bar"><div class="bay__bar-fill" style="width:88%"></div></div>
        </div>
        <div class="bay__slot" data-eff="SM-3">
            <div class="bay__row"><span class="bay__id">SM-3</span><span class="bay__count">48</span></div>
            <div class="bay__bar"><div class="bay__bar-fill" style="width:96%"></div></div>
        </div>
        <div class="bay__slot" data-eff="PAC-3">
            <div class="bay__row"><span class="bay__id">PAC-3</span><span class="bay__count">320</span></div>
            <div class="bay__bar"><div class="bay__bar-fill" style="width:100%"></div></div>
        </div>
        <div class="bay__slot" data-eff="HEL">
            <div class="bay__row"><span class="bay__id">HEL</span><span class="bay__count">1.2 MJ</span></div>
            <div class="bay__bar"><div class="bay__bar-fill" style="width:80%"></div></div>
        </div>
    </div>

    <div class="overlay calm">
        <span class="calm__label">LOG</span>
        <span class="calm__sep"></span>
        <div class="calm__list" id="calmList"></div>
    </div>

    <div class="overlay stats">
        <div class="stats__title">ENGAGEMENT STATE</div>
        <div class="stats__rule"></div>
        <div class="stats__row"><span class="stats__k">ACTIVE TRACKS</span><span class="stats__v" id="stTracks">3</span></div>
        <div class="stats__row"><span class="stats__k">UNDER ENG.</span><span class="stats__v" id="stEng">0 / 3</span></div>
        <div class="stats__row"><span class="stats__k">PRIMARY TTI</span><span class="stats__v" id="stTTI">—</span></div>
        <div class="stats__row"><span class="stats__k">EXP. Pk (SHOT)</span><span class="stats__v stats__v--ok" id="stPk">0.93</span></div>
        <div class="stats__row"><span class="stats__k">EXP. LEAKAGE</span><span class="stats__v stats__v--ok" id="stLeak">5%</span></div>
        <div class="stats__row"><span class="stats__k">ROE</span><span class="stats__v" id="stRoe">ROE-2 (RESTR.)</span></div>
        <div class="stats__row"><span class="stats__k">PQC POSTURE</span><span class="stats__v stats__v--ok" id="stPqc">HYBRID</span></div>
    </div>

    <div class="overlay wm">
        <div class="wm__big">CHAOS ONE</div>
        <div>BATTLESPACE · v__VERSION__</div>
    </div>

<script>
(() => {
'use strict';

// ═════════════════════════════════════════════════════════════════════
//   MATH LAYER
//   Right-handed coordinate system: +X east, +Y up, +Z north.
//   All distances are metres. All angles are radians.
// ═════════════════════════════════════════════════════════════════════
const V3 = {
    sub:   (a, b) => [a[0]-b[0], a[1]-b[1], a[2]-b[2]],
    add:   (a, b) => [a[0]+b[0], a[1]+b[1], a[2]+b[2]],
    scale: (a, s) => [a[0]*s, a[1]*s, a[2]*s],
    dot:   (a, b) => a[0]*b[0] + a[1]*b[1] + a[2]*b[2],
    cross: (a, b) => [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]],
    len:   (a) => Math.hypot(a[0], a[1], a[2]),
    norm:  (a) => {
        const L = Math.hypot(a[0], a[1], a[2]);
        return L > 0 ? [a[0]/L, a[1]/L, a[2]/L] : [0, 0, 0];
    },
    lerp:  (a, b, t) => [a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t, a[2]+(b[2]-a[2])*t],
    // Quadratic Bezier: B(t) = (1-t)²P0 + 2(1-t)t P1 + t² P2
    bezQ: (p0, p1, p2, t) => {
        const u = 1 - t;
        return [
            u*u*p0[0] + 2*u*t*p1[0] + t*t*p2[0],
            u*u*p0[1] + 2*u*t*p1[1] + t*t*p2[1],
            u*u*p0[2] + 2*u*t*p1[2] + t*t*p2[2],
        ];
    },
    // Catmull-Rom interpolation between p1 and p2, with p0/p3 as
    // neighbours. t in [0, 1]. Yields C¹-continuous curves through the
    // control points.
    catmull: (p0, p1, p2, p3, t) => {
        const t2 = t * t, t3 = t2 * t;
        const a = -0.5 * t3 + t2 - 0.5 * t;
        const b =  1.5 * t3 - 2.5 * t2 + 1.0;
        const c = -1.5 * t3 + 2.0 * t2 + 0.5 * t;
        const d =  0.5 * t3 - 0.5 * t2;
        return [
            a*p0[0] + b*p1[0] + c*p2[0] + d*p3[0],
            a*p0[1] + b*p1[1] + c*p2[1] + d*p3[1],
            a*p0[2] + b*p1[2] + c*p2[2] + d*p3[2],
        ];
    },
};

// 4×4 matrix. Stored as a 16-element Float32Array in column-major form
// (m[col*4 + row]) so it matches the conventional OpenGL / WebGPU
// layout. Multiplication is C = A * B.
const M4 = {
    create:   () => new Float32Array(16),
    identity: () => { const m = new Float32Array(16); m[0]=m[5]=m[10]=m[15]=1; return m; },

    multiply: (a, b) => {
        const o = new Float32Array(16);
        for (let r = 0; r < 4; r++) {
            for (let c = 0; c < 4; c++) {
                let s = 0;
                for (let k = 0; k < 4; k++) s += a[k*4 + r] * b[c*4 + k];
                o[c*4 + r] = s;
            }
        }
        return o;
    },

    // Right-handed perspective: maps view-space points with negative z
    // (in front of the camera) into normalized device coordinates in
    // [-1, 1]^3. fovY is vertical field of view in radians.
    perspective: (fovY, aspect, near, far) => {
        const f = 1 / Math.tan(fovY * 0.5);
        const nf = 1 / (near - far);
        const m = new Float32Array(16);
        m[0] = f / aspect;
        m[5] = f;
        m[10] = (far + near) * nf;
        m[11] = -1;
        m[14] = 2 * far * near * nf;
        return m;
    },

    // Right-handed lookAt: places the camera at `eye` looking at
    // `target` with `up` as the world-up reference. The returned matrix
    // transforms world coordinates into view (camera-local) coordinates
    // where -Z is forward.
    lookAt: (eye, target, up) => {
        const f = V3.norm(V3.sub(target, eye));    // forward (camera looks down -z in view, +z in world to target)
        const s = V3.norm(V3.cross(f, up));         // side
        const u = V3.cross(s, f);                   // recomputed up
        const m = new Float32Array(16);
        m[0]  =  s[0]; m[4]  =  s[1]; m[8]   =  s[2]; m[12] = -V3.dot(s, eye);
        m[1]  =  u[0]; m[5]  =  u[1]; m[9]   =  u[2]; m[13] = -V3.dot(u, eye);
        m[2]  = -f[0]; m[6]  = -f[1]; m[10]  = -f[2]; m[14] =  V3.dot(f, eye);
        m[3]  =   0;   m[7]  =   0;   m[11]  =   0;   m[15] =  1;
        return m;
    },

    // Apply a 4×4 to a vec3 with implicit w = 1. Returns
    //   { x, y, z, w }  in clip-space coordinates (not yet divided by w).
    apply: (m, v) => ({
        x: m[0]*v[0] + m[4]*v[1] + m[8]*v[2]  + m[12],
        y: m[1]*v[0] + m[5]*v[1] + m[9]*v[2]  + m[13],
        z: m[2]*v[0] + m[6]*v[1] + m[10]*v[2] + m[14],
        w: m[3]*v[0] + m[7]*v[1] + m[11]*v[2] + m[15],
    }),
};

// ═════════════════════════════════════════════════════════════════════
//   CAMERA + PROJECTOR
// ═════════════════════════════════════════════════════════════════════
class Camera {
    constructor() {
        this.pivot     = [0, 0, 0];
        this.radius    = 14_500;
        this.height    = 6_000;
        this.lookAtY   = 1_400;
        this.angle     = -2.05;
        this.angleRate = 0.018;
        this.fovDeg    = 40;
    }
    eye() {
        return [
            Math.sin(this.angle) * this.radius,
            this.height,
            Math.cos(this.angle) * this.radius,
        ];
    }
    target() { return [this.pivot[0], this.pivot[1] + this.lookAtY, this.pivot[2]]; }
    tick(dt) { this.angle += this.angleRate * dt; }
}

class Projector {
    constructor(camera, width, height) {
        this.cam = camera;
        this.resize(width, height);
    }
    resize(width, height) {
        this.w = width;
        this.h = height;
        this._build();
    }
    _build() {
        const fovY = this.cam.fovDeg * Math.PI / 180;
        const aspect = this.w / this.h;
        const proj = M4.perspective(fovY, aspect, 10, 200_000);
        const view = M4.lookAt(this.cam.eye(), this.cam.target(), [0, 1, 0]);
        this.viewProj = M4.multiply(proj, view);
    }
    tick() { this._build(); }
    // Project world → CSS pixels. Returns null for points behind the
    // near plane (clip after homogeneous divide).
    project(p) {
        const c = M4.apply(this.viewProj, p);
        if (c.w <= 0) return null;
        const ndcX = c.x / c.w;
        const ndcY = c.y / c.w;
        const ndcZ = c.z / c.w;
        if (ndcZ > 1 || ndcZ < -1) return null;
        return {
            sx: (ndcX * 0.5 + 0.5) * this.w,
            sy: (1 - (ndcY * 0.5 + 0.5)) * this.h,
            depth: c.w,         // distance from camera plane, monotonic with z
        };
    }
}

// ═════════════════════════════════════════════════════════════════════
//   SCENE DEFINITION
//   Defender batteries are spread on a 3000 m circle so they remain
//   four distinct icons at any viewport — earlier 1900 m spacing still
//   visually collapsed below ~1200 px wide.
// ═════════════════════════════════════════════════════════════════════
const RING_RADII_M = [3_000, 5_500, 8_000, 10_500, 13_000];

function hexPosition(thetaDeg, radius) {
    const t = thetaDeg * Math.PI / 180;
    return [Math.sin(t) * radius, 0, Math.cos(t) * radius];
}

// 4 batteries at the cardinal points of a 3000-m circle around the
// defended cell, separated by 90°. Centre command bunker at origin.
const DEFENDER_RADIUS_M = 3_000;
const DEFENDER_BATTERIES = [
    { id: 'NGI',   pos: hexPosition(  0, DEFENDER_RADIUS_M), color: [0.55, 0.85, 1.00] },
    { id: 'SM-3',  pos: hexPosition( 90, DEFENDER_RADIUS_M), color: [0.55, 0.95, 0.78] },
    { id: 'PAC-3', pos: hexPosition(180, DEFENDER_RADIUS_M), color: [0.72, 0.95, 0.55] },
    { id: 'HEL',   pos: hexPosition(270, DEFENDER_RADIUS_M), color: [1.00, 0.88, 0.55] },
];

const COMPASS = [
    { id: 'N', pos: [    0, 0,  13_200] },
    { id: 'E', pos: [13_200, 0,       0] },
    { id: 'S', pos: [    0, 0, -13_200] },
    { id: 'W', pos: [-13_200, 0,      0] },
];

// Defended assets — small hex markers tucked inside the defender ring.
const ASSETS = [
    { id: 'COMMAND', pos: hexPosition(  45, 1_400) },
    { id: 'PORT',    pos: hexPosition( 135, 1_400) },
    { id: 'GRID',    pos: hexPosition( 225, 1_400) },
    { id: 'NODE-7',  pos: hexPosition( 315, 1_400) },
];

// Three threats inbound from different bearings. Each track has an
// explicit `launchAt` (seconds into the demo cycle) and a `flightTime`.
// Outside the [launchAt, launchAt + flightTime] window the track is
// "off-screen" — pre-launch or post-splash — and won't be rendered.
// This fixes the bug where reloading mid-cycle showed threats already
// mid-air with no acquisition history.
const TRACKS = [
    {
        id: 'HGV-WRAITH-01',
        kind: 'HGV',
        launch:   [-13_200,   280,   4_400],
        apogee:   [ -1_400, 7_200,   1_700],
        terminal: [    900,   350,    -700],
        launchAt: 0.4,
        flightTime: 8.5,
        color: [1.00, 0.66, 0.38],
        machBase: 9.4,
        priority: 1,
    },
    {
        id: 'HGV-WRAITH-02',
        kind: 'HGV',
        launch:   [ -9_200,   360, -11_200],
        apogee:   [ -1_000, 6_400,  -2_800],
        terminal: [    600,   360,   1_300],
        launchAt: 2.0,
        flightTime: 9.5,
        color: [1.00, 0.55, 0.20],
        machBase: 8.8,
        priority: 2,
    },
    {
        id: 'MARV-VIPER-03',
        kind: 'MARV',
        launch:   [ 12_400,   220,  10_200],
        apogee:   [  3_400, 4_400,   3_800],
        terminal: [   -800,   320,    -500],
        launchAt: 4.0,
        flightTime: 7.0,
        color: [0.95, 0.84, 0.55],
        machBase: 6.8,
        priority: 3,
    },
];

const findDefender = (id) => DEFENDER_BATTERIES.find(d => d.id === id);
const findTrack    = (id) => TRACKS.find(t => t.id === id);

// Per-COA allocation. Map keyed by COA id → list of {defender, target,
// kind, speed}. The `speed` here is the average interceptor speed used
// for TTI prediction (display only — actual flight uses the boost +
// cruise + turn-rate physics in tickSalvos).
const COA_ALLOCATIONS = {
    'COA-A': [
        { defender: 'NGI', target: 'HGV-WRAITH-01', kind: 'KINETIC',  speed: 850 },
        { defender: 'NGI', target: 'HGV-WRAITH-02', kind: 'KINETIC',  speed: 850 },
        { defender: 'NGI', target: 'MARV-VIPER-03', kind: 'KINETIC',  speed: 850 },
    ],
    'COA-B': [
        { defender: 'NGI', target: 'HGV-WRAITH-01', kind: 'KINETIC',  speed: 850 },
        { defender: 'NGI', target: 'HGV-WRAITH-02', kind: 'KINETIC',  speed: 850 },
        { defender: 'HEL', target: 'MARV-VIPER-03', kind: 'DIRECTED', speed: 2.998e8 },
    ],
    'COA-C': [
        { defender: 'NGI', target: 'HGV-WRAITH-01', kind: 'KINETIC',  speed: 850 },
        { defender: 'NGI', target: 'HGV-WRAITH-02', kind: 'KINETIC',  speed: 850 },
    ],
};

// The currently-recommended allocation (shown as dashed lines while
// COAs are on the table). After authorization, the actual salvos take
// over and this is hidden.
const ENGAGEMENT_ALLOC = COA_ALLOCATIONS['COA-B'];

// ═════════════════════════════════════════════════════════════════════
//   THREAT MOTION
//   Each track has an explicit launchAt + flightTime measured against
//   cyclePhase (so it loops with the demo). Outside [launchAt, launchAt
//   + flightTime] the track is dormant — returns a phase of -1 (pre)
//   or 2 (post) which trackPos / trackVisible / draw* all check.
// ═════════════════════════════════════════════════════════════════════
function trackPhaseAt(tr, t) {
    const cyc = t % CYCLE;
    const elapsed = cyc - tr.launchAt;
    if (elapsed < 0) return -1;
    if (elapsed > tr.flightTime) return 2;
    return elapsed / tr.flightTime;
}
function trackPhase(tr) { return trackPhaseAt(tr, clock.now); }
function trackVisible(tr) {
    const ph = trackPhase(tr);
    return ph >= 0 && ph <= 1;
}
function trackPosAt(tr, t) {
    const ph = trackPhaseAt(tr, t);
    if (ph < 0) return tr.launch;
    if (ph > 1) return tr.terminal;
    return V3.bezQ(tr.launch, tr.apogee, tr.terminal, ph);
}
function trackPos(tr) { return trackPosAt(tr, clock.now); }
function trackSpeedMach(tr) {
    const t = clamp(trackPhase(tr), 0, 1);
    return tr.machBase * (1 - 0.18 * Math.sin(Math.PI * t)) * (0.95 + 0.10 * t);
}

// ═════════════════════════════════════════════════════════════════════
//   ENGAGEMENT STATE — what the operator has actually committed to.
// ═════════════════════════════════════════════════════════════════════
const engagement = {
    authorizedCOA: null,          // 'COA-A' | 'COA-B' | 'COA-C' | null
    authorizedAt: null,           // sec on clock
    authorizedBy: null,           // 'OPERATOR' | 'AUTO'
    objected: new Set(),          // COA ids the operator rejected
    salvos: [],                   // live projectiles
    splashes: [],                 // post-impact rings, faded out by age
    killedTracks: new Set(),      // track ids that have been killed
    pulseUntil: 0,                // gold ring confirmation effect
    notice: null,                 // { text, until }
    pushedLog: new Set(),         // dedupe one-shot log lines
    autoEngage: false,            // ROE weapons-free auto-authorization
    autoEngagedThisCycle: false,  // dedupe per cycle
};

function pushLogOnce(key, line) {
    if (engagement.pushedLog.has(key)) return;
    engagement.pushedLog.add(key);
    CALM_LIVE.unshift(line);
    if (CALM_LIVE.length > 14) CALM_LIVE.pop();
    lastCalmK = -2;     // force re-render of calm channel next frame
}

function resetEngagement() {
    engagement.authorizedCOA = null;
    engagement.authorizedAt = null;
    engagement.authorizedBy = null;
    engagement.objected = new Set();
    engagement.salvos = [];
    engagement.splashes = [];
    engagement.killedTracks = new Set();
    engagement.pulseUntil = 0;
    engagement.notice = null;
    engagement.pushedLog = new Set();
    engagement.autoEngagedThisCycle = false;
}

// ═════════════════════════════════════════════════════════════════════
//   CLOCK — fixed-rate logical clock with optional freeze.
// ═════════════════════════════════════════════════════════════════════
class Clock {
    constructor() {
        this.now = 0;            // monotonic seconds since start
        this.frozenAt = null;
    }
    tick(dt) { if (this.frozenAt === null) this.now += dt; }
    freeze(sec) { this.frozenAt = sec; this.now = sec; }
    unfreeze()  { this.frozenAt = null; }
}
const clock = new Clock();

// Demo cycle — tightened so AUTO actually exercises a wave every ~20s
// instead of every 28s, and the operator sees COA cards within ~1.2s
// of page load. Threats spawn at their declared launchAt times.
const CYCLE = 20;
const COA_OPEN_T   = 1.2;
const COA_CLOSE_T  = 14.0;
const MODE_B_OPEN  = 0.8;
const MODE_B_CLOSE = 16.0;
function cyclePhase() { return clock.now % CYCLE; }

// ═════════════════════════════════════════════════════════════════════
//   STARS — deterministic placement so reloads are pixel-identical.
// ═════════════════════════════════════════════════════════════════════
function mulberry32(seed) {
    return function () {
        seed |= 0; seed = (seed + 0x6D2B79F5) | 0;
        let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
        t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
        return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
    };
}
function makeStars(rng, count, width, height) {
    const out = [];
    for (let i = 0; i < count; i++) {
        out.push({
            x: rng() * width,
            y: rng() * (height * 0.62),
            r: 0.45 + rng() * 1.1,
            a: 0.18 + rng() * 0.48,
        });
    }
    return out;
}

// ═════════════════════════════════════════════════════════════════════
//   CANVAS
// ═════════════════════════════════════════════════════════════════════
const canvas = document.getElementById('stage');
const ctx = canvas.getContext('2d');
const cam = new Camera();
let proj = new Projector(cam, window.innerWidth, window.innerHeight);
let stars = [];

function resizeCanvas() {
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    canvas.width  = Math.floor(window.innerWidth  * dpr);
    canvas.height = Math.floor(window.innerHeight * dpr);
    canvas.style.width  = window.innerWidth  + 'px';
    canvas.style.height = window.innerHeight + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    proj.resize(window.innerWidth, window.innerHeight);
    stars = makeStars(mulberry32(0xC1A05), 140, window.innerWidth, window.innerHeight);
}
window.addEventListener('resize', resizeCanvas);
resizeCanvas();

const snap = (v) => Math.round(v) + 0.5;     // crisp 1-pixel strokes
const rgbStr = (c, a) => {
    const r = Math.max(0, Math.min(255, c[0] * 255 | 0));
    const g = Math.max(0, Math.min(255, c[1] * 255 | 0));
    const b = Math.max(0, Math.min(255, c[2] * 255 | 0));
    return a === undefined ? `rgb(${r},${g},${b})` : `rgba(${r},${g},${b},${a})`;
};
const easeOutCubic = (x) => 1 - Math.pow(1 - x, 3);
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

// ═════════════════════════════════════════════════════════════════════
//   LAYER: sky + atmosphere
// ═════════════════════════════════════════════════════════════════════
function horizonScreenY() {
    // Project a point on the ground plane at 200 km along the camera's
    // ground-plane forward direction. That gives us a stable horizon Y
    // regardless of orbit angle.
    const eye = cam.eye();
    const f = V3.norm(V3.sub(cam.target(), eye));
    const groundFwd = V3.norm([f[0], 0, f[2]]);
    const far = [eye[0] + groundFwd[0]*200_000, 0, eye[2] + groundFwd[2]*200_000];
    const p = proj.project(far);
    if (!p) return proj.h * 0.5;
    return clamp(p.sy, 60, proj.h - 80);
}

function drawSky() {
    const W = proj.w, H = proj.h;
    const horizonY = horizonScreenY();

    const sky = ctx.createLinearGradient(0, 0, 0, horizonY);
    sky.addColorStop(0.00, '#020714');
    sky.addColorStop(0.45, '#06142A');
    sky.addColorStop(1.00, '#0E2541');
    ctx.fillStyle = sky;
    ctx.fillRect(0, 0, W, horizonY);

    const ground = ctx.createLinearGradient(0, horizonY, 0, H);
    ground.addColorStop(0.00, '#0A1B30');
    ground.addColorStop(0.45, '#060F1E');
    ground.addColorStop(1.00, '#020814');
    ctx.fillStyle = ground;
    ctx.fillRect(0, horizonY, W, H - horizonY);

    // Atmospheric haze line above the horizon
    const halo = ctx.createLinearGradient(0, horizonY - 40, 0, horizonY + 12);
    halo.addColorStop(0.00, 'rgba(201, 169, 97, 0.00)');
    halo.addColorStop(0.65, 'rgba(201, 169, 97, 0.045)');
    halo.addColorStop(1.00, 'rgba(201, 169, 97, 0.13)');
    ctx.fillStyle = halo;
    ctx.fillRect(0, horizonY - 40, W, 52);

    ctx.strokeStyle = 'rgba(201, 169, 97, 0.30)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, snap(horizonY));
    ctx.lineTo(W, snap(horizonY));
    ctx.stroke();
}

function drawStars() {
    for (const s of stars) {
        ctx.fillStyle = `rgba(232, 226, 208, ${s.a})`;
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
        ctx.fill();
    }
}

// ═════════════════════════════════════════════════════════════════════
//   LAYER: ground grid (rings + radial spokes + cardinal compass)
// ═════════════════════════════════════════════════════════════════════
function drawRangeRings() {
    const segs = 128;
    for (let r = 0; r < RING_RADII_M.length; r++) {
        const radius = RING_RADII_M[r];
        ctx.beginPath();
        let prev = null;
        for (let i = 0; i <= segs; i++) {
            const theta = (i / segs) * Math.PI * 2;
            const p = proj.project([Math.sin(theta) * radius, 0, Math.cos(theta) * radius]);
            if (!p) { prev = null; continue; }
            if (!prev) ctx.moveTo(p.sx, p.sy); else ctx.lineTo(p.sx, p.sy);
            prev = p;
        }
        const baseAlpha = 0.60 - r * 0.09;
        ctx.strokeStyle = `rgba(201, 169, 97, ${baseAlpha})`;
        ctx.lineWidth = r === 0 ? 1.3 : (r === RING_RADII_M.length - 1 ? 0.8 : 1.0);
        ctx.stroke();

        // Tick label
        const labelP = proj.project([radius, 0, 0]);
        if (labelP) {
            ctx.fillStyle = `rgba(201, 169, 97, ${baseAlpha * 0.85})`;
            ctx.font = '600 9px ui-monospace, "SF Mono", Menlo, monospace';
            ctx.textBaseline = 'middle';
            ctx.fillText(`${(radius/1000).toFixed(1)} km`, labelP.sx + 6, labelP.sy - 1);
        }
    }
}

function drawRadialSpokes() {
    const spokes = 12;
    const outer = RING_RADII_M[RING_RADII_M.length - 1];
    const origin = proj.project([0, 0, 0]);
    if (!origin) return;
    for (let i = 0; i < spokes; i++) {
        const theta = (i / spokes) * Math.PI * 2;
        const end = proj.project([Math.sin(theta) * outer, 0, Math.cos(theta) * outer]);
        if (!end) continue;
        ctx.strokeStyle = 'rgba(201, 169, 97, 0.12)';
        ctx.lineWidth = 0.7;
        ctx.beginPath();
        ctx.moveTo(snap(origin.sx), snap(origin.sy));
        ctx.lineTo(end.sx, end.sy);
        ctx.stroke();
    }
}

function drawCompass() {
    for (const c of COMPASS) {
        const head = proj.project([c.pos[0], 900, c.pos[2]]);
        const foot = proj.project([c.pos[0], -50,  c.pos[2]]);
        if (!head || !foot) continue;
        const g = ctx.createLinearGradient(0, head.sy, 0, foot.sy);
        g.addColorStop(0.0, 'rgba(201, 169, 97, 0.0)');
        g.addColorStop(0.6, 'rgba(201, 169, 97, 0.85)');
        g.addColorStop(1.0, 'rgba(201, 169, 97, 0.45)');
        ctx.strokeStyle = g;
        ctx.lineWidth = 1.4;
        ctx.beginPath();
        ctx.moveTo(snap(head.sx), head.sy);
        ctx.lineTo(snap(foot.sx), foot.sy);
        ctx.stroke();

        ctx.fillStyle = 'rgba(201, 169, 97, 0.92)';
        ctx.font = '800 12px -apple-system, "SF Pro Display", sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'alphabetic';
        ctx.fillText(c.id, head.sx, head.sy - 6);
        ctx.textAlign = 'start';
    }
}

// ═════════════════════════════════════════════════════════════════════
//   LAYER: defended assets + defender batteries
// ═════════════════════════════════════════════════════════════════════
function drawAssets() {
    for (const a of ASSETS) {
        const g = proj.project(a.pos);
        if (!g) continue;
        const half = Math.max(3, 20 / Math.max(0.5, g.depth / 6500));
        ctx.strokeStyle = 'rgba(232, 226, 208, 0.55)';
        ctx.lineWidth = 1.0;
        ctx.beginPath();
        for (let i = 0; i < 6; i++) {
            const t = (i / 6) * Math.PI * 2 + Math.PI / 6;
            const px = g.sx + Math.cos(t) * half;
            const py = g.sy + Math.sin(t) * half;
            if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
        }
        ctx.closePath();
        ctx.stroke();
        ctx.fillStyle = 'rgba(232, 226, 208, 0.72)';
        ctx.beginPath();
        ctx.arc(g.sx, g.sy, 1.4, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = 'rgba(232, 226, 208, 0.50)';
        ctx.font = '700 8px ui-monospace, "SF Mono", Menlo, monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillText(a.id, g.sx, g.sy + half + 2);
        ctx.textAlign = 'start';
    }
}

function drawDefenderBatteries() {
    for (const b of DEFENDER_BATTERIES) {
        const base = proj.project(b.pos);
        const top  = proj.project([b.pos[0], 380, b.pos[2]]);
        if (!base || !top) continue;
        const half = Math.max(5, 90 / Math.max(0.7, base.depth / 7000));

        // Pedestal chevron
        ctx.fillStyle = 'rgba(14, 26, 44, 0.96)';
        ctx.strokeStyle = rgbStr(b.color, 0.95);
        ctx.lineWidth = 1.4;
        ctx.beginPath();
        ctx.moveTo(base.sx - half, base.sy + half * 0.42);
        ctx.lineTo(base.sx + half, base.sy + half * 0.42);
        ctx.lineTo(top.sx,         top.sy);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();

        // Halo
        const glowR = half * 2.0;
        const halo = ctx.createRadialGradient(top.sx, top.sy, 0, top.sx, top.sy, glowR);
        halo.addColorStop(0, rgbStr(b.color, 0.60));
        halo.addColorStop(1, rgbStr(b.color, 0.00));
        ctx.fillStyle = halo;
        ctx.beginPath();
        ctx.arc(top.sx, top.sy, glowR, 0, Math.PI * 2);
        ctx.fill();

        // Hot core
        ctx.fillStyle = rgbStr(b.color, 1.0);
        ctx.beginPath();
        ctx.arc(top.sx, top.sy, 2.5, 0, Math.PI * 2);
        ctx.fill();

        // Label below pedestal
        const labelP = proj.project([b.pos[0], -120, b.pos[2]]);
        if (labelP) {
            ctx.fillStyle = rgbStr(b.color, 0.95);
            ctx.font = '800 9.5px ui-monospace, "SF Mono", Menlo, monospace';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'top';
            ctx.fillText(b.id, labelP.sx, labelP.sy + 2);
            ctx.textAlign = 'start';
        }
    }

    // Centre marker — small bone-color cross at the origin
    const origin = proj.project([0, 0, 0]);
    if (origin) {
        ctx.strokeStyle = 'rgba(232, 226, 208, 0.68)';
        ctx.lineWidth = 1.1;
        ctx.beginPath();
        ctx.moveTo(snap(origin.sx - 7), snap(origin.sy));
        ctx.lineTo(snap(origin.sx + 7), snap(origin.sy));
        ctx.moveTo(snap(origin.sx),     snap(origin.sy - 7));
        ctx.lineTo(snap(origin.sx),     snap(origin.sy + 7));
        ctx.stroke();
        ctx.fillStyle = 'rgba(232, 226, 208, 0.85)';
        ctx.beginPath();
        ctx.arc(origin.sx, origin.sy, 1.6, 0, Math.PI * 2);
        ctx.fill();
    }
}

// ═════════════════════════════════════════════════════════════════════
//   LAYER: sensor coverage arcs
// ═════════════════════════════════════════════════════════════════════
function drawSensorCoverage() {
    const sectors = [
        { range: 11_000, halfAngle: Math.PI * 0.32, bearing: 0,                  color: [0.78, 0.66, 0.38], alpha: 0.20 },
        { range:  7_000, halfAngle: Math.PI * 0.55, bearing: Math.PI * 0.72,     color: [0.55, 0.78, 0.95], alpha: 0.16 },
    ];
    const segs = 80;
    for (const s of sectors) {
        const a0 = s.bearing - s.halfAngle;
        const a1 = s.bearing + s.halfAngle;
        const a  = proj.project([0, 0, 0]);
        if (!a) continue;

        ctx.beginPath();
        ctx.moveTo(a.sx, a.sy);
        let any = false;
        for (let i = 0; i <= segs; i++) {
            const theta = a0 + (a1 - a0) * (i / segs);
            const p = proj.project([Math.sin(theta) * s.range, 0, Math.cos(theta) * s.range]);
            if (!p) continue;
            ctx.lineTo(p.sx, p.sy);
            any = true;
        }
        if (any) {
            ctx.lineTo(a.sx, a.sy);
            ctx.fillStyle = rgbStr(s.color, s.alpha * 0.35);
            ctx.fill();
        }

        ctx.strokeStyle = rgbStr(s.color, s.alpha * 2.4);
        ctx.lineWidth = 0.9;
        ctx.beginPath();
        let started = false;
        for (let i = 0; i <= segs; i++) {
            const theta = a0 + (a1 - a0) * (i / segs);
            const p = proj.project([Math.sin(theta) * s.range, 0, Math.cos(theta) * s.range]);
            if (!p) { started = false; continue; }
            if (!started) ctx.moveTo(p.sx, p.sy);
            else          ctx.lineTo(p.sx, p.sy);
            started = true;
        }
        ctx.stroke();
    }
}

// ═════════════════════════════════════════════════════════════════════
//   LAYER: impact-point reticles
// ═════════════════════════════════════════════════════════════════════
function drawImpactPredictions() {
    for (const tr of TRACKS) {
        if (!trackVisible(tr)) continue;
        if (engagement.killedTracks.has(tr.id)) continue;
        const t = trackPhase(tr);
        const impact = proj.project([tr.terminal[0], 0, tr.terminal[2]]);
        if (!impact) continue;
        const urgency = Math.pow(t, 1.8);
        const alpha = 0.32 + urgency * 0.55;
        const r = 10 + urgency * 8;

        ctx.strokeStyle = rgbStr(tr.color, alpha);
        ctx.lineWidth = 0.9;
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.arc(impact.sx, impact.sy, r, 0, Math.PI * 2);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.beginPath();
        ctx.moveTo(snap(impact.sx - r * 0.7), snap(impact.sy));
        ctx.lineTo(snap(impact.sx + r * 0.7), snap(impact.sy));
        ctx.moveTo(snap(impact.sx),           snap(impact.sy - r * 0.7));
        ctx.lineTo(snap(impact.sx),           snap(impact.sy + r * 0.7));
        ctx.stroke();
    }
}

// ═════════════════════════════════════════════════════════════════════
//   LAYER: trails (Catmull-Rom smoothed)
// ═════════════════════════════════════════════════════════════════════
const TRAIL_SAMPLES = 72;
const trails = TRACKS.map(() => []);

function pushTrailSamples() {
    for (let i = 0; i < TRACKS.length; i++) {
        // Reset the trail when the track is dormant — keeps the
        // streak from "teleporting" between cycles.
        if (!trackVisible(TRACKS[i])) {
            if (trails[i].length) trails[i].length = 0;
            continue;
        }
        trails[i].push(trackPos(TRACKS[i]));
        if (trails[i].length > TRAIL_SAMPLES) trails[i].shift();
    }
}

function drawTrails() {
    const subdivisions = 8;        // Catmull-Rom interior samples per segment
    for (let ti = 0; ti < TRACKS.length; ti++) {
        const tr = TRACKS[ti];
        if (engagement.killedTracks.has(tr.id)) continue;
        if (!trackVisible(tr)) continue;
        const s = trails[ti];
        const n = s.length;
        if (n < 4) continue;

        // Project all points once; null entries are clip-skips.
        const proj_pts = new Array(n);
        for (let i = 0; i < n; i++) proj_pts[i] = proj.project(s[i]);

        for (let i = 1; i < n - 2; i++) {
            const p0 = s[i - 1], p1 = s[i], p2 = s[i + 1], p3 = s[i + 2];
            // Per-segment width and alpha based on age (older = thinner/dimmer)
            const age = (i + 1) / n;
            const alphaPath = Math.pow(age, 1.6);
            const widthPath = 0.7 + age * 2.6;
            const colorBlend = [
                tr.color[0] * (0.25 + 0.75 * age),
                tr.color[1] * (0.25 + 0.75 * age),
                tr.color[2] * (0.25 + 0.75 * age),
            ];
            ctx.strokeStyle = rgbStr(colorBlend, alphaPath * 0.95);
            ctx.lineWidth   = widthPath;
            ctx.lineCap = 'round';

            ctx.beginPath();
            let firstSet = false;
            for (let k = 0; k <= subdivisions; k++) {
                const tk = k / subdivisions;
                const wp = V3.catmull(p0, p1, p2, p3, tk);
                const sp = proj.project(wp);
                if (!sp) continue;
                if (!firstSet) { ctx.moveTo(sp.sx, sp.sy); firstSet = true; }
                else            { ctx.lineTo(sp.sx, sp.sy); }
            }
            ctx.stroke();
        }
    }
}

// ═════════════════════════════════════════════════════════════════════
//   INTERCEPT MATHEMATICS
//
//   Two related problems:
//
//   1. Engagement planning (planIntercept). Given a threat whose
//      trajectory is known parametrically, sweep φ ∈ [φ_now, 1] over
//      the threat's normalised flight phase and pick the φ* that
//      minimises |T_threat(φ) − T_interceptor(φ)|, where
//        T_threat(φ)      = launchAt + φ·flightTime − cyclePhase
//        T_interceptor(φ) = boost + max(0, dist(launcher,r_T(φ)) − boostDist) / cruise
//      Returns a feasibility flag — false if the soonest the
//      interceptor can be there is still after the threat has
//      already passed. This is what kills the "ghost shoot": if a
//      defender can't catch the threat, the salvo is never armed.
//
//   2. In-flight guidance (leadInterceptTime). Once airborne, the
//      missile shouldn't chase where the target IS — it has to lead.
//      Treating the target as locally linear at velocity v_T, the
//      collision-course equation reduces to a quadratic in t:
//        (v_I² − |v_T|²) t² − 2(d · v_T) t − |d|² = 0
//      with d = r_T(now) − r_I(now). The smaller positive root is
//      the lead time; the aim point is r_T(now + t*). This is the
//      classic proportional-navigation lead solution, applied each
//      frame so the missile flies a true collision course.
// ═════════════════════════════════════════════════════════════════════

// Average interceptor speed including boost (used by planIntercept
// only — in-flight uses the live boost+cruise model).
const KINETIC_AVG_MPS = 935;
const KINETIC_CRUISE_MPS = 1100;
const KINETIC_BOOST_DURATION = 0.55;
const KINETIC_BOOST_AVG_MPS = 660;

function planIntercept(track, defender, avgSpeed) {
    const launcherPos = [defender.pos[0], 380, defender.pos[2]];
    const boostDist = KINETIC_BOOST_AVG_MPS * KINETIC_BOOST_DURATION;
    // Earliest phase the threat can be intercepted from now: at minimum
    // the radar must have acquired it (track.launchAt + 0.3 s detection
    // delay), and we need a small reaction window.
    const REACTION = 0.35;
    const nowCyc = cyclePhase();
    const minPhase = Math.max(
        0,
        (Math.max(track.launchAt + 0.3, nowCyc + REACTION) - track.launchAt) / track.flightTime
    );
    if (minPhase > 1) return null;

    const samples = 60;
    let best = null;
    for (let i = 0; i <= samples; i++) {
        const ph = minPhase + (1 - minPhase) * (i / samples);
        const tAtCycle = track.launchAt + ph * track.flightTime;
        const threatT = tAtCycle - nowCyc;
        if (threatT < REACTION) continue;
        const point = V3.bezQ(track.launch, track.apogee, track.terminal, ph);
        const dist = V3.len(V3.sub(point, launcherPos));
        const interceptorT = (dist <= boostDist)
            ? dist / KINETIC_BOOST_AVG_MPS
            : KINETIC_BOOST_DURATION + (dist - boostDist) / KINETIC_CRUISE_MPS;
        if (interceptorT > threatT + 0.05) continue;     // infeasible
        const slack = threatT - interceptorT;
        // Prefer the SMALLEST positive slack — converge on the
        // crossing point where threat and interceptor times match.
        if (best === null || slack < best.slack) {
            best = { tti: interceptorT, threatT, slack, ph, point };
        }
    }
    return best;        // null if no feasible intercept along trajectory
}

// Quadratic lead solution for an interceptor at p_I cruising at v_I
// against a target at r_T moving at v_T (locally linear). Returns the
// smallest positive root of (v_I²−|v_T|²)t² − 2(d·v_T)t − |d|² = 0, or
// null if no real positive root.
function leadInterceptTime(p_I, r_T, v_T, v_I) {
    const d = V3.sub(r_T, p_I);
    const dvt = V3.dot(d, v_T);
    const vTvT = V3.dot(v_T, v_T);
    const dd = V3.dot(d, d);
    const a = v_I * v_I - vTvT;
    const b = -2 * dvt;
    const c = -dd;
    if (Math.abs(a) < 1e-6) {
        if (Math.abs(b) < 1e-6) return null;
        const t = -c / b;
        return t > 0 ? t : null;
    }
    const disc = b * b - 4 * a * c;
    if (disc < 0) return null;
    const sqrtD = Math.sqrt(disc);
    const t1 = (-b + sqrtD) / (2 * a);
    const t2 = (-b - sqrtD) / (2 * a);
    let best = Infinity;
    if (t1 > 0 && t1 < best) best = t1;
    if (t2 > 0 && t2 < best) best = t2;
    return isFinite(best) ? best : null;
}

// Numerical derivative of the threat trajectory at time t (world m/s).
function trackVelAt(track, t) {
    const eps = 0.05;
    const a = trackPosAt(track, t);
    const b = trackPosAt(track, t + eps);
    return V3.scale(V3.sub(b, a), 1 / eps);
}

// Legacy name retained for the dashed planning lines + the stats TTI.
// Now backed by planIntercept so it shares the same math.
function predictIntercept(track, defender, _interceptorV) {
    const p = planIntercept(track, defender, KINETIC_AVG_MPS);
    if (p) return { tti: p.tti, point: p.point, feasible: true };
    return { tti: 0, point: trackPos(track), feasible: false };
}

function drawEngagementAllocations() {
    // Hide the planning overlay once the operator authorizes — the
    // actual salvo lines take over.
    if (engagement.authorizedCOA !== null) return;
    if (!(cyclePhase() >= 8 && cyclePhase() < 21)) return;
    for (const a of ENGAGEMENT_ALLOC) {
        const def = findDefender(a.defender);
        const tr  = findTrack(a.target);
        if (!def || !tr) continue;
        if (engagement.killedTracks.has(tr.id)) continue;
        const { tti, point } = predictIntercept(tr, def, a.speed);
        const defS = proj.project([def.pos[0], 380, def.pos[2]]);
        const intS = proj.project(point);
        if (!defS || !intS) continue;

        ctx.strokeStyle = 'rgba(201, 169, 97, 0.55)';
        ctx.setLineDash([6, 5]);
        ctx.lineWidth = 1.0;
        ctx.beginPath();
        ctx.moveTo(defS.sx, defS.sy);
        ctx.lineTo(intS.sx, intS.sy);
        ctx.stroke();
        ctx.setLineDash([]);

        // Diamond + label
        const r = 9;
        ctx.strokeStyle = 'rgba(201, 169, 97, 0.95)';
        ctx.lineWidth = 1.4;
        ctx.beginPath();
        ctx.moveTo(intS.sx,     intS.sy - r);
        ctx.lineTo(intS.sx + r, intS.sy);
        ctx.lineTo(intS.sx,     intS.sy + r);
        ctx.lineTo(intS.sx - r, intS.sy);
        ctx.closePath();
        ctx.stroke();

        ctx.font = '800 9px ui-monospace, "SF Mono", Menlo, monospace';
        const txt = `${a.defender}→${a.target.split('-').slice(-1)[0]} · TTI ${tti.toFixed(1)}s`;
        const m = ctx.measureText(txt);
        ctx.fillStyle = 'rgba(10, 22, 40, 0.85)';
        ctx.fillRect(intS.sx + r + 4, intS.sy - 8, m.width + 8, 14);
        ctx.fillStyle = 'rgba(201, 169, 97, 0.95)';
        ctx.textBaseline = 'middle';
        ctx.fillText(txt, intS.sx + r + 8, intS.sy);
    }
}

// ═════════════════════════════════════════════════════════════════════
//   SALVOS — operator-launched interceptors. State machine:
//     planned  ->  inflight  ->  splash  ->  done.
//   Position uses proportional pursuit: each step, the salvo accelerates
//   along the unit vector toward the target's current world position.
// ═════════════════════════════════════════════════════════════════════
function launchSalvo(coaId, alloc, launchOffsetSec) {
    const def = findDefender(alloc.defender);
    const tr  = findTrack(alloc.target);
    if (!def || !tr) return;
    if (engagement.killedTracks.has(tr.id)) return;

    // Pre-flight feasibility check (kinetic only — directed energy is
    // effectively instantaneous so it's always feasible while the
    // target is in line-of-sight).
    let plan = null;
    if (alloc.kind === 'KINETIC') {
        plan = planIntercept(tr, def, KINETIC_AVG_MPS);
        if (!plan) {
            pushLogOnce(
                `infeasible-${coaId}-${alloc.defender}-${alloc.target}`,
                `intercept infeasible <em>${alloc.defender}→${tr.id}</em> · no kinematic solution`,
            );
            return;     // no ghost shot
        }
    }

    engagement.salvos.push({
        id: `${coaId}-${alloc.defender}-${alloc.target}-${engagement.salvos.length}`,
        coa: coaId,
        defenderId: alloc.defender,
        targetId: alloc.target,
        kind: alloc.kind,
        cruiseSpeedMps:  alloc.kind === 'DIRECTED' ? 0 : KINETIC_CRUISE_MPS,
        boostSpeedMps:   alloc.kind === 'DIRECTED' ? 0 : 220,
        accelMps2:       alloc.kind === 'DIRECTED' ? 0 : 1_400,
        turnRateRadSec:  alloc.kind === 'DIRECTED' ? 0 : 2.4,
        boostDuration:   alloc.kind === 'DIRECTED' ? 0 : KINETIC_BOOST_DURATION,
        directedDwell:   alloc.kind === 'DIRECTED' ? 0.4 : 0,
        // `commitAt`  — when the operator pressed AUTHORIZE
        // `armedAt`   — when the target was acquired by radar (the
        //               salvo holds at the launcher until then)
        // `launchedAt`— when the missile actually lifts off
        commitAt: clock.now + launchOffsetSec,
        armedAt: null,
        launchedAt: null,
        // Planned intercept point + planned TTI from planIntercept.
        // These are refined each frame by leadInterceptTime once the
        // missile is airborne.
        plannedTTI:   plan ? plan.tti   : null,
        plannedPoint: plan ? plan.point : null,
        position: [def.pos[0], 380, def.pos[2]],
        velocity: [0, 0, 0],
        speed: 0,
        state: 'queued',           // queued (pre-arm) → armed (on launcher, target acquired) →
                                   // inflight → splash → done
        impactPoint: null,
        impactAt: null,
        color: alloc.kind === 'DIRECTED' ? [1.00, 0.88, 0.55] : [0.55, 0.85, 1.00],
        trail: [],
    });
}

// Smoothly rotate vector `v` toward `target` direction at angular
// speed `omega` (rad/s). Returns a new unit vector — caller scales
// to the desired speed.
function turnToward(velUnit, targetDir, omega, dt) {
    const dot = clamp(V3.dot(velUnit, targetDir), -1, 1);
    const angle = Math.acos(dot);
    if (angle < 1e-4) return targetDir.slice();
    const maxStep = omega * dt;
    if (maxStep >= angle) return targetDir.slice();
    // Slerp between velUnit and targetDir by fraction `maxStep / angle`.
    const f = maxStep / angle;
    const sinA = Math.sin(angle);
    const a = Math.sin((1 - f) * angle) / sinA;
    const b = Math.sin(f * angle) / sinA;
    return [
        velUnit[0] * a + targetDir[0] * b,
        velUnit[1] * a + targetDir[1] * b,
        velUnit[2] * a + targetDir[2] * b,
    ];
}

function tickSalvos(dt) {
    for (const s of engagement.salvos) {
        if (s.state === 'done') continue;
        if (clock.now < s.commitAt) continue;        // pre-commit hold
        const tr = findTrack(s.targetId);
        if (!tr || engagement.killedTracks.has(s.targetId)) {
            s.state = 'done';
            continue;
        }
        const def = findDefender(s.defenderId);

        // ── Acquisition gate ──────────────────────────────────────
        // queued → armed: the salvo is committed but the radar hasn't
        // yet acquired the threat. Re-plan continuously while we wait;
        // refuse to lift off until we have a feasible solution AND the
        // track has been visible for at least the detection window.
        if (s.state === 'queued') {
            if (!trackVisible(tr)) continue;
            // Re-plan now that the track is up. This both keeps the
            // plan tight when the cycle wraps and catches the case
            // where waiting too long left no feasible intercept.
            if (s.kind === 'KINETIC') {
                const plan = planIntercept(tr, def, KINETIC_AVG_MPS);
                if (!plan) {
                    s.state = 'done';
                    pushLogOnce(
                        `miss-${tr.id}-${s.defenderId}`,
                        `intercept infeasible <em>${s.defenderId}→${tr.id}</em> · target out of envelope`,
                    );
                    continue;
                }
                s.plannedTTI = plan.tti;
                s.plannedPoint = plan.point;
            }
            s.armedAt = clock.now;
            s.launchedAt = clock.now;
            s.state = 'inflight';
        }

        const targetPos = trackPos(tr);

        if (s.kind === 'DIRECTED') {
            s.position = V3.lerp(s.position, targetPos, 0.5);
            if (clock.now - s.launchedAt >= s.directedDwell) {
                s.state = 'splash';
                s.impactPoint = targetPos;
                s.impactAt = clock.now;
                killTrack(tr.id, targetPos);
            }
            continue;
        }

        // ── Kinetic interceptor ───────────────────────────────────
        // Lead-angle guidance via the quadratic collision-course
        // solution. Aim point is r_T(now + t*), recomputed each frame.
        const flightT = clock.now - s.launchedAt;
        const cruise = s.speed > 0 ? s.speed : s.cruiseSpeedMps;
        const v_T = trackVelAt(tr, clock.now);
        const t_lead = leadInterceptTime(s.position, targetPos, v_T, Math.max(cruise, KINETIC_BOOST_AVG_MPS));
        const aimPoint = (t_lead !== null)
            ? trackPosAt(tr, clock.now + t_lead)
            : targetPos;                                    // fallback: pure pursuit

        const toAim = V3.sub(aimPoint, s.position);
        const aimDistance = V3.len(toAim);
        const aimDir = V3.scale(toAim, 1 / Math.max(1, aimDistance));

        // During boost, blend up-axis → aim direction so the missile
        // leaves the launcher mostly-vertical and pitches over.
        let desiredDir;
        if (flightT < s.boostDuration) {
            const blend = Math.pow(flightT / s.boostDuration, 1.4);
            const up = [0, 1, 0];
            desiredDir = V3.norm([
                up[0] * (1 - blend) + aimDir[0] * blend,
                up[1] * (1 - blend) + aimDir[1] * blend,
                up[2] * (1 - blend) + aimDir[2] * blend,
            ]);
        } else {
            desiredDir = aimDir;
        }

        const targetSpeed = (flightT < s.boostDuration) ? s.boostSpeedMps : s.cruiseSpeedMps;
        s.speed = Math.min(targetSpeed, (s.speed || s.boostSpeedMps) + s.accelMps2 * dt);

        const currentDir = (V3.len(s.velocity) > 0) ? V3.norm(s.velocity) : [0, 1, 0];
        const newDir = turnToward(currentDir, desiredDir, s.turnRateRadSec, dt);
        s.velocity = V3.scale(newDir, s.speed);

        // Live distance to the actual threat (not the aim point) drives
        // the splash threshold so the warhead detonates at proximity.
        const liveDist = V3.len(V3.sub(targetPos, s.position));
        const stepLen = s.speed * dt;
        if (liveDist < Math.max(140, stepLen * 1.4)) {
            s.state = 'splash';
            s.impactPoint = targetPos;
            s.impactAt = clock.now;
            killTrack(tr.id, targetPos);
        } else {
            s.position = V3.add(s.position, V3.scale(s.velocity, dt));
            const samplePeriod = 1 / 30;
            if (!s._lastSampled || (clock.now - s._lastSampled) >= samplePeriod) {
                s.trail.push(s.position.slice());
                if (s.trail.length > 48) s.trail.shift();
                s._lastSampled = clock.now;
            }
        }

        // Safety floor: if a kinetic salvo has dropped below 20 m and
        // hasn't yet impacted, it's a leakage. Mark done, log it. Stops
        // dud salvos from ploughing into the deck and rendering forever.
        if (s.position[1] < 20 && flightT > 0.8 && s.state !== 'splash') {
            s.state = 'done';
            pushLogOnce(
                `leak-${s.id}`,
                `interceptor leakage <em>${s.defenderId}→${tr.id}</em> · ground impact`,
            );
        }
    }
    // Garbage-collect old splashes
    const cutoff = clock.now - 1.2;
    engagement.salvos = engagement.salvos.filter(s =>
        s.state !== 'splash' || (s.impactAt && s.impactAt > cutoff)
    );
    engagement.splashes = engagement.splashes.filter(sp => sp.until > clock.now);
}

function killTrack(targetId, worldPoint) {
    if (engagement.killedTracks.has(targetId)) return;
    engagement.killedTracks.add(targetId);
    engagement.splashes.push({ point: worldPoint, born: clock.now, until: clock.now + 1.1 });
    pushLogOnce(
        `kill-${targetId}`,
        `target destroyed <em>${targetId}</em>`,
    );
}

function drawSalvos() {
    for (const s of engagement.salvos) {
        if (s.state === 'done') continue;

        // Pending salvo: committed but waiting for the radar to acquire
        // the assigned target. Draw a small pulsing arming reticle on
        // the launcher so the operator sees it's tasked but not yet fired.
        if (s.state === 'queued' && clock.now >= s.commitAt) {
            const def = findDefender(s.defenderId);
            if (!def) continue;
            const dp = proj.project([def.pos[0], 380, def.pos[2]]);
            if (!dp) continue;
            const phase = (clock.now * 4) % 1;
            const r = 10 + phase * 10;
            ctx.strokeStyle = `rgba(220, 160, 60, ${0.75 * (1 - phase)})`;
            ctx.lineWidth = 1.4;
            ctx.beginPath();
            ctx.arc(dp.sx, dp.sy, r, 0, Math.PI * 2);
            ctx.stroke();
            continue;
        }
        if (s.state === 'queued') continue;
        const def = findDefender(s.defenderId);
        const defScreen = def ? proj.project([def.pos[0], 380, def.pos[2]]) : null;
        const projP = proj.project(s.position);
        if (s.kind === 'DIRECTED') {
            // Beam — solid line from defender to current "position" with
            // a halo at the target end.
            if (!defScreen || !projP) continue;
            ctx.strokeStyle = rgbStr(s.color, 0.85);
            ctx.lineWidth = 1.4;
            ctx.beginPath();
            ctx.moveTo(defScreen.sx, defScreen.sy);
            ctx.lineTo(projP.sx, projP.sy);
            ctx.stroke();
            ctx.fillStyle = rgbStr(s.color, 0.95);
            ctx.beginPath();
            ctx.arc(projP.sx, projP.sy, 4, 0, Math.PI * 2);
            ctx.fill();
            continue;
        }
        // Kinetic: hot dot + curving smoke trail from the actual path.
        if (!projP) continue;
        if (s.trail && s.trail.length >= 2) {
            // Draw the trail as a polyline whose alpha and width grow
            // toward the leading dot. Includes the defender launch
            // point as the oldest sample.
            const pts = s.trail.slice();
            if (defScreen && def) pts.unshift([def.pos[0], 380, def.pos[2]]);
            pts.push(s.position);
            const n = pts.length;
            for (let i = 1; i < n; i++) {
                const a = proj.project(pts[i - 1]);
                const b = proj.project(pts[i]);
                if (!a || !b) continue;
                const age = i / n;
                const width = 0.8 + age * 2.0;
                const alpha = Math.pow(age, 1.4);
                ctx.strokeStyle = rgbStr(s.color, alpha * 0.95);
                ctx.lineWidth = width;
                ctx.lineCap = 'round';
                ctx.beginPath();
                ctx.moveTo(a.sx, a.sy);
                ctx.lineTo(b.sx, b.sy);
                ctx.stroke();
            }
        } else if (defScreen) {
            // Pre-trail: render a thin connector from defender to head.
            ctx.strokeStyle = rgbStr(s.color, 0.55);
            ctx.lineWidth = 1.2;
            ctx.beginPath();
            ctx.moveTo(defScreen.sx, defScreen.sy);
            ctx.lineTo(projP.sx, projP.sy);
            ctx.stroke();
        }
        // Hot leading dot + halo
        const halo = ctx.createRadialGradient(projP.sx, projP.sy, 0, projP.sx, projP.sy, 14);
        halo.addColorStop(0.00, rgbStr(s.color, 0.95));
        halo.addColorStop(0.45, rgbStr(s.color, 0.40));
        halo.addColorStop(1.00, rgbStr(s.color, 0.00));
        ctx.fillStyle = halo;
        ctx.beginPath();
        ctx.arc(projP.sx, projP.sy, 14, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = 'rgba(255,255,255,0.95)';
        ctx.beginPath();
        ctx.arc(projP.sx, projP.sy, 2.4, 0, Math.PI * 2);
        ctx.fill();
    }
}

function drawSplashes() {
    for (const sp of engagement.splashes) {
        const p = proj.project(sp.point);
        if (!p) continue;
        const age = (clock.now - sp.born) / (sp.until - sp.born);
        if (age < 0 || age > 1) continue;
        const r1 = 8 + age * 60;
        const r2 = r1 * 0.45;
        // Outer expanding ring (white-hot → amber → gone)
        ctx.strokeStyle = `rgba(255, 220, 140, ${(1 - age) * 0.95})`;
        ctx.lineWidth = 2.2 - age * 1.6;
        ctx.beginPath();
        ctx.arc(p.sx, p.sy, r1, 0, Math.PI * 2);
        ctx.stroke();
        // Inner hot core (yellow → red)
        const hot = ctx.createRadialGradient(p.sx, p.sy, 0, p.sx, p.sy, r2);
        hot.addColorStop(0.00, `rgba(255, 255, 220, ${(1 - age) * 0.95})`);
        hot.addColorStop(0.50, `rgba(255, 180,  60, ${(1 - age) * 0.55})`);
        hot.addColorStop(1.00, `rgba(220,  80,  40, 0)`);
        ctx.fillStyle = hot;
        ctx.beginPath();
        ctx.arc(p.sx, p.sy, r2, 0, Math.PI * 2);
        ctx.fill();
        // Shrapnel ticks
        ctx.strokeStyle = `rgba(255, 200, 100, ${(1 - age) * 0.65})`;
        ctx.lineWidth = 0.9;
        const spokes = 8;
        for (let i = 0; i < spokes; i++) {
            const a = (i / spokes) * Math.PI * 2 + age * 0.5;
            const x1 = p.sx + Math.cos(a) * r1 * 0.5;
            const y1 = p.sy + Math.sin(a) * r1 * 0.5;
            const x2 = p.sx + Math.cos(a) * r1 * 0.95;
            const y2 = p.sy + Math.sin(a) * r1 * 0.95;
            ctx.beginPath();
            ctx.moveTo(x1, y1);
            ctx.lineTo(x2, y2);
            ctx.stroke();
        }
    }
}

// ═════════════════════════════════════════════════════════════════════
//   LAYER: tracks (glowing kinetic markers)
// ═════════════════════════════════════════════════════════════════════
// Draws four L-shaped corner brackets around (cx, cy) at half-size `s`,
// stroke `col` and length `len`. Used as a "track locked" frame around
// each threat — replaces a closed rectangle for a less-busy military look.
function drawCornerBrackets(cx, cy, s, len, col, width) {
    ctx.strokeStyle = col;
    ctx.lineWidth = width;
    ctx.beginPath();
    // top-left
    ctx.moveTo(cx - s, cy - s + len); ctx.lineTo(cx - s, cy - s); ctx.lineTo(cx - s + len, cy - s);
    // top-right
    ctx.moveTo(cx + s - len, cy - s); ctx.lineTo(cx + s, cy - s); ctx.lineTo(cx + s, cy - s + len);
    // bottom-right
    ctx.moveTo(cx + s, cy + s - len); ctx.lineTo(cx + s, cy + s); ctx.lineTo(cx + s - len, cy + s);
    // bottom-left
    ctx.moveTo(cx - s + len, cy + s); ctx.lineTo(cx - s, cy + s); ctx.lineTo(cx - s, cy + s - len);
    ctx.stroke();
}

function drawTracks() {
    for (const tr of TRACKS) {
        if (engagement.killedTracks.has(tr.id)) continue;
        if (!trackVisible(tr)) continue;
        const p = trackPos(tr);
        const sp = proj.project(p);
        if (!sp) continue;
        const r = Math.max(2.5, 220 / Math.max(0.5, sp.depth / 800));

        const halo = ctx.createRadialGradient(sp.sx, sp.sy, 0, sp.sx, sp.sy, r * 4);
        halo.addColorStop(0.00, rgbStr(tr.color, 0.95));
        halo.addColorStop(0.35, rgbStr(tr.color, 0.42));
        halo.addColorStop(1.00, rgbStr(tr.color, 0.00));
        ctx.fillStyle = halo;
        ctx.beginPath();
        ctx.arc(sp.sx, sp.sy, r * 4, 0, Math.PI * 2);
        ctx.fill();

        ctx.fillStyle = 'rgba(255, 255, 255, 0.98)';
        ctx.beginPath();
        ctx.arc(sp.sx, sp.sy, r * 0.55, 0, Math.PI * 2);
        ctx.fill();

        // Corner-bracket "track locked" frame replaces the closed ring.
        const bracketHalf = Math.max(10, r * 2.1);
        const bracketLen  = Math.max(4, bracketHalf * 0.30);
        drawCornerBrackets(sp.sx, sp.sy, bracketHalf, bracketLen, rgbStr(tr.color, 0.95), 1.2);

        // Priority badge
        ctx.fillStyle = 'rgba(10, 22, 40, 0.78)';
        ctx.strokeStyle = rgbStr(tr.color, 0.90);
        ctx.lineWidth = 1.0;
        ctx.beginPath();
        ctx.arc(sp.sx - bracketHalf - 4, sp.sy - bracketHalf - 4, 8, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();
        ctx.fillStyle = rgbStr(tr.color, 0.95);
        ctx.font = '800 9px ui-monospace, "SF Mono", Menlo, monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillText(String(tr.priority), sp.sx - bracketHalf - 4, sp.sy - bracketHalf - 4);
        ctx.textAlign = 'start';
    }
}

// ─── Scanning radar sweep (top-left inset, under the classification bar) ───
// Centre and radius are computed at render time so the inset always sits
// in the same screen position regardless of canvas resize.
function drawRadarSweep() {
    const cx = 120;
    const cy = 200;
    const R  = 64;
    // outer circle + inner range steps
    ctx.strokeStyle = 'rgba(150, 220, 160, 0.32)';
    ctx.lineWidth = 1.0;
    ctx.beginPath();
    ctx.arc(cx, cy, R, 0, Math.PI * 2);
    ctx.stroke();
    ctx.strokeStyle = 'rgba(150, 220, 160, 0.16)';
    ctx.beginPath();
    ctx.arc(cx, cy, R * 0.66, 0, Math.PI * 2);
    ctx.moveTo(cx + R * 0.33, cy);
    ctx.arc(cx, cy, R * 0.33, 0, Math.PI * 2);
    ctx.stroke();
    // crosshair
    ctx.beginPath();
    ctx.moveTo(cx - R, cy); ctx.lineTo(cx + R, cy);
    ctx.moveTo(cx, cy - R); ctx.lineTo(cx, cy + R);
    ctx.stroke();

    // sweep — 720°/s = 4°/frame at 60Hz; phase taken from clock so the
    // sweep is deterministic when frozen.
    const sweepAngle = (clock.now * Math.PI * 0.9) % (Math.PI * 2);
    const sweepArc = ctx.createConicGradient(sweepAngle - Math.PI / 2, cx, cy);
    sweepArc.addColorStop(0.00, 'rgba(150, 220, 160, 0.55)');
    sweepArc.addColorStop(0.08, 'rgba(150, 220, 160, 0.18)');
    sweepArc.addColorStop(0.20, 'rgba(150, 220, 160, 0.00)');
    sweepArc.addColorStop(1.00, 'rgba(150, 220, 160, 0.00)');
    ctx.fillStyle = sweepArc;
    ctx.beginPath();
    ctx.arc(cx, cy, R, 0, Math.PI * 2);
    ctx.fill();
    // crisp leading edge
    ctx.strokeStyle = 'rgba(150, 220, 160, 0.85)';
    ctx.lineWidth = 1.2;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.lineTo(cx + Math.cos(sweepAngle - Math.PI / 2) * R, cy + Math.sin(sweepAngle - Math.PI / 2) * R);
    ctx.stroke();

    // Defender batteries — small green chevrons at their bearings,
    // anchored at the centre. Gives the operator a quick reference for
    // which way each effector is facing.
    for (const b of DEFENDER_BATTERIES) {
        const range = Math.hypot(b.pos[0], b.pos[2]);
        const bearing = Math.atan2(b.pos[0], b.pos[2]);
        const bx = cx + Math.sin(bearing) * (range / 12_500) * R;
        const by = cy - Math.cos(bearing) * (range / 12_500) * R;
        ctx.fillStyle = rgbStr(b.color, 0.55);
        ctx.beginPath();
        ctx.arc(bx, by, 1.6, 0, Math.PI * 2);
        ctx.fill();
    }

    // Threat blips. A track is "displayed" only after the radar's
    // sweep line has crossed its bearing at least once since it
    // appeared — that's what makes the radar feel like a sensor and
    // not omniscient. A small sub-pixel sensor jitter is added so the
    // blip "breathes".
    const sweepBearing = sweepAngle;     // 0 = up = +Z; matches our atan2(x,z)
    let blipCount = 0;
    for (const tr of TRACKS) {
        if (!trackVisible(tr)) continue;
        if (engagement.killedTracks.has(tr.id)) continue;
        const p = trackPos(tr);
        const range = Math.hypot(p[0], p[2]);
        if (range > 13_000) continue;
        const trackBearing = Math.atan2(p[0], p[2]);
        // Difference between sweep and track bearing, wrapped to [0, 2π).
        let phase = (sweepBearing - trackBearing) % (Math.PI * 2);
        if (phase < 0) phase += Math.PI * 2;
        // Blip brightness fades as the sweep moves away (afterglow ~0.5s).
        const afterglow = Math.exp(-phase * 1.4);
        const acquired = (clock.now - (tr.launchAt + 0.1)) > (Math.PI * 2) / 2.83;  // at least one full sweep since launch
        // Range jitter: ±60 m over a slow oscillation per track id.
        const noiseSeed = tr.id.charCodeAt(0) * 0.13 + tr.id.charCodeAt(4) * 0.07;
        const jitter = 60 * Math.sin(clock.now * 3.1 + noiseSeed);
        const dispRange = range + jitter;
        const bx = cx + Math.sin(trackBearing) * (dispRange / 12_500) * R;
        const by = cy - Math.cos(trackBearing) * (dispRange / 12_500) * R;
        const alpha = acquired ? (0.55 + 0.4 * afterglow) : (0.35 * afterglow);
        const rad = acquired ? (2.0 + 1.2 * afterglow) : 1.4;
        ctx.fillStyle = rgbStr(tr.color, alpha);
        ctx.beginPath();
        ctx.arc(bx, by, rad, 0, Math.PI * 2);
        ctx.fill();
        // Ring on freshly-acquired tracks (first ~1s after launch).
        if ((clock.now - tr.launchAt) < 1.2 && (clock.now - tr.launchAt) > 0) {
            ctx.strokeStyle = rgbStr(tr.color, 0.6);
            ctx.lineWidth = 0.8;
            ctx.beginPath();
            ctx.arc(bx, by, rad + 4 + (clock.now - tr.launchAt) * 6, 0, Math.PI * 2);
            ctx.stroke();
        }
        blipCount++;
    }

    // label
    ctx.fillStyle = 'rgba(150, 220, 160, 0.85)';
    ctx.font = '700 8px ui-monospace, "SF Mono", Menlo, monospace';
    ctx.textAlign = 'center';
    ctx.fillText(`RADAR · 12.5 km · ${blipCount} TRK`, cx, cy + R + 12);
    ctx.textAlign = 'start';
}

// ─── Compass tape (top, between classbar and stage) ───
// Sliding tick marks centered on the camera's current ground-plane
// bearing toward (0, 0, 0). Reads in degrees clockwise from north.
function drawCompassTape() {
    const tapeY = 56;             // just below the classification banner
    const tapeH = 22;
    const tapeW = Math.min(720, proj.w - 360);
    const cx = proj.w / 2;
    const x0 = cx - tapeW / 2;

    // background
    ctx.fillStyle = 'rgba(8, 18, 32, 0.72)';
    ctx.fillRect(x0, tapeY, tapeW, tapeH);
    ctx.strokeStyle = 'rgba(201, 169, 97, 0.32)';
    ctx.lineWidth = 1;
    ctx.strokeRect(snap(x0), snap(tapeY), tapeW, tapeH);

    // The camera's bearing: it sits at angle `cam.angle` around the
    // origin, so the heading from camera to origin is angle + π
    // (camera looks "toward" origin). Modulo 360°, expressed as degrees
    // clockwise from north (= +Z axis).
    const bearingRad = cam.angle + Math.PI;
    const bearingDeg = ((bearingRad * 180 / Math.PI) % 360 + 360) % 360;

    // Show ticks for every 10° within ±60° of current bearing.
    const pxPerDeg = tapeW / 120;
    ctx.textAlign = 'center';
    for (let d = -60; d <= 60; d += 10) {
        const heading = ((bearingDeg + d) % 360 + 360) % 360;
        const tx = cx + d * pxPerDeg;
        const isMajor = heading % 30 === 0;
        ctx.strokeStyle = isMajor ? 'rgba(232, 226, 208, 0.78)' : 'rgba(232, 226, 208, 0.38)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(snap(tx), tapeY + 4);
        ctx.lineTo(snap(tx), tapeY + (isMajor ? 12 : 8));
        ctx.stroke();
        if (isMajor) {
            ctx.fillStyle = 'rgba(232, 226, 208, 0.85)';
            ctx.font = '700 9px ui-monospace, "SF Mono", Menlo, monospace';
            ctx.fillText(String(Math.round(heading)).padStart(3, '0'), tx, tapeY + tapeH - 3);
        }
    }
    ctx.textAlign = 'start';

    // Current-heading caret
    ctx.fillStyle = 'rgba(201, 169, 97, 1)';
    ctx.beginPath();
    ctx.moveTo(cx, tapeY + tapeH + 5);
    ctx.lineTo(cx - 5, tapeY + tapeH);
    ctx.lineTo(cx + 5, tapeY + tapeH);
    ctx.closePath();
    ctx.fill();
    ctx.fillStyle = 'rgba(201, 169, 97, 0.95)';
    ctx.font = '800 9.5px ui-monospace, "SF Mono", Menlo, monospace';
    ctx.textAlign = 'center';
    ctx.fillText(`HDG ${String(Math.round(bearingDeg)).padStart(3, '0')}°`, cx, tapeY + tapeH + 17);
    ctx.textAlign = 'start';
}

// ─── Subtle scanlines ───
// Single-pixel dark lines every 3 px at very low opacity. Sells the
// "tactical display" feel without the crunchy CRT look.
function drawScanlines() {
    ctx.fillStyle = 'rgba(0, 0, 0, 0.06)';
    for (let y = 0; y < proj.h; y += 3) {
        ctx.fillRect(0, y, proj.w, 1);
    }
}

// ═════════════════════════════════════════════════════════════════════
//   LAYER: callouts (HTML, positioned via JS — uses CSS transitions)
// ═════════════════════════════════════════════════════════════════════
function positionCallouts() {
    const container = document.getElementById('callouts');
    for (const tr of TRACKS) {
        let node = document.getElementById('co-' + tr.id);
        if (!node) {
            node = document.createElement('div');
            node.id = 'co-' + tr.id;
            node.className = 'callout';
            node.innerHTML = `<span class="callout__id"></span><span class="callout__data"></span>`;
            container.appendChild(node);
        }
        if (engagement.killedTracks.has(tr.id)) { node.style.display = 'none'; continue; }
        if (!trackVisible(tr)) { node.style.display = 'none'; continue; }
        const p = trackPos(tr);
        const sp = proj.project(p);
        if (!sp) { node.style.display = 'none'; continue; }
        const speed = trackSpeedMach(tr);
        const altKm = (p[1] / 1000).toFixed(1);
        const rngKm = (Math.hypot(p[0], p[2]) / 1000).toFixed(1);
        node.style.display = '';
        node.style.left = (sp.sx + 18) + 'px';
        node.style.top  = (sp.sy - 4) + 'px';
        node.querySelector('.callout__id').textContent = `${tr.id} · P${tr.priority}`;
        node.querySelector('.callout__data').textContent =
            `${tr.kind} · CONFIDENT · M${speed.toFixed(1)} · ALT ${altKm} km · RNG ${rngKm} km`;
    }
}

// ═════════════════════════════════════════════════════════════════════
//   UI panels
// ═════════════════════════════════════════════════════════════════════
const COAS = {
    'COA-A': {
        id: 'COA-A',
        head: 'Pure kinetic engagement',
        why: '4× NGI on confirmed HGV midcourse. No directed-energy or non-kinetic.',
        metrics: ['LEAKAGE 7%', 'COST 4 NGI', 'ESC MODERATE', 'REL NATO'],
        countdownSec: 10,
        rec: false,
    },
    'COA-B': {
        id: 'COA-B',
        head: 'Mixed engagement',
        why: '2× NGI on highest-confidence HGV. HEL warmed for swarm screen. Cyber deny adversary GNSS guidance under ROE-2.',
        metrics: ['LEAKAGE 5%', 'COST 2 NGI + 1.2MJ', 'ESC LOW', 'REL NATO'],
        countdownSec: 8,
        rec: true,
    },
    'COA-C': {
        id: 'COA-C',
        head: 'Conservative reserve',
        why: 'Engage two threats now. Reserve NGI for projected Wave-2 launch in next 5 min.',
        metrics: ['LEAKAGE 11%', 'COST 2 NGI', 'ESC LOW', 'REL NATO'],
        countdownSec: 12,
        rec: false,
    },
};

// COAs reveal as soon as the mode trips (now ~1.2s after a fresh page
// load) so the operator — or AUTO — can act inside the threat window.
function activeCOAs(t) {
    if (engagement.authorizedCOA) {
        return [{ ...COAS[engagement.authorizedCOA], remaining: 0, authorized: true }];
    }
    if (t < COA_OPEN_T || t >= COA_CLOSE_T) return [];
    const offset = t - COA_OPEN_T;
    return [
        { ...COAS['COA-B'], remaining: clamp(COAS['COA-B'].countdownSec - offset, 0, COAS['COA-B'].countdownSec) },
        { ...COAS['COA-A'], remaining: clamp(COAS['COA-A'].countdownSec - offset, 0, COAS['COA-A'].countdownSec) },
        { ...COAS['COA-C'], remaining: clamp(COAS['COA-C'].countdownSec - offset, 0, COAS['COA-C'].countdownSec) },
    ].filter(c => !engagement.objected.has(c.id));
}
function modeAt(t) {
    if (t >= MODE_B_OPEN && t < MODE_B_CLOSE) return { letter: 'B', name: 'SENSOR DEGRADED', color: 'amber' };
    return { letter: 'A', name: 'NOMINAL', color: 'gold' };
}

let lastCoaSig = '';
function renderHUD(t) {
    const m = modeAt(t);
    const ltr = document.getElementById('modeLetter');
    const nm  = document.getElementById('modeName');
    const hud = document.getElementById('modeHud');
    if (ltr.textContent !== m.letter) ltr.textContent = m.letter;
    if (nm.textContent !== m.name) nm.textContent = m.name;
    hud.style.borderBottomColor = m.color === 'amber' ? 'rgba(220, 160, 60, 0.85)' : 'var(--rule)';
    ltr.style.color = m.color === 'amber' ? '#DC9A3C' : 'var(--gold)';
}

function renderDecisions(t) {
    const stack = document.getElementById('coaStack');
    const coas = activeCOAs(t);
    const sig = coas.map(c => c.id + (c.authorized ? ':A' : '')).join('|')
              + (coas.length === 0 ? 'X' : '')
              + '|' + [...engagement.objected].sort().join(',');
    if (sig !== lastCoaSig) {
        if (coas.length === 0) {
            stack.innerHTML = `<div class="decisions__empty">STAND BY — NO ACTIVE COA</div>`;
        } else {
            stack.innerHTML = coas.map(c => {
                const cls = c.authorized
                    ? 'coa coa--authorized'
                    : 'coa' + (c.rec ? ' coa--rec' : '');
                const badgeLabel = c.authorized
                    ? (engagement.authorizedBy === 'AUTO' ? 'AUTO-AUTH' : 'AUTHORIZED')
                    : (c.rec ? 'RECOMMENDED' : '');
                const badge = c.authorized
                    ? `<span class="coa__badge coa__badge--ok">${badgeLabel}</span>`
                    : (c.rec ? `<span class="coa__badge">${badgeLabel}</span>` : '');
                const statusText = engagement.authorizedBy === 'AUTO'
                    ? 'EFFECTORS COMMITTED · AUTO-ENGAGE · IMPACT IN PROGRESS'
                    : 'EFFECTORS COMMITTED · IMPACT IN PROGRESS';
                const buttonsHTML = c.authorized
                    ? `<div class="coa__status">${statusText}</div>`
                    : `
                        <div class="coa__btns">
                            <button class="coa__btn coa__btn--p" data-action="auth" data-coa="${c.id}">AUTHORIZE</button>
                            <button class="coa__btn coa__btn--s" data-action="obj" data-coa="${c.id}">OBJECT</button>
                        </div>
                    `;
                return `
                    <div class="${cls}" data-id="${c.id}" data-cd="${c.countdownSec}">
                        <div class="coa__top">
                            <span class="coa__id">${c.id}</span>
                            ${badge}
                        </div>
                        <div class="coa__head">${c.head}</div>
                        <div class="coa__why">${c.why}</div>
                        <div class="coa__metrics">${c.metrics.map(m => `<div>${m}</div>`).join('')}</div>
                        <div class="coa__bar"><div class="coa__bar-fill" style="width:100%"></div></div>
                        ${buttonsHTML}
                    </div>
                `;
            }).join('');
        }
        lastCoaSig = sig;
    }
    // Update only the bar widths per frame
    if (coas.length > 0 && !engagement.authorizedCOA) {
        const cards = stack.querySelectorAll('.coa');
        for (let i = 0; i < cards.length && i < coas.length; i++) {
            const c = coas[i];
            const fill = cards[i].querySelector('.coa__bar-fill');
            if (fill) fill.style.width = ((c.remaining / c.countdownSec) * 100).toFixed(1) + '%';
        }
    }
}

// One-shot delegated click handler — survives every renderDecisions
// rebuild because it listens on the stable parent #coaStack.
document.getElementById('coaStack').addEventListener('click', (e) => {
    const btn = e.target.closest('button[data-action]');
    if (!btn) return;
    const action = btn.dataset.action;
    const coaId  = btn.dataset.coa;
    if (action === 'auth') authorizeCOA(coaId);
    if (action === 'obj')  objectCOA(coaId);
});
// Also accept the keyboard mnemonics shown in the panel footer.
document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === 'a' || e.key === 'A') {
        const rec = Object.values(COAS).find(c => c.rec);
        if (rec && !engagement.authorizedCOA && !engagement.objected.has(rec.id)) {
            authorizeCOA(rec.id);
        }
    } else if (e.key === 'o' || e.key === 'O') {
        const rec = Object.values(COAS).find(c => c.rec);
        if (rec && !engagement.authorizedCOA && !engagement.objected.has(rec.id)) {
            objectCOA(rec.id);
        }
    } else if (e.key === 't' || e.key === 'T') {
        setAutoEngage(!engagement.autoEngage);
    }
});

function authorizeCOA(coaId, source) {
    if (engagement.authorizedCOA) return;
    const allocs = COA_ALLOCATIONS[coaId];
    if (!allocs) return;
    engagement.authorizedCOA = coaId;
    engagement.authorizedAt = clock.now;
    engagement.authorizedBy = source || 'OPERATOR';
    engagement.pulseUntil = clock.now + 0.8;
    let stagger = 0;
    for (const a of allocs) {
        launchSalvo(coaId, a, stagger);
        stagger += 0.15;
    }
    const kinetic = allocs.filter(a => a.kind === 'KINETIC').length;
    const directed = allocs.filter(a => a.kind === 'DIRECTED').length;
    const summary = [
        kinetic ? `${kinetic}× NGI` : null,
        directed ? `${directed}× HEL` : null,
    ].filter(Boolean).join(' + ');
    const tag = engagement.authorizedBy === 'AUTO' ? 'AUTO-AUTH' : 'COA authorized';
    const trail = engagement.authorizedBy === 'AUTO' ? ' · ROE-2 weapons-free' : '';
    CALM_LIVE.unshift(`${tag} <em>${coaId}</em> · ${summary} commit · audit logged${trail}`);
    if (CALM_LIVE.length > 14) CALM_LIVE.pop();
    lastCalmK = -2;
    lastCoaSig = '';
}

// ─── AUTO-ENGAGE toggle ────────────────────────────────────────────
function setAutoEngage(on) {
    if (engagement.autoEngage === on) return;
    engagement.autoEngage = on;
    const btn = document.getElementById('autoToggle');
    if (btn) btn.classList.toggle('auto-toggle--on', on);
    CALM_LIVE.unshift(
        on
            ? `AUTO-ENGAGE armed · ROE-2 weapons-free · operator override available`
            : `AUTO-ENGAGE disarmed · operator-in-loop restored`
    );
    if (CALM_LIVE.length > 14) CALM_LIVE.pop();
    lastCalmK = -2;
}

document.getElementById('autoToggle').addEventListener('click', () => {
    setAutoEngage(!engagement.autoEngage);
});

// Called from the frame loop. When AUTO is on and a recommended COA
// is active and we haven't already committed this cycle, authorize.
function tickAutoEngage() {
    if (!engagement.autoEngage) return;
    if (engagement.authorizedCOA) return;
    if (engagement.autoEngagedThisCycle) return;
    const t = cyclePhase();
    if (t < COA_OPEN_T || t >= COA_CLOSE_T) return;
    // ~300 ms reveal delay so the operator sees the recommendation
    // appear before the system commits.
    if (t < COA_OPEN_T + 0.3) return;
    const recommended = Object.values(COAS).find(c => c.rec);
    if (!recommended) return;
    if (engagement.objected.has(recommended.id)) return;
    engagement.autoEngagedThisCycle = true;
    authorizeCOA(recommended.id, 'AUTO');
}

function objectCOA(coaId) {
    if (engagement.authorizedCOA) return;
    engagement.objected.add(coaId);
    CALM_LIVE.unshift(`COA objected <em>${coaId}</em> · operator dissent · audit logged`);
    if (CALM_LIVE.length > 14) CALM_LIVE.pop();
    lastCalmK = -2;
    lastCoaSig = '';
    // Operator dissent overrides this cycle's AUTO-AUTH on the same COA.
    if (engagement.autoEngage) engagement.autoEngagedThisCycle = true;
}

const HYPS_BASE = [
    { name: 'Charlie-7 saturation HGV + decoy cloud', weight: 0.63 },
    { name: 'Bravo-3 probe, no follow-on',             weight: 0.24 },
    { name: 'Off-distribution / unknown',              weight: 0.13 },
];
const sparkHistory = [];
for (let i = 0; i < 32; i++) sparkHistory.push(1.0 + (Math.sin(i*0.42) + Math.cos(i*0.17)) * 0.08);

let lastHypSig = '';
function renderAdversary(t) {
    const drift = Math.sin(t * 0.5) * 0.04;
    const hyps = HYPS_BASE.map((h, i) => ({
        name: h.name,
        weight: clamp(h.weight + (i === 0 ? drift : -drift / 2), 0.04, 0.92),
        delta: (i === 0 ? drift : -drift) > 0.005 ? '↑' : (i === 0 ? drift : -drift) < -0.005 ? '↓' : '→',
    }));
    const sum = hyps.reduce((s, h) => s + h.weight, 0);
    hyps.forEach(h => h.weight /= sum);

    const sig = hyps.map(h => h.name).join('|');
    const stack = document.getElementById('hypStack');
    if (sig !== lastHypSig) {
        stack.innerHTML = hyps.map(h => `
            <div class="hyp">
                <span class="hyp__w">${Math.round(h.weight * 100)}%</span>
                <span class="hyp__n">${h.name}</span>
                <span class="hyp__d">${h.delta}</span>
                <span class="hyp__bar"><span class="hyp__bar-fill" style="width:${h.weight * 100}%"></span></span>
            </div>
        `).join('');
        lastHypSig = sig;
    } else {
        // Update only the weight text and bar widths per frame
        const rows = stack.children;
        for (let i = 0; i < rows.length && i < hyps.length; i++) {
            rows[i].children[0].textContent = `${Math.round(hyps[i].weight * 100)}%`;
            rows[i].children[2].textContent = hyps[i].delta;
            rows[i].children[3].children[0].style.width = (hyps[i].weight * 100).toFixed(1) + '%';
        }
    }

    const cost = 1.0 + 0.18 * Math.sin(t * 0.20) + 0.05 * Math.cos(t * 0.83);
    sparkHistory.push(cost);
    while (sparkHistory.length > 32) sparkHistory.shift();
    const min = Math.min(...sparkHistory);
    const max = Math.max(...sparkHistory);
    const range = Math.max(0.05, max - min);
    const sparkEl = document.getElementById('costSpark');
    if (sparkEl.children.length !== sparkHistory.length) {
        sparkEl.innerHTML = sparkHistory.map(() => '<div></div>').join('');
    }
    for (let i = 0; i < sparkHistory.length; i++) {
        const h = 15 + ((sparkHistory[i] - min) / range) * 85;
        sparkEl.children[i].style.height = h.toFixed(1) + '%';
    }
    const pct = (cost - 1.0) * 100;
    document.getElementById('costLabel').textContent =
        `COST IMPOSITION ${pct >= 0 ? '+' : ''}${pct.toFixed(0)}% ADV`;
}

const CALM_BASE = [
    'mode A → B  <em>SENSOR DEGRADED</em>',
    'track acquired <em>HGV-WRAITH-01</em>',
    'track acquired <em>HGV-WRAITH-02</em>',
    'track acquired <em>MARV-VIPER-03</em>',
    'COA proposed <em>COA-B (RECOMMENDED)</em>',
    'COA proposed <em>COA-A (alternative)</em>',
    'COA proposed <em>COA-C (alternative)</em>',
    'audit chain  <em>OK · 14 entries</em>',
];
const CALM_LIVE = CALM_BASE.slice();    // mutable; operator events unshift here
let lastCalmK = -1;
function renderCalm() {
    const k = Math.floor(clock.now * 0.4) % CALM_LIVE.length;
    if (k === lastCalmK) return;
    lastCalmK = k;
    const ordered = CALM_LIVE.slice(k).concat(CALM_LIVE.slice(0, k));
    document.getElementById('calmList').innerHTML = ordered.map(s => `<span>${s}</span>`).join('');
}

// ─── Weapons bay state — magazines drop when COA-B is authorized ─────
const BAY_BASE = {
    'NGI':   { count: 22,  max: 25,  fmt: (v) => String(v) },
    'SM-3':  { count: 48,  max: 50,  fmt: (v) => String(v) },
    'PAC-3': { count: 320, max: 320, fmt: (v) => String(v) },
    'HEL':   { count: 1.2, max: 1.5, fmt: (v) => v.toFixed(1) + ' MJ' },
};
let lastBayState = '';
function renderBay() {
    const t = cyclePhase();
    const authorized = (t >= 14 && t < 24);    // COA-B authorize → restore at end of cycle
    const firing     = (t >= 14 && t < 17);    // brief firing window
    const ngiCount   = BAY_BASE['NGI'].count - (authorized ? 2 : 0);
    const helEnergy  = BAY_BASE['HEL'].count - (authorized ? 0.4 : 0);
    const values = {
        'NGI':   ngiCount,
        'SM-3':  BAY_BASE['SM-3'].count,
        'PAC-3': BAY_BASE['PAC-3'].count,
        'HEL':   helEnergy,
    };
    const sig = `${authorized}|${firing}|${ngiCount.toFixed(2)}|${helEnergy.toFixed(2)}`;
    if (sig === lastBayState) return;
    lastBayState = sig;

    for (const id of Object.keys(BAY_BASE)) {
        const slot = document.querySelector(`.bay__slot[data-eff="${id}"]`);
        if (!slot) continue;
        const base = BAY_BASE[id];
        const v = values[id];
        slot.querySelector('.bay__count').textContent = base.fmt(v);
        slot.querySelector('.bay__bar-fill').style.width = ((v / base.max) * 100).toFixed(1) + '%';
        slot.classList.remove('bay__slot--depleted', 'bay__slot--firing');
        if (firing && (id === 'NGI' || id === 'HEL')) {
            slot.classList.add('bay__slot--firing');
        } else if (authorized && id === 'NGI') {
            slot.classList.add('bay__slot--depleted');
        }
    }
}

function renderStats() {
    const t = cyclePhase();
    const engaging = (t >= 8 && t < 21) ? ENGAGEMENT_ALLOC.length : 0;
    document.getElementById('stEng').textContent = `${engaging} / ${TRACKS.length}`;
    let primaryTTI = null;
    for (const a of ENGAGEMENT_ALLOC) {
        if (a.target !== 'HGV-WRAITH-01') continue;
        const def = findDefender(a.defender);
        const tr  = findTrack(a.target);
        if (!def || !tr) continue;
        const { tti } = predictIntercept(tr, def, a.speed);
        if (primaryTTI === null || tti < primaryTTI) primaryTTI = tti;
    }
    const ttiEl = document.getElementById('stTTI');
    if (primaryTTI === null) {
        ttiEl.textContent = '—';
        ttiEl.className = 'stats__v';
    } else {
        ttiEl.textContent = `${primaryTTI.toFixed(1)} s`;
        ttiEl.className = primaryTTI < 4 ? 'stats__v stats__v--warn' : 'stats__v stats__v--ok';
    }
}

// ═════════════════════════════════════════════════════════════════════
//   FRAME LOOP
//   Logical updates run on a fixed 16.67ms step so trajectory motion is
//   independent of refresh rate. Rendering follows requestAnimationFrame.
// ═════════════════════════════════════════════════════════════════════
const FIXED_STEP = 1 / 60;        // 60 Hz logical
let lastTs = performance.now();
let accum = 0;
let trailAccum = 0;

function frame(ts) {
    let dt = (ts - lastTs) / 1000;
    lastTs = ts;
    if (dt > 0.25) dt = 0.25;     // clamp on long pauses
    accum += dt;

    while (accum >= FIXED_STEP) {
        clock.tick(FIXED_STEP);
        cam.tick(FIXED_STEP);
        tickSalvos(FIXED_STEP);
        tickAutoEngage();
        // Auto-reset the engagement when the demo cycle wraps around.
        if (engagement.authorizedCOA && (clock.now - engagement.authorizedAt) > 10) {
            resetEngagement();
        }
        trailAccum += FIXED_STEP;
        if (trailAccum >= 1 / 30) {
            pushTrailSamples();
            trailAccum -= 1 / 30;
        }
        accum -= FIXED_STEP;
    }

    proj.tick();

    // Draw — back to front
    drawSky();
    drawStars();
    drawRadialSpokes();
    drawRangeRings();
    drawSensorCoverage();
    drawImpactPredictions();
    drawAssets();
    drawCompass();
    drawDefenderBatteries();
    drawTrails();
    drawEngagementAllocations();
    drawSalvos();
    drawTracks();
    drawSplashes();
    drawCompassTape();
    drawRadarSweep();
    drawScanlines();
    positionCallouts();

    const t = cyclePhase();
    renderHUD(t);
    renderDecisions(t);
    renderAdversary(clock.now);
    renderStats();
    renderBay();
    renderCalm();

    requestAnimationFrame(frame);
}
requestAnimationFrame(frame);

// ═════════════════════════════════════════════════════════════════════
//   HARNESS — exposes clock control for automated visual verification.
// ═════════════════════════════════════════════════════════════════════
window.__chaos = {
    freezeAt: (sec) => { clock.freeze(sec); cam.angleRate = 0; },
    unfreeze: () => { clock.unfreeze(); cam.angleRate = 0.018; },
    setCameraAngle: (rad) => { cam.angle = rad; cam.angleRate = 0; },
    clock: () => clock.now,
};
})();
</script>
</body>
</html>
"""


def build_router() -> APIRouter:
    """Return a router that mounts `/battlespace` on the dashboard app."""
    router = APIRouter()

    @router.get("/battlespace", response_class=HTMLResponse)
    def battlespace() -> str:
        return _BATTLESPACE_HTML.replace("__VERSION__", __version__)

    return router
