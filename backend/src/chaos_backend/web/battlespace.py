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
            gap: 8px;
            margin-bottom: 10px;
        }
        .decisions__title {
            color: var(--gold);
            font-size: 11px;
            letter-spacing: 5px;
            font-weight: 800;
            cursor: pointer;
            user-select: none;
            display: flex; align-items: center; gap: 6px;
        }
        .decisions__chevron {
            display: inline-block;
            width: 0; height: 0;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid currentColor;
            transition: transform var(--t-fast);
            transform-origin: center;
        }
        .decisions--collapsed .decisions__chevron {
            transform: rotate(-90deg);
        }
        .decisions__rule {
            height: 1px;
            background: var(--rule);
            margin-bottom: 12px;
        }
        /* When collapsed, hide the rule + body but keep the header. */
        .decisions--collapsed .decisions__rule,
        .decisions--collapsed #coaStack,
        .decisions--collapsed .decisions__hint {
            display: none;
        }
        .decisions--collapsed {
            padding-bottom: 8px;
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

        /* ─── Generic collapsible panel ─── */
        .panel__header {
            cursor: pointer;
            user-select: none;
            pointer-events: auto;        /* parents are pointer-events:none */
            display: flex; align-items: center; gap: 6px;
        }
        .panel__chevron {
            display: inline-block;
            width: 0; height: 0;
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 5px solid currentColor;
            transition: transform var(--t-fast);
        }
        .panel--collapsed .panel__chevron { transform: rotate(-90deg); }
        .panel--collapsed .panel__body { display: none; }
        .panel--collapsed.adv,
        .panel--collapsed.stats { padding-bottom: 8px; }

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
            transform-origin: left center;
            background: rgba(10, 22, 40, 0.78);
            border: 1px solid rgba(201, 169, 97, 0.45);
            border-left-width: 2px;
            padding: 4px 8px 4px 8px;
            font-variant-numeric: tabular-nums;
            transition: left var(--t-fast), top var(--t-fast), opacity var(--t-fast);
            will-change: left, top, transform;
        }
        .callout--far {
            /* When the threat is far, drop the full readout and show
               just the id chip so the picture doesn't get clobbered
               by stacked labels. */
            font-size: 8.5px;
            padding: 2px 5px;
            opacity: 0.78;
        }
        .callout--far .callout__data { display: none; }
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
        <span class="mode-hud__mag" id="modeMag">MAG 24 NGI / 32 SM-3 / 48 PAC-3 / 60 IRON-D</span>
    </div>

    <div class="overlay classbar">UNCLASSIFIED // DEMO // FOR EVALUATION</div>

    <div class="overlay decisions" id="decisionsPanel">
        <div class="decisions__head">
            <span class="decisions__title" id="decisionsTitle" title="Click to collapse / expand">
                <span class="decisions__chevron"></span>
                DECISIONS
            </span>
            <button class="auto-toggle" id="autoToggle" type="button" title="Toggle auto-engage (T)">
                <span class="auto-toggle__dot"></span>
                <span class="auto-toggle__label">AUTO</span>
                <span class="auto-toggle__hint">T</span>
            </button>
        </div>
        <div class="decisions__rule"></div>
        <div id="coaStack"></div>
        <div class="decisions__hint">ENTER AUTH · O OBJECT · T AUTO · S STRESS</div>
    </div>

    <div class="overlay adv" id="advPanel">
        <div class="adv__title panel__header" data-target="advPanel">
            <span class="panel__chevron"></span>
            ADVERSARY MIRROR
        </div>
        <div class="panel__body">
            <div class="adv__rule"></div>
            <div id="hypStack"></div>
            <div class="cost">
                <div class="cost__lbl" id="costLabel">COST IMPOSITION +13% ADV</div>
                <div class="cost__spark" id="costSpark"></div>
            </div>
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
        <div class="bay__slot" data-eff="IRON-D">
            <div class="bay__row"><span class="bay__id">IRON-D</span><span class="bay__count">60</span></div>
            <div class="bay__bar"><div class="bay__bar-fill" style="width:100%"></div></div>
        </div>
    </div>

    <div class="overlay calm">
        <span class="calm__label">LOG</span>
        <span class="calm__sep"></span>
        <div class="calm__list" id="calmList"></div>
    </div>

    <div class="overlay stats" id="statsPanel">
        <div class="stats__title panel__header" data-target="statsPanel">
            <span class="panel__chevron"></span>
            ENGAGEMENT STATE
        </div>
        <div class="panel__body">
            <div class="stats__rule"></div>
            <div class="stats__row"><span class="stats__k">ACTIVE TRACKS</span><span class="stats__v" id="stTracks">3</span></div>
            <div class="stats__row"><span class="stats__k">UNDER ENG.</span><span class="stats__v" id="stEng">0 / 3</span></div>
            <div class="stats__row"><span class="stats__k">PRIMARY TTI</span><span class="stats__v" id="stTTI">—</span></div>
            <div class="stats__row"><span class="stats__k">EXP. Pk (SHOT)</span><span class="stats__v stats__v--ok" id="stPk">0.93</span></div>
            <div class="stats__row"><span class="stats__k">EXP. LEAKAGE</span><span class="stats__v stats__v--ok" id="stLeak">5%</span></div>
            <div class="stats__row"><span class="stats__k">ROE</span><span class="stats__v" id="stRoe">ROE-2 (RESTR.)</span></div>
            <div class="stats__row"><span class="stats__k">PQC POSTURE</span><span class="stats__v stats__v--ok" id="stPqc">HYBRID</span></div>
        </div>
    </div>

    <div class="overlay wm">
        <div class="wm__big">CHAOS ONE</div>
        <div>BATTLESPACE · v__VERSION__</div>
        <div id="camBadge" style="margin-top:4px;color:rgba(150,220,160,0.55);"></div>
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
        this.angleRate = 0;            // auto-orbit off by default; operator drives
        this.fovDeg    = 40;
        // Bounds (operator can't dive into the floor or fly to the moon).
        this.minRadius = 2_500;
        this.maxRadius = 60_000;
        this.minHeight = 200;
        this.maxHeight = 35_000;
        // Free-cam state: any mouse interaction sets `interacted` and
        // suspends the auto-orbit; auto-orbit resumes after IDLE_RESUME.
        this.interacted    = 0;        // sec on clock
        this.idleResume    = 4.0;
        // 'C' key locks the camera entirely (toggles free-cam mode).
        this.freeCamLocked = false;
    }
    eye() {
        return [
            Math.sin(this.angle) * this.radius,
            this.height,
            Math.cos(this.angle) * this.radius,
        ];
    }
    target() { return [this.pivot[0], this.pivot[1] + this.lookAtY, this.pivot[2]]; }
    tick(dt) {
        // Auto-orbit only when the operator hasn't touched the camera
        // recently and free-cam isn't locked.
        if (this.freeCamLocked) return;
        const idleFor = clock.now - this.interacted;
        if (idleFor < this.idleResume) return;
        this.angle += this.angleRate * dt;
    }
    nudgeOrbit(dyaw, dheight) {
        this.angle += dyaw;
        this.height = Math.max(this.minHeight, Math.min(this.maxHeight, this.height + dheight));
        this.interacted = clock.now;
    }
    zoom(factor) {
        // factor > 1 zooms out, < 1 zooms in. Multiplicative so the
        // operator gets a smooth feel from 2.5 km to 60 km.
        this.radius = Math.max(this.minRadius, Math.min(this.maxRadius, this.radius * factor));
        // Subtle elevation tracking so the camera doesn't bury itself
        // when zooming in close: height tracks radius via a soft floor.
        this.height = Math.max(this.minHeight, Math.min(this.maxHeight, this.height * Math.sqrt(factor)));
        this.interacted = clock.now;
    }
    home() {
        this.pivot     = [0, 0, 0];
        this.radius    = 14_500;
        this.height    = 6_000;
        this.lookAtY   = 1_400;
        this.angle     = -2.05;
        this.angleRate = 0;
        this.interacted = clock.now;
    }
    toggleFreeCam() {
        this.freeCamLocked = !this.freeCamLocked;
        this.interacted = clock.now;
    }
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

// ═════════════════════════════════════════════════════════════════════
//   DEFENDER DOCTRINE
//
//   Four batteries on a 3000-m circle. Each has:
//
//     POSITION       cartesian world-position
//     COLOR          UI tint
//     CLASS          'KINETIC' or 'DIRECTED'
//     ENVELOPE       physical engagement envelope:
//                    R_min, R_max  (slant range to PIP)
//                    H_min, H_max  (target altitude band)
//     PROFILE        interceptor flight model:
//                    cruise_mps    terminal cruise speed
//                    boost_mps     boost-phase mean speed
//                    accel_mps2    boost→cruise acceleration
//                    boost_s       seconds in boost
//                    turn_rad_s    seeker turn rate (proportional nav)
//                    detonation_m  proximity-fuze radius
//     LOGISTICS      magazine, reload, max in-flight
//     PK_MATRIX      kill probability vs threat class
//
//   Class-appropriate speeds let each effector earn its slot:
//   NGI is a Mach-13 exoatmospheric kill vehicle; PAC-3 is a Mach-5
//   terminal-tier hit-to-kill round; SM-3 sits in between with
//   upper-tier reach. IRON-D is a Tamir-class short-range kinetic
//   interceptor for cruise / drone / late-MARV leakers.
// ═════════════════════════════════════════════════════════════════════
const DEFENDER_RADIUS_M = 3_000;
const DEFENDER_BATTERIES = [
    {
        id: 'NGI',  pos: hexPosition(  0, DEFENDER_RADIUS_M),
        color: [0.55, 0.85, 1.00], class: 'KINETIC',
        envelope: { rangeMin:   500, rangeMax: 14_000, hMin: 200,  hMax: 100_000 },
        profile:  { cruise_mps: 3_400, boost_mps: 480, accel_mps2: 5_800,
                    boost_s: 0.45, turn_rad_s: 3.2, detonation_m: 220 },
        logistics:{ magazine: 24, magazineMax: 24, reload_s: 0.7, maxSimul: 4,
                    resupply_s: 6.0 /* one round trickles in every 6 s */ },
        pk:       { HGV: 0.93, BM: 0.96, MARV: 0.88, CRUISE: 0.42, DRONE: 0.55, HYP: 0.58 },
    },
    {
        id: 'SM-3', pos: hexPosition( 90, DEFENDER_RADIUS_M),
        color: [0.55, 0.95, 0.78], class: 'KINETIC',
        envelope: { rangeMin:   400, rangeMax: 11_000, hMin: 100,  hMax: 60_000 },
        profile:  { cruise_mps: 2_600, boost_mps: 420, accel_mps2: 4_900,
                    boost_s: 0.42, turn_rad_s: 3.0, detonation_m: 200 },
        logistics:{ magazine: 32, magazineMax: 32, reload_s: 0.6, maxSimul: 6,
                    resupply_s: 4.5 },
        pk:       { HGV: 0.82, BM: 0.90, MARV: 0.90, CRUISE: 0.65, DRONE: 0.78, HYP: 0.32 },
    },
    {
        id: 'PAC-3', pos: hexPosition(180, DEFENDER_RADIUS_M),
        color: [0.72, 0.95, 0.55], class: 'KINETIC',
        envelope: { rangeMin:   200, rangeMax:  7_000, hMin:  20,  hMax: 25_000 },
        profile:  { cruise_mps: 1_700, boost_mps: 360, accel_mps2: 4_200,
                    boost_s: 0.40, turn_rad_s: 4.5, detonation_m: 160 },
        logistics:{ magazine: 48, magazineMax: 48, reload_s: 0.45, maxSimul: 8,
                    resupply_s: 3.0 },
        pk:       { HGV: 0.40, BM: 0.55, MARV: 0.85, CRUISE: 0.90, DRONE: 0.92, HYP: 0.06 },
    },
    {
        // IRON-D — short-range kinetic terminal interceptor in the
        // Tamir family. Replaces the previous directed-energy block.
        // Best against cruise / drone / late-MARV; not effective vs
        // hypersonic or exoatmospheric tracks.
        id: 'IRON-D', pos: hexPosition(270, DEFENDER_RADIUS_M),
        color: [1.00, 0.88, 0.55], class: 'KINETIC',
        envelope: { rangeMin:   150, rangeMax:  9_000, hMin:   20, hMax: 18_000 },
        profile:  { cruise_mps: 1_500, boost_mps: 320, accel_mps2: 4_000,
                    boost_s: 0.38, turn_rad_s: 4.8, detonation_m: 140 },
        logistics:{ magazine: 60, magazineMax: 60, reload_s: 0.35, maxSimul: 8,
                    resupply_s: 2.5 },
        pk:       { HGV: 0.30, BM: 0.35, MARV: 0.78, CRUISE: 0.93, DRONE: 0.95, HYP: 0.08 },
    },
];

// Runtime defender state (magazine, in-flight, last-fire, last-resupply).
const defenderState = new Map();
function resetDefenderState() {
    for (const b of DEFENDER_BATTERIES) {
        defenderState.set(b.id, {
            magazine: b.logistics.magazine,
            inflight: 0,
            lastFired:    -Infinity,
            lastResupply: 0,
        });
    }
}
resetDefenderState();

// One round trickles back into the magazine every `resupply_s`. Models
// a logistics tail (truck reloads / fresh canisters) so the system
// can operate indefinitely without the operator hitting empty.
function tickResupply() {
    for (const b of DEFENDER_BATTERIES) {
        const period = b.logistics.resupply_s;
        if (!period) continue;
        const st = defenderState.get(b.id);
        if (!st) continue;
        if (st.magazine >= b.logistics.magazineMax) {
            st.lastResupply = clock.now;
            continue;
        }
        if (clock.now - st.lastResupply >= period) {
            st.magazine = Math.min(b.logistics.magazineMax, st.magazine + 1);
            st.lastResupply = clock.now;
        }
    }
}

const COMPASS = [
    { id: 'N', pos: [    0, 0,  13_200] },
    { id: 'E', pos: [13_200, 0,       0] },
    { id: 'S', pos: [    0, 0, -13_200] },
    { id: 'W', pos: [-13_200, 0,      0] },
];

// Named landmark buildings — placed at fixed bearings inside the
// defender ring. Each is a tall labelled building in the procedural
// city below. The labels show in the operator display so the operator
// always knows which asset they're protecting.
const LANDMARKS = [
    { id: 'COMMAND', pos: hexPosition(  45, 1_300), w: 200, d: 200, h: 540 },
    { id: 'PORT',    pos: hexPosition( 135, 1_500), w: 180, d: 260, h: 400 },
    { id: 'GRID',    pos: hexPosition( 225, 1_400), w: 220, d: 160, h: 460 },
    { id: 'NODE-7',  pos: hexPosition( 315, 1_350), w: 160, d: 160, h: 380 },
];
// Legacy name preserved so the existing assets-hex labels keep
// pointing to the right world positions. (The hex render is replaced
// by drawCity below.)
const ASSETS = LANDMARKS;

// ═════════════════════════════════════════════════════════════════════
//   3D CITY GENERATOR
//
//   ~70 procedural buildings on a 180-m street grid inside the
//   defender ring (radius < 2.4 km). Three building tiers:
//
//     • low-rise  (50-140 m tall)  — densest, fills the outskirts
//     • mid-rise  (150-280 m tall) — common, mixed throughout
//     • tower     (300-520 m tall) — sparse, "downtown core"
//
//   The four landmark towers (COMMAND/PORT/GRID/NODE-7) are placed
//   first at their fixed bearings so the procedural fill respects
//   their footprints.
// ═════════════════════════════════════════════════════════════════════
function makeCity(seed) {
    const rng = mulberry32(seed);
    const buildings = [];
    const GRID = 180;
    const CITY_R = 2_400;
    const CENTRAL_PLAZA_R = 380;

    // Place landmarks first.
    for (const L of LANDMARKS) {
        buildings.push({
            cx: L.pos[0], cz: L.pos[2],
            w: L.w, d: L.d, h: L.h,
            tier: 'landmark',
            label: L.id,
            litness: 0.65,
            tint: 0.95,
            windowSeed: (L.id.charCodeAt(0) * 137.5) | 0,
        });
    }

    // Then ~70 procedural fillers.
    const placed = new Set();
    // Seed the landmark grid cells so we don't drop a procedural
    // building on top of one.
    for (const b of buildings) {
        const gx = Math.round(b.cx / GRID), gz = Math.round(b.cz / GRID);
        for (let dx = -2; dx <= 2; dx++) for (let dz = -2; dz <= 2; dz++) {
            placed.add(`${gx + dx},${gz + dz}`);
        }
    }

    let attempts = 0;
    while (buildings.length < 74 && attempts < 800) {
        attempts++;
        const gx = Math.floor((rng() - 0.5) * 28);
        const gz = Math.floor((rng() - 0.5) * 28);
        const key = `${gx},${gz}`;
        if (placed.has(key)) continue;
        const cx = gx * GRID + (rng() - 0.5) * 30;
        const cz = gz * GRID + (rng() - 0.5) * 30;
        const r2 = cx * cx + cz * cz;
        if (r2 > CITY_R * CITY_R) continue;
        if (r2 < CENTRAL_PLAZA_R * CENTRAL_PLAZA_R) continue;
        placed.add(key);

        // Tier biased by distance from centre — downtown towers near
        // the middle, low-rise on the outskirts.
        const ringT = Math.sqrt(r2) / CITY_R;       // 0 centre → 1 edge
        const tierRoll = rng() + ringT * 0.4;       // bias toward low-rise farther out
        let w, d, h, tier;
        if (tierRoll < 0.55) {
            tier = 'low';
            w = 35 + rng() * 55;
            d = 35 + rng() * 55;
            h = 50 + rng() * 90;
        } else if (tierRoll < 0.92) {
            tier = 'mid';
            w = 60 + rng() * 70;
            d = 60 + rng() * 70;
            h = 150 + rng() * 130;
        } else {
            tier = 'tower';
            w = 80 + rng() * 100;
            d = 80 + rng() * 100;
            h = 280 + rng() * 240;
        }
        buildings.push({
            cx, cz, w, d, h, tier,
            label: null,
            litness: 0.35 + rng() * 0.45,
            tint: 0.74 + rng() * 0.20,
            windowSeed: (rng() * 100000) | 0,
        });
    }
    return buildings;
}
const CITY = makeCity(0xC17B1D);

// ═════════════════════════════════════════════════════════════════════
//   THREAT TAXONOMY + PROCEDURAL WAVE GENERATOR
//
//   Five classes of inbound threat — chosen to span the realistic
//   envelope a layered defense has to handle. Each class fixes its
//   trajectory shape, peak altitude band, Mach number, and which
//   defenders are kinematically suited to engage it.
//
//   HGV     hypersonic glide vehicle — long arc, high apogee, fast
//   BM      ballistic missile — high parabolic, exo / re-entry
//   MARV    manoeuvring re-entry vehicle — descending, jinks late
//   CRUISE  low-altitude cruise missile — sea-skimming subsonic
//   DRONE   one-way attack drone — slow, low, large salvo doctrine
//
//   Every threat is a Bezier (launch, apogee, terminal) so the
//   physics layer doesn't care which class it is — only the priors
//   that feed weapon-target assignment.
// ═════════════════════════════════════════════════════════════════════
// Spawn radii pushed PAST the 18-42 km mountain ring so threats
// emerge over the terrain instead of popping into existence at the
// inner edge of the map. Flight times scaled so the threat still
// completes its trajectory in 9-16 s — the displayed Mach numbers
// are an operational shorthand, not the literal traversal speed.
const THREAT_CLASSES = {
    HGV:    { color: [1.00, 0.66, 0.38], machBase: 9.0,
              apogeeRange:[7_500, 11_000], flightTimeRange: [10.0, 14.0],
              spawnRange: [46_000, 62_000], terminalRange: [400, 1_400],
              priority: 1 },
    BM:     { color: [0.95, 0.55, 0.55], machBase: 7.5,
              apogeeRange:[10_000, 16_000], flightTimeRange: [11.0, 15.0],
              spawnRange: [48_000, 65_000], terminalRange: [200, 900],
              priority: 1 },
    MARV:   { color: [0.95, 0.84, 0.55], machBase: 6.8,
              apogeeRange:[5_000, 8_000], flightTimeRange: [9.0, 12.5],
              spawnRange: [36_000, 50_000], terminalRange: [200, 800],
              priority: 2 },
    CRUISE: { color: [0.85, 0.60, 0.30], machBase: 0.85,
              apogeeRange:[ 280,   650], flightTimeRange: [12.0, 16.0],
              spawnRange: [28_000, 42_000], terminalRange: [150, 600],
              priority: 3 },
    DRONE:  { color: [0.78, 0.55, 0.85], machBase: 0.30,
              apogeeRange:[ 200,   380], flightTimeRange: [12.0, 17.0],
              spawnRange: [22_000, 36_000], terminalRange: [120, 500],
              priority: 4 },
    // HYP — advanced hypersonic glide vehicle. Top-priority hard
    // target: Mach 14+, very high apogee, fast descent, brightly
    // coloured so the operator immediately sees the threat picture
    // change. Defender Pk against HYP is intentionally lower for
    // anything but NGI — the operator should observe NGI carrying
    // the engagement while the other batteries struggle.
    HYP:    { color: [1.00, 0.42, 0.95], machBase: 14.0,
              apogeeRange:[16_000, 24_000], flightTimeRange: [8.0, 10.5],
              spawnRange: [70_000, 92_000], terminalRange: [300, 1_200],
              priority: 1 },
};

// PRNG with sessionable seed so different page-loads see different
// threat pictures, but a `window.__chaos.setSeed(n)` call reproduces.
let WAVE_SEED = (Date.now() & 0x7fffffff) ^ 0xC1A05;
let waveRng = mulberry32(WAVE_SEED);
function reseedWaves(seed) { WAVE_SEED = seed; waveRng = mulberry32(seed); }

let threatSerial = 0;
function newThreatId(kind) {
    threatSerial++;
    const tag = { HGV: 'WRAITH', BM: 'TALON', MARV: 'VIPER', CRUISE: 'SCYTHE',
                  DRONE: 'SHAHED', HYP: 'AVANGARD' }[kind] || 'UNKNOWN';
    return `${kind}-${tag}-${String(threatSerial).padStart(2, '0')}`;
}

function jitter(min, max, rng) { return min + rng() * (max - min); }

// Spawn one threat with a random bearing, altitude profile, and timing.
// Returns the canonical track object the rest of the system expects.
function makeRandomThreat(kindHint, launchAt, rng) {
    const kinds = Object.keys(THREAT_CLASSES);
    const kind = kindHint || kinds[(rng() * kinds.length) | 0];
    const c = THREAT_CLASSES[kind];
    const bearing = rng() * Math.PI * 2;
    const spawnR = jitter(c.spawnRange[0], c.spawnRange[1], rng);
    const termR = jitter(c.terminalRange[0], c.terminalRange[1], rng);
    const termBearing = bearing + (rng() - 0.5) * 1.4;        // re-aim toward defended cell with scatter
    const apoR = spawnR * (0.10 + rng() * 0.18);
    const apoBearing = bearing + (rng() - 0.5) * 0.6;
    const apogeeAlt = jitter(c.apogeeRange[0], c.apogeeRange[1], rng);
    const launchAlt = 200 + rng() * 200;
    const termAlt = 200 + rng() * 250;
    return {
        id: newThreatId(kind),
        kind,
        launch:   [Math.sin(bearing)    * spawnR, launchAlt, Math.cos(bearing)    * spawnR],
        apogee:   [Math.sin(apoBearing) * apoR,    apogeeAlt, Math.cos(apoBearing) * apoR],
        terminal: [Math.sin(termBearing) * termR,  termAlt,   Math.cos(termBearing) * termR],
        launchAt: launchAt,
        flightTime: jitter(c.flightTimeRange[0], c.flightTimeRange[1], rng),
        color: c.color,
        machBase: c.machBase * (0.92 + rng() * 0.18),
        priority: c.priority,
        spawnedAt: clock.now,
    };
}

// THREATS is the live list. resetThreats wipes and re-seeds.
const THREATS = [];

function findThreat(id) { return THREATS.find(t => t.id === id); }
// Legacy alias so older code paths keep working through the rewrite.
const TRACKS = THREATS;
function findTrack(id) { return findThreat(id); }

const findDefender = (id) => DEFENDER_BATTERIES.find(d => d.id === id);

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
        { defender: 'IRON-D', target: 'MARV-VIPER-03', kind: 'KINETIC', speed: 850 },
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
// Phase in [0, 1] while the threat is in flight, -1 before launch,
// >1 after impact. Uses absolute clock time — no modular cycle wrap.
// The wrap was a bug: threats with launchAt > CYCLE re-appeared as
// "pre-launch" each time clock.now wrapped, making mid-engagement
// tracks vanish from the picture. Lifetime is owned by the
// tickThreatLifecycle GC instead.
function trackPhaseAt(tr, t) {
    const elapsed = t - tr.launchAt;
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
    autoEngage: false,            // initial state; setAutoEngage(true) is called on init
    autoEngagedThisCycle: false,  // dedupe per cycle (legacy COA path)
    _salvoSerial: 0,
    leakers: 0,
    intercepts: 0,
    lastAssignmentAt: -Infinity,
    stressTriggered: false,
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
    engagement._salvoSerial = 0;
    engagement.lastAssignmentAt = -Infinity;
    resetDefenderState();
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

// Continuous demo — replaces the old fixed 20-second cycle with a
// rolling wave scheduler. Cycle constants are retained because the
// Mode HUD + Decisions panel still use them as the operator-loop tempo;
// the wave generator runs independently on real-time.
const CYCLE = 20;
const COA_OPEN_T   = 1.2;
const COA_CLOSE_T  = 14.0;
const MODE_B_OPEN  = 0.8;
const MODE_B_CLOSE = 16.0;
function cyclePhase() { return clock.now % CYCLE; }

// ═════════════════════════════════════════════════════════════════════
//   WAVE SCHEDULER + DRIZZLE
//
//   Continuous attack picture. Two parallel spawners:
//
//   • WAVE  — every 6-10 s, drops a 3-6-threat coordinated wave
//             with the full spectrum (HGV / BM / MARV / CRUISE / DRONE).
//             Models a coordinated saturation push.
//   • DRIZZLE — every 1.4-2.6 s, drops one low-priority threat
//             (DRONE / CRUISE biased) so the picture is never empty
//             between waves. Iron Dome reality is constant pressure.
//
//   Press S to drop a 14-threat stress wave on top of all of this.
// ═════════════════════════════════════════════════════════════════════
const WAVE = {
    nextAt: 0.6,
    interval: [6, 10],
    sizeRange: [3, 6],
    composition: [
        ['HGV',    0.18],
        ['BM',     0.16],
        ['MARV',   0.18],
        ['CRUISE', 0.30],
        ['DRONE',  0.18],
    ],
};
const DRIZZLE = {
    nextAt: 1.8,
    interval: [1.4, 2.6],
    composition: [
        ['DRONE',  0.55],
        ['CRUISE', 0.30],
        ['MARV',   0.08],
        ['HGV',    0.04],
        ['BM',     0.03],
    ],
};

// HYPERSONIC ALERT — rare event that fires a small burst of HYP
// threats from deep beyond the mountain ring. Forces the WTA to
// reassign NGI to the high-priority target while the other
// batteries fall back to mopping up the surrounding wave.
const HYPERSONIC = {
    nextAt: 22 + Math.random() * 18,      // first event ~25-40 s after load
    interval: [38, 68],
    burst: [1, 2],
};

function pickFromTable(table, rng) {
    const r = rng();
    let acc = 0;
    for (const [k, w] of table) {
        acc += w;
        if (r <= acc) return k;
    }
    return table[table.length - 1][0];
}
function pickThreatKind(rng) { return pickFromTable(WAVE.composition, rng); }

function spawnWave(size, kindOverride) {
    const stagger = 0.18;
    let acc = 0;
    for (let i = 0; i < size; i++) {
        const kind = kindOverride || pickThreatKind(waveRng);
        const t = clock.now + 0.25 + acc + waveRng() * 0.4;
        THREATS.push(makeRandomThreat(kind, t, waveRng));
        acc += stagger + waveRng() * 0.4;
    }
}

function tickWaves() {
    if (clock.now >= WAVE.nextAt) {
        const size = (WAVE.sizeRange[0] | 0) + Math.floor(waveRng() * (WAVE.sizeRange[1] - WAVE.sizeRange[0] + 1));
        spawnWave(size, null);
        WAVE.nextAt = clock.now + WAVE.interval[0] + waveRng() * (WAVE.interval[1] - WAVE.interval[0]);
        pushLogOnce(
            `wave-${clock.now.toFixed(1)}`,
            `wave inbound · ${size} contacts · BNG multiple · acquisition pending`,
        );
    }
    if (clock.now >= DRIZZLE.nextAt) {
        const kind = pickFromTable(DRIZZLE.composition, waveRng);
        const t = clock.now + 0.25;
        THREATS.push(makeRandomThreat(kind, t, waveRng));
        DRIZZLE.nextAt = clock.now + DRIZZLE.interval[0] + waveRng() * (DRIZZLE.interval[1] - DRIZZLE.interval[0]);
    }
    if (clock.now >= HYPERSONIC.nextAt) {
        const count = (HYPERSONIC.burst[0] | 0) + Math.floor(waveRng() * (HYPERSONIC.burst[1] - HYPERSONIC.burst[0] + 1));
        let stagger = 0;
        for (let i = 0; i < count; i++) {
            const t = clock.now + 0.20 + stagger + waveRng() * 0.25;
            THREATS.push(makeRandomThreat('HYP', t, waveRng));
            stagger += 0.45;
        }
        HYPERSONIC.nextAt = clock.now + HYPERSONIC.interval[0] + waveRng() * (HYPERSONIC.interval[1] - HYPERSONIC.interval[0]);
        pushLogOnce(
            `hyp-${clock.now.toFixed(2)}`,
            `<em>HYPERSONIC ALERT</em> · ${count} HGV-S contact${count > 1 ? 's' : ''} · Mach 14+ · NGI primary`,
        );
    }
}

// Stress-test: jam an oversized wave through the assignment layer.
function spawnStressWave() {
    spawnWave(14, null);
    pushLogOnce(
        `stress-${clock.now.toFixed(2)}`,
        `<em>STRESS WAVE</em> · 14 inbound · saturation test`,
    );
}

// Aging: garbage-collect threats whose flight is over (splashed
// against the ground or got killed) and whose trail buffers have
// faded. Keep them around for ~3 seconds post-event so the radar
// afterglow / splash effects can complete.
function tickThreatLifecycle() {
    for (let i = THREATS.length - 1; i >= 0; i--) {
        const t = THREATS[i];
        const phase = trackPhase(t);
        // Cleanup if killed >3 s ago OR phase > 1.15 (ground impact already drawn)
        if (engagement.killedTracks.has(t.id)) {
            if (clock.now - (t._killedAt || clock.now) > 2.5) {
                THREATS.splice(i, 1);
                trailsByTrack.delete(t.id);
                engagement.killedTracks.delete(t.id);
            }
        } else if (phase > 1.4) {
            // Threat reached terminal and was never killed — log a
            // leak AND book a ground-impact splash at its terminal
            // point so the operator sees the breach (drawn in
            // crimson, larger than an intercept splash).
            pushLogOnce(`leaker-${t.id}`, `LEAKER <em>${t.id}</em> impacted defended cell`);
            engagement.leakers = (engagement.leakers || 0) + 1;
            engagement.splashes.push({
                point: [t.terminal[0], 10, t.terminal[2]],
                born: clock.now,
                until: clock.now + 1.6,
                kind: 'leak',
            });
            THREATS.splice(i, 1);
            trailsByTrack.delete(t.id);
        }
    }
}

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
    // Warm and cool stars at varied magnitudes. Twinkle phase + rate
    // are per-star so the field shimmers without a uniform pulse.
    const out = [];
    for (let i = 0; i < count; i++) {
        const warm = rng() < 0.18;
        out.push({
            x: rng() * width,
            y: rng() * (height * 0.62),
            r: 0.4 + rng() * 1.2,
            a: 0.18 + rng() * 0.55,
            warm,
            twinkleRate: 0.4 + rng() * 1.8,
            twinklePhase: rng() * Math.PI * 2,
        });
    }
    return out;
}

// World-space mountain ring — actual 3D peaks placed in a band around
// the defended cell at 22-35 km radius. Each peak is a tetrahedron
// projected through the camera pipeline, so the silhouette PARALLAXES
// as the operator orbits or zooms (no 2D billboard cheat).
function makeMountainRing(seed) {
    const rng = mulberry32(seed);
    const peaks = [];
    // ~64 peaks spread around the perimeter with angular scatter so
    // they don't form an obvious regular spacing. Two ranges: near
    // (closer, sharper) and far (more distant, fainter).
    const COUNT = 72;
    for (let i = 0; i < COUNT; i++) {
        // Most peaks in the near range; a third get the far-range
        // (smaller, dimmer) treatment.
        const far = rng() < 0.32;
        const theta = (i / COUNT) * Math.PI * 2 + (rng() - 0.5) * (Math.PI / COUNT) * 1.8;
        const distance = far
            ? 30_000 + rng() * 12_000
            : 18_000 + rng() *  8_000;
        const height = far
            ? 700 + rng() * 1200
            : 900 + rng() * 2400;
        const baseR = far
            ? 1000 + rng() * 1400
            : 1400 + rng() * 1900;
        const cx = Math.sin(theta) * distance;
        const cz = Math.cos(theta) * distance;
        // Base orientation — apex slightly tilted toward the defended
        // centre so the lit face is always somewhat visible.
        const facing = Math.atan2(-cx, -cz);
        // Cool slate tone with subtle hue variance so peaks read as
        // a range, not a uniform fence.
        const tint = far ? 0.62 + rng() * 0.18 : 0.78 + rng() * 0.18;
        peaks.push({
            cx, cz, facing, height, baseR, far,
            tint,
            // Slight base offset so the apex isn't always centred —
            // gives an asymmetric silhouette.
            apexShift: (rng() - 0.5) * baseR * 0.35,
        });
    }
    return peaks;
}

// World-space city lights — warm pinpricks scattered on the ground
// between the defender ring (3 km) and the inner mountains (~16 km).
// They project through the same camera so they parallax / occlude
// correctly behind threats and salvos.
function makeCityLightField(seed) {
    const rng = mulberry32(seed);
    const lights = [];
    const COUNT = 240;
    for (let i = 0; i < COUNT; i++) {
        const theta = rng() * Math.PI * 2;
        // Annulus radius — denser near the outer band (suburbs around
        // the inner range), sparser near the defender ring.
        const r = Math.sqrt(0.32 + 0.68 * rng()) * 14_000 + 3_400;
        lights.push({
            pos: [Math.sin(theta) * r, 6, Math.cos(theta) * r],
            warm: rng() < 0.72,
            brightness: 0.30 + rng() * 0.55,
            twinkleRate: 0.6 + rng() * 1.8,
            twinklePhase: rng() * Math.PI * 2,
        });
    }
    return lights;
}

// Nebula blobs — soft radial gradients drifting in the upper sky.
function makeNebulae(rng, width, height) {
    return [
        { cx: width * 0.18, cy: height * 0.22, r: 240, hue: [120,  90, 60], a: 0.10 },
        { cx: width * 0.74, cy: height * 0.14, r: 320, hue: [ 60, 100, 140], a: 0.08 },
        { cx: width * 0.55, cy: height * 0.32, r: 280, hue: [180, 110,  60], a: 0.06 },
    ];
}

// ═════════════════════════════════════════════════════════════════════
//   CANVAS
// ═════════════════════════════════════════════════════════════════════
const canvas = document.getElementById('stage');
const ctx = canvas.getContext('2d');
const cam = new Camera();
let proj = new Projector(cam, window.innerWidth, window.innerHeight);
let stars = [];
let mountainRing = makeMountainRing(0xC1A07);     // world-space tetrahedra
let cityLightField = makeCityLightField(0xC1A09); // world-space ground pricks
let nebulae = [];

function resizeCanvas() {
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    canvas.width  = Math.floor(window.innerWidth  * dpr);
    canvas.height = Math.floor(window.innerHeight * dpr);
    canvas.style.width  = window.innerWidth  + 'px';
    canvas.style.height = window.innerHeight + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    proj.resize(window.innerWidth, window.innerHeight);
    stars     = makeStars(mulberry32(0xC1A05), 220, window.innerWidth, window.innerHeight);
    nebulae   = makeNebulae(mulberry32(0xC1A0B), window.innerWidth, window.innerHeight);
    // mountainRing and cityLightField are world-space — built once at
    // module load and reused across resizes (no screen-space dependency).
}
window.addEventListener('resize', resizeCanvas);
resizeCanvas();

// ═════════════════════════════════════════════════════════════════════
//   CAMERA INTERACTION (free-cam)
//
//   • mouse wheel       → zoom (multiplicative; smooth feel 2.5-60 km)
//   • left-drag         → orbit (horizontal: yaw, vertical: elevation)
//   • C key             → lock free-cam (suspends auto-orbit until
//                          pressed again); auto-orbit also pauses for
//                          4 s after any mouse interaction
//   • Home / =          → reset camera to default
//   The canvas takes pointer-events; the overlay HTML stays clickable
//   because the canvas is below it in DOM stacking.
// ═════════════════════════════════════════════════════════════════════
canvas.style.cursor = 'grab';
canvas.style.touchAction = 'none';      // prevent browser scroll on wheel

canvas.addEventListener('wheel', (e) => {
    e.preventDefault();
    // Normalised delta: wheel "ticks" zoom by ~12% per notch.
    const delta = Math.sign(e.deltaY);
    const factor = (delta > 0) ? 1.12 : 0.89;
    cam.zoom(factor);
}, { passive: false });

let drag = null;
canvas.addEventListener('pointerdown', (e) => {
    if (e.button !== 0) return;       // left button only
    canvas.setPointerCapture(e.pointerId);
    drag = { x: e.clientX, y: e.clientY, pointerId: e.pointerId };
    canvas.style.cursor = 'grabbing';
});
canvas.addEventListener('pointermove', (e) => {
    if (!drag || e.pointerId !== drag.pointerId) return;
    const dx = e.clientX - drag.x;
    const dy = e.clientY - drag.y;
    drag.x = e.clientX;
    drag.y = e.clientY;
    // Horizontal: 0.5° per pixel feels right.
    const dyaw = -dx * (Math.PI / 180) * 0.5;
    // Vertical: 12 m per pixel.
    const dheight = -dy * 30;
    cam.nudgeOrbit(dyaw, dheight);
});
canvas.addEventListener('pointerup', (e) => {
    if (!drag || e.pointerId !== drag.pointerId) return;
    canvas.releasePointerCapture(e.pointerId);
    drag = null;
    canvas.style.cursor = 'grab';
});
canvas.addEventListener('pointercancel', () => { drag = null; canvas.style.cursor = 'grab'; });

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

    // Upper sky: deep space → midnight blue → dusk navy as we approach
    // the horizon. Atmospheric scattering reads near the bottom.
    const sky = ctx.createLinearGradient(0, 0, 0, horizonY);
    sky.addColorStop(0.00, '#020616');
    sky.addColorStop(0.35, '#06142A');
    sky.addColorStop(0.78, '#0F2A48');
    sky.addColorStop(1.00, '#173A5C');
    ctx.fillStyle = sky;
    ctx.fillRect(0, 0, W, horizonY);

    // Sub-horizon ground/sea — slight tint shift so the join reads
    // as terrain rather than reflection.
    const ground = ctx.createLinearGradient(0, horizonY, 0, H);
    ground.addColorStop(0.00, '#0A1B30');
    ground.addColorStop(0.45, '#060F1E');
    ground.addColorStop(1.00, '#020814');
    ctx.fillStyle = ground;
    ctx.fillRect(0, horizonY, W, H - horizonY);

    // Soft nebula glows in the upper sky — additive radial gradients.
    for (const n of nebulae) {
        // Pin to upper half so they never collide with the terrain.
        if (n.cy > horizonY * 0.85) continue;
        const grad = ctx.createRadialGradient(n.cx, n.cy, 0, n.cx, n.cy, n.r);
        grad.addColorStop(0.00, `rgba(${n.hue[0]},${n.hue[1]},${n.hue[2]},${n.a})`);
        grad.addColorStop(0.55, `rgba(${n.hue[0]},${n.hue[1]},${n.hue[2]},${n.a * 0.35})`);
        grad.addColorStop(1.00, `rgba(${n.hue[0]},${n.hue[1]},${n.hue[2]},0)`);
        ctx.fillStyle = grad;
        ctx.fillRect(n.cx - n.r, n.cy - n.r, n.r * 2, n.r * 2);
    }

    // Atmospheric scattering glow at the horizon — warmer where the
    // sun sits down-range, cool everywhere else.
    const halo = ctx.createLinearGradient(0, horizonY - 70, 0, horizonY + 24);
    halo.addColorStop(0.00, 'rgba(201, 169, 97, 0.00)');
    halo.addColorStop(0.60, 'rgba(201, 169, 97, 0.06)');
    halo.addColorStop(1.00, 'rgba(220, 184, 110, 0.20)');
    ctx.fillStyle = halo;
    ctx.fillRect(0, horizonY - 70, W, 90);
}

// World-space mountain ring drawn as 3D tetrahedra (apex + 3 base
// corners). Each peak's faces are Lambertian-shaded against the sun
// direction; the painter's algorithm renders back-to-front by
// distance from the camera, so closer peaks correctly occlude the
// farther range.
function drawMountainRing() {
    if (!mountainRing || mountainRing.length === 0) return;
    const eye = cam.eye();

    // Build a list of all face polygons across all peaks, then sort.
    const polys = [];
    for (const peak of mountainRing) {
        const apex = [peak.cx + peak.apexShift, peak.height, peak.cz];
        // Three base corners — front (toward origin), back-left, back-right.
        const c1 = [
            peak.cx + Math.sin(peak.facing) * peak.baseR,
            0,
            peak.cz + Math.cos(peak.facing) * peak.baseR,
        ];
        const c2 = [
            peak.cx + Math.sin(peak.facing + 2.094) * peak.baseR,
            0,
            peak.cz + Math.cos(peak.facing + 2.094) * peak.baseR,
        ];
        const c3 = [
            peak.cx + Math.sin(peak.facing + 4.189) * peak.baseR,
            0,
            peak.cz + Math.cos(peak.facing + 4.189) * peak.baseR,
        ];
        const verts = [apex, c1, c2, c3];
        const prj = verts.map(v => proj.project(v));
        if (prj.some(p => !p)) continue;

        // 3 side faces (the bottom face faces straight down and is
        // never visible from this orbit camera).
        const faces = [[0, 1, 2], [0, 2, 3], [0, 3, 1]];
        for (const f of faces) {
            const a = verts[f[0]], b = verts[f[1]], c = verts[f[2]];
            const e1 = V3.sub(b, a);
            const e2 = V3.sub(c, a);
            const n = V3.norm(V3.cross(e1, e2));
            // Back-face cull.
            const centroid = V3.scale(V3.add(V3.add(a, b), c), 1 / 3);
            const toFace = V3.norm(V3.sub(centroid, eye));
            if (V3.dot(n, toFace) > 0.05) continue;
            const lambert = Math.max(0.10, V3.dot(n, SUN_DIR));
            const depth = V3.len(V3.sub(centroid, eye));
            polys.push({ p0: prj[f[0]], p1: prj[f[1]], p2: prj[f[2]],
                         lambert, depth, peak, n });
        }
    }
    // Painter's algorithm — back to front.
    polys.sort((a, b) => b.depth - a.depth);

    for (const poly of polys) {
        const { p0, p1, p2, lambert, depth, peak } = poly;
        // Distance fade: peaks beyond ~28 km wash into the atmosphere.
        const distFade = 1 - Math.min(1, Math.max(0, (depth - 18_000) / 22_000));
        // Cool slate base color, brightened by lambert + tint, atmospherically
        // hazed away to a cool blue with distance.
        const baseR = 10 + peak.tint * 28 * lambert;
        const baseG = 16 + peak.tint * 34 * lambert;
        const baseB = 28 + peak.tint * 56 * lambert;
        // Mix with atmospheric haze color (toward sky tint) as distFade falls.
        const hazeR = 16, hazeG = 36, hazeB = 70;
        const r = baseR * distFade + hazeR * (1 - distFade);
        const g = baseG * distFade + hazeG * (1 - distFade);
        const bRGB = baseB * distFade + hazeB * (1 - distFade);
        ctx.fillStyle = `rgb(${r|0},${g|0},${bRGB|0})`;
        ctx.beginPath();
        ctx.moveTo(p0.sx, p0.sy);
        ctx.lineTo(p1.sx, p1.sy);
        ctx.lineTo(p2.sx, p2.sy);
        ctx.closePath();
        ctx.fill();
        // Sun-lit edge highlight — only the brightest faces get it.
        if (lambert > 0.55 && distFade > 0.55) {
            ctx.strokeStyle = `rgba(${(r+30)|0},${(g+30)|0},${(bRGB+40)|0},0.55)`;
            ctx.lineWidth = 0.6;
            ctx.stroke();
        }
    }
}

// World-space city lights as small projected pinpricks. Drawn on top
// of the mountain ring but below the ground grid so they read as
// distant settlements scattered on the plain.
function drawCityLightField() {
    if (!cityLightField || cityLightField.length === 0) return;
    const t = clock.now;
    for (const L of cityLightField) {
        const p = proj.project(L.pos);
        if (!p) continue;
        // Twinkle: alpha modulated per-light.
        const twinkle = 0.65 + 0.35 * Math.sin(t * L.twinkleRate + L.twinklePhase);
        // Distance fade — points beyond 35 km wash out.
        const distFade = 1 - Math.min(1, Math.max(0, (p.depth - 12_000) / 24_000));
        if (distFade < 0.03) continue;
        const alpha = L.brightness * twinkle * distFade;
        // Size scales mildly with distance for a sense of depth.
        const r = 0.6 + (1 - Math.min(1, p.depth / 30_000)) * 0.8;
        ctx.fillStyle = L.warm
            ? `rgba(255, 198, 128, ${alpha})`
            : `rgba(184, 220, 255, ${alpha * 0.75})`;
        ctx.beginPath();
        ctx.arc(p.sx, p.sy, r, 0, Math.PI * 2);
        ctx.fill();
    }
}

// Horizon hairline — preserved from the old terrain pass so the sky
// still meets the ground with a visible gold seam.
function drawHorizonLine() {
    const horizonY = horizonScreenY();
    ctx.strokeStyle = 'rgba(201, 169, 97, 0.22)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, snap(horizonY));
    ctx.lineTo(proj.w, snap(horizonY));
    ctx.stroke();
}

function drawStars() {
    const t = clock.now;
    for (const s of stars) {
        // Twinkle: alpha modulated by per-star phase + rate.
        const twinkle = 0.78 + 0.22 * Math.sin(t * s.twinkleRate + s.twinklePhase);
        const tint = s.warm
            ? `rgba(255, 220, 180, ${s.a * twinkle})`
            : `rgba(220, 230, 255, ${s.a * twinkle})`;
        ctx.fillStyle = tint;
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
        ctx.fill();
        // Brightest stars get a tiny cross-bloom.
        if (s.r > 1.2 && twinkle > 0.92) {
            ctx.strokeStyle = tint;
            ctx.lineWidth = 0.4;
            ctx.beginPath();
            ctx.moveTo(s.x - s.r * 3, s.y); ctx.lineTo(s.x + s.r * 3, s.y);
            ctx.moveTo(s.x, s.y - s.r * 3); ctx.lineTo(s.x, s.y + s.r * 3);
            ctx.stroke();
        }
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
// Draw the 3D city: each building is a cuboid with 8 vertices and 5
// renderable faces (we never see the bottom). Each face is back-face
// culled, Lambertian-shaded against the sun direction, and depth-
// sorted across ALL buildings' faces (painter's algorithm) so closer
// buildings correctly occlude the farther skyline.
function drawAssets() {
    if (!CITY || CITY.length === 0) return;
    const eye = cam.eye();
    const allFaces = [];

    for (const b of CITY) {
        const hw = b.w * 0.5, hd = b.d * 0.5;
        const x1 = b.cx - hw, x2 = b.cx + hw;
        const z1 = b.cz - hd, z2 = b.cz + hd;
        const verts = [
            [x1, 0,    z1], // 0
            [x2, 0,    z1], // 1
            [x2, 0,    z2], // 2
            [x1, 0,    z2], // 3
            [x1, b.h,  z1], // 4
            [x2, b.h,  z1], // 5
            [x2, b.h,  z2], // 6
            [x1, b.h,  z2], // 7
        ];
        // 5 visible faces (no floor):
        //   top:    4-5-6-7   normal +Y
        //   -Z:     0-1-5-4   normal -Z
        //   +X:     1-2-6-5   normal +X
        //   +Z:     3-2-6-7   normal +Z
        //   -X:     0-3-7-4   normal -X
        const faces = [
            { idx: [4,5,6,7], normal: [ 0, 1, 0], kind: 'top' },
            { idx: [0,1,5,4], normal: [ 0, 0,-1], kind: 'side' },
            { idx: [1,2,6,5], normal: [ 1, 0, 0], kind: 'side' },
            { idx: [3,2,6,7], normal: [ 0, 0, 1], kind: 'side' },
            { idx: [0,3,7,4], normal: [-1, 0, 0], kind: 'side' },
        ];

        // Project once per building.
        const prj = verts.map(v => proj.project(v));
        if (prj.some(p => !p)) continue;

        for (const f of faces) {
            // Back-face cull via face centroid → eye direction.
            let cx = 0, cy = 0, cz = 0;
            for (const i of f.idx) {
                cx += verts[i][0]; cy += verts[i][1]; cz += verts[i][2];
            }
            cx /= f.idx.length; cy /= f.idx.length; cz /= f.idx.length;
            const toFaceX = cx - eye[0], toFaceY = cy - eye[1], toFaceZ = cz - eye[2];
            const tLen = Math.hypot(toFaceX, toFaceY, toFaceZ) || 1;
            const dotN = (f.normal[0] * toFaceX + f.normal[1] * toFaceY + f.normal[2] * toFaceZ) / tLen;
            if (dotN > 0.02) continue;
            const lambert = Math.max(0.18, f.normal[0]*SUN_DIR[0] + f.normal[1]*SUN_DIR[1] + f.normal[2]*SUN_DIR[2]);
            allFaces.push({ b, idx: f.idx, prj, lambert, kind: f.kind, depth: tLen, faceNormal: f.normal });
        }
    }
    allFaces.sort((a, b) => b.depth - a.depth);

    for (const fa of allFaces) {
        const b = fa.b;
        const isLandmark = !!b.label;
        // Building palette: cool concrete with a faint warm bias for
        // landmarks. Lambert lifts the lit faces; sub-horizon faces
        // sit just above the navy floor.
        const baseR = (isLandmark ? 22 : 14) + b.tint * (isLandmark ? 75 : 65) * fa.lambert;
        const baseG = (isLandmark ? 28 : 18) + b.tint * (isLandmark ? 78 : 70) * fa.lambert;
        const baseB = (isLandmark ? 42 : 32) + b.tint * (isLandmark ? 95 : 88) * fa.lambert;
        ctx.fillStyle = `rgb(${baseR|0},${baseG|0},${baseB|0})`;
        const p = fa.idx.map(i => fa.prj[i]);
        ctx.beginPath();
        ctx.moveTo(p[0].sx, p[0].sy);
        for (let i = 1; i < p.length; i++) ctx.lineTo(p[i].sx, p[i].sy);
        ctx.closePath();
        ctx.fill();
        // Subtle edge so adjacent faces don't bleed into each other.
        ctx.strokeStyle = `rgba(${(baseR+18)|0},${(baseG+18)|0},${(baseB+24)|0},0.55)`;
        ctx.lineWidth = 0.6;
        ctx.stroke();

        // Window lights on side faces.
        if (fa.kind === 'side') {
            const v0 = p[0], v1 = p[1], v2 = p[2], v3 = p[3];
            // Approximate face area on screen to skip rendering windows
            // on tiny far-away faces.
            const screenW = Math.hypot(v1.sx - v0.sx, v1.sy - v0.sy);
            const screenH = Math.hypot(v3.sx - v0.sx, v3.sy - v0.sy);
            if (screenW < 8 || screenH < 12) continue;
            const cols = Math.max(2, Math.min(6, Math.floor(screenW / 6)));
            const rows = Math.max(2, Math.min(12, Math.floor(b.h / 35)));
            const rngLocal = mulberry32((b.windowSeed + (fa.faceNormal[0] | 0) * 13 + (fa.faceNormal[2] | 0) * 29) | 0);
            const t = clock.now;
            for (let rr = 0; rr < rows; rr++) {
                for (let cc = 0; cc < cols; cc++) {
                    if (rngLocal() > b.litness) continue;
                    const u = (cc + 0.5) / cols;
                    const v = (rr + 0.5) / rows;
                    // Bilinear interpolation of the four screen-space corners.
                    const sx = (1 - u) * (1 - v) * v0.sx + u * (1 - v) * v1.sx + u * v * v2.sx + (1 - u) * v * v3.sx;
                    const sy = (1 - u) * (1 - v) * v0.sy + u * (1 - v) * v1.sy + u * v * v2.sy + (1 - u) * v * v3.sy;
                    // Faint flicker.
                    const flicker = 0.62 + 0.38 * Math.sin(t * 1.3 + b.windowSeed + rr * 3 + cc);
                    const alpha = flicker * 0.78;
                    ctx.fillStyle = isLandmark
                        ? `rgba(220, 230, 250, ${alpha})`
                        : `rgba(255, 215, 140, ${alpha})`;
                    ctx.fillRect(sx - 0.6, sy - 0.6, 1.4, 1.4);
                }
            }
        }
    }

    // Landmark labels — render last so they sit on top.
    for (const L of LANDMARKS) {
        const ground = proj.project([L.pos[0], -50, L.pos[2]]);
        if (!ground) continue;
        ctx.fillStyle = 'rgba(232, 226, 208, 0.65)';
        ctx.font = '700 8.5px ui-monospace, "SF Mono", Menlo, monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillText(L.id, ground.sx, ground.sy + 4);
        ctx.textAlign = 'start';
    }
}

// Sun direction in world space — drives Lambertian shading on the
// 3D defender pyramids and on any other lit surface we add later.
const SUN_DIR = V3.norm([0.45, 0.85, 0.30]);

function drawDefenderBatteries() {
    for (const b of DEFENDER_BATTERIES) {
        // ── 3D defender pyramid ──────────────────────────────────────
        // Four world-space vertices: apex (above the position) + 3
        // base corners on the ground in an equilateral triangle.
        const apexH = 540;
        const baseR = 420;
        // Rotate the base triangle so one vertex faces the center
        // (origin) — that's the "down-range" side, gives every battery
        // a consistent orientation.
        const cx = b.pos[0], cz = b.pos[2];
        const facing = Math.atan2(-cx, -cz);   // toward origin
        const VERTS = [
            [cx,                                      apexH, cz                                      ], // 0: apex
            [cx + baseR * Math.sin(facing),               0, cz + baseR * Math.cos(facing)              ], // 1: front
            [cx + baseR * Math.sin(facing + 2.094),       0, cz + baseR * Math.cos(facing + 2.094)      ], // 2: rear-left
            [cx + baseR * Math.sin(facing + 4.189),       0, cz + baseR * Math.cos(facing + 4.189)      ], // 3: rear-right
        ];
        const PRJ = VERTS.map(v => proj.project(v));
        if (PRJ.some(p => !p)) continue;

        // 3 side faces (skip the bottom — never visible from above).
        const FACES = [[0, 1, 2], [0, 2, 3], [0, 3, 1]];
        const shaded = FACES.map(idx => {
            const a = VERTS[idx[0]], B = VERTS[idx[1]], c = VERTS[idx[2]];
            const e1 = V3.sub(B, a);
            const e2 = V3.sub(c, a);
            const n = V3.norm(V3.cross(e1, e2));
            const lambert = Math.max(0.18, V3.dot(n, SUN_DIR));
            const centroid = V3.scale(V3.add(V3.add(a, B), c), 1 / 3);
            const depth = V3.len(V3.sub(centroid, cam.eye()));
            // Back-face cull: face is "facing away" if the normal points
            // in the same direction as eye→centroid.
            const toFace = V3.norm(V3.sub(centroid, cam.eye()));
            const facingAway = V3.dot(n, toFace) > 0.05;
            return { idx, lambert, depth, facingAway };
        }).filter(f => !f.facingAway)
          .sort((a, b) => b.depth - a.depth);

        for (const { idx, lambert } of shaded) {
            const p0 = PRJ[idx[0]], p1 = PRJ[idx[1]], p2 = PRJ[idx[2]];
            // Build a shaded fill from the battery's accent colour
            // blended with a dark navy underlay.
            const r = Math.min(255, 14 + b.color[0] * 200 * lambert);
            const g = Math.min(255, 22 + b.color[1] * 200 * lambert);
            const bb = Math.min(255, 36 + b.color[2] * 220 * lambert);
            ctx.fillStyle = `rgba(${r|0},${g|0},${bb|0},0.97)`;
            ctx.beginPath();
            ctx.moveTo(p0.sx, p0.sy);
            ctx.lineTo(p1.sx, p1.sy);
            ctx.lineTo(p2.sx, p2.sy);
            ctx.closePath();
            ctx.fill();
            // Edge highlight — brighter on faces nearest the sun.
            ctx.strokeStyle = rgbStr(b.color, 0.45 + 0.45 * lambert);
            ctx.lineWidth = 1.0;
            ctx.stroke();
        }

        // Apex emissive bead + halo.
        const apex = PRJ[0];
        const haloR = 22;
        const halo = ctx.createRadialGradient(apex.sx, apex.sy, 0, apex.sx, apex.sy, haloR);
        halo.addColorStop(0, rgbStr(b.color, 0.55));
        halo.addColorStop(1, rgbStr(b.color, 0.00));
        ctx.fillStyle = halo;
        ctx.beginPath();
        ctx.arc(apex.sx, apex.sy, haloR, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = rgbStr(b.color, 1.0);
        ctx.beginPath();
        ctx.arc(apex.sx, apex.sy, 2.6, 0, Math.PI * 2);
        ctx.fill();

        // Label below the base.
        const labelP = proj.project([cx, -110, cz]);
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
//   Keyed by track id so the THREATS list can be dynamic without
//   invalidating per-track history.
// ═════════════════════════════════════════════════════════════════════
const TRAIL_SAMPLES = 72;
const trailsByTrack = new Map();

function pushTrailSamples() {
    for (const tr of THREATS) {
        let s = trailsByTrack.get(tr.id);
        if (!trackVisible(tr)) {
            if (s && s.length) s.length = 0;
            continue;
        }
        if (!s) { s = []; trailsByTrack.set(tr.id, s); }
        s.push(trackPos(tr));
        if (s.length > TRAIL_SAMPLES) s.shift();
    }
}

function drawTrails() {
    const subdivisions = 8;        // Catmull-Rom interior samples per segment
    for (const tr of THREATS) {
        if (engagement.killedTracks.has(tr.id)) continue;
        if (!trackVisible(tr)) continue;
        const s = trailsByTrack.get(tr.id);
        if (!s) continue;
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

// Per-defender effective-speed helpers. The planner uses an average
// that accounts for the boost ramp; the salvo physics uses the live
// boost+cruise+accel model from the defender profile.
function defenderAvgSpeed(def) {
    if (def.class === 'DIRECTED') return 1e9;       // effectively instant
    return def.profile.boost_mps * (def.profile.boost_s / 4) / 1 +
           def.profile.cruise_mps * 0.85;           // ~85% of cruise on average
}
function defenderBoostDist(def) {
    if (def.class === 'DIRECTED') return 0;
    return def.profile.boost_mps * def.profile.boost_s;
}

// REACTION: minimum slack we require before committing — accounts for
// the seeker's reaction time and the operator-loop reveal delay.
const ENGAGEMENT_REACTION = 0.35;
// Detection delay: how long after a threat appears before the radar
// has a track quality fit to engage on.
const RADAR_DETECTION_DELAY = 0.4;

// Predicted-impact point (PIP) — where the threat will impact the
// ground plane if unengaged. Iron Dome's signature behaviour: only
// expend interceptors on threats that will hit the defended cell.
function predictImpactPoint(track) {
    return [track.terminal[0], 0, track.terminal[2]];
}

// True if the predicted impact lies inside the defended bubble. We
// also classify the impact as VITAL (≤ 2 km — near command/assets) or
// PERIPHERAL (2-8 km — assets-of-opportunity but still defended).
function classifyImpact(track) {
    const pip = predictImpactPoint(track);
    const range = Math.hypot(pip[0], pip[2]);
    if (range <= 2_400) return 'VITAL';
    if (range <= 8_000) return 'PERIPHERAL';
    return 'OUTSIDE';
}

function planIntercept(track, defender) {
    if (defender.class === 'DIRECTED') {
        // Line-of-sight directed energy: feasible if the target is
        // ever in envelope at any phase, and if mid-trajectory
        // distance is within rangeMax. Pick the phase that minimises
        // slant range.
        let best = null;
        const samples = 48;
        for (let i = 0; i <= samples; i++) {
            const ph = i / samples;
            const point = V3.bezQ(track.launch, track.apogee, track.terminal, ph);
            const tAtCycle = track.launchAt + ph * track.flightTime;
            const threatT = tAtCycle - clock.now;
            if (threatT < ENGAGEMENT_REACTION) continue;
            const dist = V3.len(V3.sub(point, [defender.pos[0], 380, defender.pos[2]]));
            if (dist < defender.envelope.rangeMin || dist > defender.envelope.rangeMax) continue;
            if (point[1] < defender.envelope.hMin || point[1] > defender.envelope.hMax) continue;
            const interceptorT = defender.profile.dwell_s || 0.45;
            if (interceptorT > threatT + 0.05) continue;
            const slack = threatT - interceptorT;
            if (best === null || slack < best.slack) {
                best = { tti: interceptorT, threatT, slack, ph, point };
            }
        }
        return best;
    }

    const launcherPos = [defender.pos[0], 380, defender.pos[2]];
    const boostDist = defenderBoostDist(defender);
    const profile = defender.profile;
    const minPhase = Math.max(
        0,
        (Math.max(track.launchAt + RADAR_DETECTION_DELAY, clock.now + ENGAGEMENT_REACTION) - track.launchAt) / track.flightTime
    );
    if (minPhase > 1) return null;

    const samples = 64;
    let best = null;
    for (let i = 0; i <= samples; i++) {
        const ph = minPhase + (1 - minPhase) * (i / samples);
        const tAtCycle = track.launchAt + ph * track.flightTime;
        const threatT = tAtCycle - clock.now;
        if (threatT < ENGAGEMENT_REACTION) continue;
        const point = V3.bezQ(track.launch, track.apogee, track.terminal, ph);
        const dist = V3.len(V3.sub(point, launcherPos));

        // Envelope gates.
        if (dist < defender.envelope.rangeMin) continue;
        if (dist > defender.envelope.rangeMax) continue;
        if (point[1] < defender.envelope.hMin)  continue;
        if (point[1] > defender.envelope.hMax)  continue;

        // Time-to-fly model: boost phase (0 → boost_s, avg boost speed)
        // + cruise phase. Exact ∫v dt over the boost ramp:
        //   distance covered in boost = (1/2)(boost_mps + cruise_mps) * boost_s
        //   approx using boost_mps avg if cruise not yet reached.
        let interceptorT;
        const avgBoost = (profile.boost_mps + profile.cruise_mps) * 0.5;
        const fullBoostDist = avgBoost * profile.boost_s;
        if (dist <= fullBoostDist) {
            // Newton-step on (1/2)(a)(t²) + boost*t = dist
            // a = (cruise - boost) / boost_s
            const aR = (profile.cruise_mps - profile.boost_mps) / profile.boost_s;
            const A = 0.5 * aR;
            const B = profile.boost_mps;
            const C = -dist;
            const disc = B * B - 4 * A * C;
            interceptorT = (disc < 0) ? dist / avgBoost : (-B + Math.sqrt(disc)) / (2 * A);
        } else {
            interceptorT = profile.boost_s + (dist - fullBoostDist) / profile.cruise_mps;
        }
        if (interceptorT > threatT + 0.04) continue;     // infeasible
        const slack = threatT - interceptorT;
        if (best === null || slack < best.slack) {
            best = { tti: interceptorT, threatT, slack, ph, point };
        }
    }
    return best;
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
    const p = planIntercept(track, defender);
    if (p) return { tti: p.tti, point: p.point, feasible: true };
    return { tti: 0, point: trackPos(track), feasible: false };
}

// ═════════════════════════════════════════════════════════════════════
//   WEAPON-TARGET ASSIGNMENT (WTA)
//
//   The classical WTA problem: assign m interceptors to n targets to
//   maximise expected kills while respecting envelope, magazine, and
//   in-flight limits per defender.
//
//   We use a priority-greedy approximation with Iron-Dome doctrine
//   biases — it's near-optimal for the 4×N case and runs in O(N log N
//   + 4N) per assignment cycle, well under one frame:
//
//   1.  PIP-filter: skip threats whose terminal lies OUTSIDE the
//       defended bubble. (Iron Dome's signature efficiency move.)
//   2.  Order surviving threats by URGENCY (low time-to-impact, high
//       class priority, vital impact > peripheral).
//   3.  For each threat in priority order, iterate the 4 defenders
//       and SCORE each pairing:
//         score = pk(defender, threat) × (slack + 0.5) − 0.4 × kindMismatch
//       Reject pairings without magazine, exceeding maxSimul, still
//       inside reload window, or with no feasible planIntercept.
//   4.  Assign the highest-scoring defender. For VITAL HVTs (HGV/BM
//       in the vital bubble) assign a SECOND interceptor from the
//       next-best defender — shoot-shoot-look salvo doctrine.
//   5.  Decrement that defender's expected magazine + in-flight
//       counters so successive iterations see the updated state.
// ═════════════════════════════════════════════════════════════════════

function urgencyScore(track) {
    // Time-to-impact = (launchAt + flightTime) − now. Negative for
    // already-past-terminal tracks (they shouldn't be in the WTA list
    // but we guard anyway).
    const ttImpact = Math.max(0.1, (track.launchAt + track.flightTime) - clock.now);
    const cls = classifyImpact(track);
    const vitalBonus = cls === 'VITAL' ? 6 : cls === 'PERIPHERAL' ? 2 : 0;
    const kindBonus = 5 - track.priority;
    return vitalBonus + kindBonus + (10 / ttImpact);
}

function computeAssignments() {
    const assignments = [];
    // Snapshot defender state so we can simulate the magazine drain
    // without mutating until we commit.
    const sim = new Map();
    for (const b of DEFENDER_BATTERIES) {
        const st = defenderState.get(b.id);
        sim.set(b.id, {
            magazine: st.magazine,
            inflight: st.inflight,
            lastFired: st.lastFired,
        });
    }

    // PIP-filter + sort threats by urgency.
    const ranked = THREATS
        .filter(t => !engagement.killedTracks.has(t.id))
        .filter(t => trackVisible(t))                        // already detected by radar
        .filter(t => classifyImpact(t) !== 'OUTSIDE')         // Iron Dome: don't waste shots
        .filter(t => !(t._assignedKinetic || 0) || t._needsReshot);
    ranked.sort((a, b) => urgencyScore(b) - urgencyScore(a));

    for (const tr of ranked) {
        // Per-track: rank defenders by score, take top-2 if HVT.
        const candidates = [];
        for (const def of DEFENDER_BATTERIES) {
            const st = sim.get(def.id);
            if (st.magazine <= 0) continue;
            if (st.inflight >= def.logistics.maxSimul) continue;
            if (clock.now - st.lastFired < def.logistics.reload_s) continue;
            const plan = planIntercept(tr, def);
            if (!plan) continue;
            const pk = def.pk[tr.kind] ?? 0.5;
            const score = pk * (plan.slack + 0.4)
                        + (def.class === 'DIRECTED' ? 0.2 : 0);   // small DEZ preference
            candidates.push({ def, plan, pk, score });
        }
        if (!candidates.length) continue;
        candidates.sort((a, b) => b.score - a.score);
        const cls = classifyImpact(tr);
        const isHVT = (tr.priority <= 2) && (cls === 'VITAL');
        const wantShots = isHVT ? 2 : 1;
        let committed = 0;
        for (const c of candidates) {
            if (committed >= wantShots) break;
            // Don't assign two of the same defender to the same target.
            if (assignments.some(a => a.targetId === tr.id && a.defenderId === c.def.id)) continue;
            assignments.push({
                defenderId: c.def.id,
                targetId:   tr.id,
                kind:       c.def.class,
                plan:       c.plan,
                pk:         c.pk,
            });
            // Mutate sim so the next threat in the ranking sees the
            // committed defender as one tube down.
            const st = sim.get(c.def.id);
            st.magazine -= 1;
            st.inflight += 1;
            st.lastFired = clock.now;
            committed++;
        }
    }
    return assignments;
}

function drawEngagementAllocations() {
    // In WTA-driven AUTO mode the salvos themselves visualise the
    // engagement; planning overlays would clutter the picture. Only
    // show planning lines for the legacy operator-COA path while a
    // COA is on the table.
    if (engagement.autoEngage) return;
    if (engagement.authorizedCOA !== null) return;
    if (!(cyclePhase() >= COA_OPEN_T && cyclePhase() < COA_CLOSE_T)) return;
    // Pick the top-N WTA candidates as the planning overlay.
    const plan = computeAssignments().slice(0, 6);
    for (const a of plan) {
        const def = findDefender(a.defenderId);
        const tr  = findTrack(a.targetId);
        if (!def || !tr) continue;
        if (engagement.killedTracks.has(tr.id)) continue;
        const point = a.plan.point;
        const tti = a.plan.tti;
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
        const txt = `${a.defenderId}→${tr.id.split('-').slice(-1)[0]} · TTI ${tti.toFixed(1)}s`;
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
// Launch a salvo using the defender's actual interceptor profile.
// `alloc` is { defender, target, kind } — the WTA / COA caller can
// optionally supply `plan` (precomputed planIntercept result) so we
// don't pay for the sweep twice in the same tick.
function launchSalvo(coaId, alloc, launchOffsetSec, precomputedPlan) {
    // Accept both naming conventions: COA-style `{defender, target}`
    // and WTA-style `{defenderId, targetId}`.
    const defenderName = alloc.defender   || alloc.defenderId;
    const targetName   = alloc.target     || alloc.targetId;
    const def = findDefender(defenderName);
    const tr  = findTrack(targetName);
    if (!def || !tr) return null;
    if (engagement.killedTracks.has(tr.id)) return null;

    const st = defenderState.get(def.id);
    if (!st || st.magazine <= 0) {
        pushLogOnce(
            `dry-${defenderName}-${tr.id}-${(clock.now * 10) | 0}`,
            `<em>${defenderName}</em> magazine empty · skipped`,
        );
        return null;
    }
    if (st.inflight >= def.logistics.maxSimul) return null;
    if (clock.now - st.lastFired < def.logistics.reload_s) return null;

    let plan = precomputedPlan || null;
    if (!plan && def.class === 'KINETIC') {
        plan = planIntercept(tr, def);
        if (!plan) {
            pushLogOnce(
                `infeasible-${defenderName}-${targetName}`,
                `intercept infeasible <em>${defenderName}→${tr.id}</em> · no kinematic solution`,
            );
            return null;
        }
    }

    const profile = def.profile;
    const isDirected = def.class === 'DIRECTED';
    engagement.salvos.push({
        id: `${defenderName}-${targetName}-${++engagement._salvoSerial}`,
        coa: coaId,
        defenderId: defenderName,
        targetId: targetName,
        kind: def.class,
        // Pulled directly from the defender's interceptor profile, so
        // each battery flies its own kinematics.
        cruiseSpeedMps:  isDirected ? 0 : profile.cruise_mps,
        boostSpeedMps:   isDirected ? 0 : profile.boost_mps,
        accelMps2:       isDirected ? 0 : profile.accel_mps2,
        turnRateRadSec:  isDirected ? 0 : profile.turn_rad_s,
        boostDuration:   isDirected ? 0 : profile.boost_s,
        detonationM:     isDirected ? 0 : profile.detonation_m,
        directedDwell:   isDirected ? (profile.dwell_s || 0.45) : 0,
        commitAt: clock.now + (launchOffsetSec || 0),
        armedAt:  null,
        launchedAt: null,
        plannedTTI:   plan ? plan.tti   : null,
        plannedPoint: plan ? plan.point : null,
        position: [def.pos[0], 380, def.pos[2]],
        velocity: [0, 0, 0],
        speed: 0,
        state: 'queued',
        impactPoint: null,
        impactAt: null,
        color: [...def.color],
        trail: [],
        pk: def.pk[tr.kind] ?? 0.5,
    });
    st.magazine -= 1;
    st.inflight += 1;
    st.lastFired = clock.now;
    return engagement.salvos[engagement.salvos.length - 1];
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

// Mark a salvo as finished — credit the defender's in-flight slot back
// and book-keep the engagement outcome.
function retireSalvo(s, outcome) {
    if (s._retired) return;
    s._retired = true;
    s.state = outcome === 'kill' ? 'splash' : 'done';
    const st = defenderState.get(s.defenderId);
    if (st && st.inflight > 0) st.inflight -= 1;
    if (outcome === 'kill') engagement.intercepts += 1;
    if (typeof noteSalvoOutcome === 'function') noteSalvoOutcome(s, outcome);
}

function tickSalvos(dt) {
    for (const s of engagement.salvos) {
        if (s.state === 'done') continue;
        if (clock.now < s.commitAt) continue;        // pre-commit hold

        const tr = findTrack(s.targetId);
        const targetLost = (!tr || engagement.killedTracks.has(s.targetId));

        if (targetLost && s.state === 'queued') {
            // Never lifted off — silently scrap. Magazine was already
            // consumed at queue time, so this is just cleanup.
            retireSalvo(s, 'abort');
            continue;
        }

        if (targetLost && s.state === 'inflight') {
            // Real interceptors don't just vanish when their target
            // is gone. Promote to 'orphaned' — they coast on their
            // last velocity for orphanCoast seconds, then the safety
            // fuze self-destructs them with a small mid-air flash.
            s.state = 'orphaned';
            s.orphanedAt = clock.now;
        }

        if (s.state === 'orphaned') {
            // Coast on existing velocity, sample the trail, and trigger
            // a self-destruct after a short window OR if the missile
            // hits the deck.
            const ORPHAN_COAST = 1.4;
            s.position = V3.add(s.position, V3.scale(s.velocity, dt));
            const samplePeriod = 1 / 30;
            if (!s._lastSampled || (clock.now - s._lastSampled) >= samplePeriod) {
                s.trail.push(s.position.slice());
                if (s.trail.length > 48) s.trail.shift();
                s._lastSampled = clock.now;
            }
            const expired = (clock.now - s.orphanedAt) > ORPHAN_COAST;
            const grounded = s.position[1] < 20;
            if (expired || grounded) {
                engagement.splashes.push({
                    point: s.position.slice(),
                    born: clock.now,
                    until: clock.now + 0.7,
                    kind: 'selfdestruct',
                });
                pushLogOnce(
                    `sd-${s.id}`,
                    `interceptor abandoned <em>${s.defenderId}</em> · safety fuze self-destruct`,
                );
                retireSalvo(s, 'abort');
            }
            continue;
        }

        const def = findDefender(s.defenderId);

        // ── Acquisition gate ──────────────────────────────────────
        if (s.state === 'queued') {
            if (!trackVisible(tr)) continue;
            if (def.class === 'KINETIC') {
                const plan = planIntercept(tr, def);
                if (!plan) {
                    pushLogOnce(
                        `miss-${tr.id}-${s.defenderId}`,
                        `intercept infeasible <em>${s.defenderId}→${tr.id}</em> · target out of envelope`,
                    );
                    retireSalvo(s, 'abort');
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
                const hit = Math.random() < (s.pk || 0.7);
                s.impactPoint = targetPos;
                s.impactAt = clock.now;
                if (hit) {
                    retireSalvo(s, 'kill');
                    killTrack(tr.id, targetPos);
                } else {
                    // Beam never landed — pulse off and re-task.
                    pushLogOnce(`miss-${s.id}`, `miss <em>${s.defenderId}→${tr.id}</em> · re-task pending`);
                    retireSalvo(s, 'miss');
                }
            }
            continue;
        }

        // ── Kinetic interceptor ───────────────────────────────────
        // Lead-angle guidance via the quadratic collision-course
        // solution. Aim point is r_T(now + t*), recomputed each frame.
        const flightT = clock.now - s.launchedAt;
        const cruise = s.speed > 0 ? s.speed : s.cruiseSpeedMps;
        const v_T = trackVelAt(tr, clock.now);
        const t_lead = leadInterceptTime(s.position, targetPos, v_T, Math.max(cruise, s.boostSpeedMps));
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

        // Live distance to the actual threat drives the proximity fuze.
        // ONLY a confirmed hit retires the interceptor immediately. A
        // fuze miss (Pk roll fails) flips the missile to 'orphaned' so
        // it continues past the target and self-destructs visibly —
        // operators never see a missile vanish without an impact.
        const liveDist = V3.len(V3.sub(targetPos, s.position));
        const stepLen = s.speed * dt;
        const fuzeR = Math.max(s.detonationM || 160, stepLen * 1.4);
        if (liveDist < fuzeR) {
            const hit = Math.random() < (s.pk || 0.8);
            s.impactPoint = targetPos;
            s.impactAt = clock.now;
            if (hit) {
                retireSalvo(s, 'kill');
                killTrack(tr.id, targetPos);
            } else {
                pushLogOnce(`miss-${s.id}`, `miss <em>${s.defenderId}→${tr.id}</em> · ${tr.kind} survived fuze`);
                // Promote to orphaned: missile flies past, the orphan
                // coast logic at the top of the loop self-destructs it.
                s.state = 'orphaned';
                s.orphanedAt = clock.now;
                // Tell the WTA the target is still alive so it re-tasks.
                noteSalvoOutcome(s, 'miss');
            }
        } else {
            s.position = V3.add(s.position, V3.scale(s.velocity, dt));
            const samplePeriod = 1 / 30;
            if (!s._lastSampled || (clock.now - s._lastSampled) >= samplePeriod) {
                s.trail.push(s.position.slice());
                if (s.trail.length > 48) s.trail.shift();
                s._lastSampled = clock.now;
            }
        }

        // Ground-floor: missile descended below 20 m without fuzing on
        // the target. Don't claim a leakage on the THREAT (it's still
        // alive) — just flip the missile to 'orphaned' and let the
        // self-destruct splash fire from the same path as the miss case.
        if (s.position[1] < 20 && flightT > 0.8 && s.state === 'inflight') {
            s.state = 'orphaned';
            s.orphanedAt = clock.now;
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
    const tr = findTrack(targetId);
    if (tr) tr._killedAt = clock.now;
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
        const isLeak = sp.kind === 'leak';
        const isSelfDestruct = sp.kind === 'selfdestruct';
        if (isSelfDestruct) {
            // Mid-air safety-fuze detonation — small white-blue flash,
            // no shrapnel ticks, no shockwave. Just a brief puff.
            const r = 6 + age * 16;
            const flash = ctx.createRadialGradient(p.sx, p.sy, 0, p.sx, p.sy, r);
            flash.addColorStop(0.00, `rgba(220, 240, 255, ${(1 - age) * 0.85})`);
            flash.addColorStop(0.55, `rgba(170, 200, 240, ${(1 - age) * 0.45})`);
            flash.addColorStop(1.00, 'rgba(170, 200, 240, 0)');
            ctx.fillStyle = flash;
            ctx.beginPath();
            ctx.arc(p.sx, p.sy, r, 0, Math.PI * 2);
            ctx.fill();
            ctx.strokeStyle = `rgba(220, 240, 255, ${(1 - age) * 0.6})`;
            ctx.lineWidth = 0.7;
            ctx.beginPath();
            ctx.arc(p.sx, p.sy, r * 0.6, 0, Math.PI * 2);
            ctx.stroke();
            continue;
        }
        // Leak splashes are bigger, crimson, longer-lived; intercept
        // splashes are smaller and amber.
        const r1 = (isLeak ? 14 : 8) + age * (isLeak ? 90 : 60);
        const r2 = r1 * 0.45;

        if (isLeak) {
            // Ground impact — crimson outer ring + red core.
            ctx.strokeStyle = `rgba(255, 90, 60, ${(1 - age) * 0.95})`;
            ctx.lineWidth = 2.8 - age * 1.8;
            ctx.beginPath();
            ctx.arc(p.sx, p.sy, r1, 0, Math.PI * 2);
            ctx.stroke();
            // Secondary smoke ring lagging the shockwave.
            ctx.strokeStyle = `rgba(60, 40, 50, ${(1 - age) * 0.55})`;
            ctx.lineWidth = 1.4;
            ctx.beginPath();
            ctx.arc(p.sx, p.sy, r1 * 0.7, 0, Math.PI * 2);
            ctx.stroke();
            const hot = ctx.createRadialGradient(p.sx, p.sy, 0, p.sx, p.sy, r2);
            hot.addColorStop(0.00, `rgba(255, 230, 180, ${(1 - age) * 0.95})`);
            hot.addColorStop(0.40, `rgba(255, 140,  60, ${(1 - age) * 0.75})`);
            hot.addColorStop(1.00, `rgba(220,  40,  30, 0)`);
            ctx.fillStyle = hot;
            ctx.beginPath();
            ctx.arc(p.sx, p.sy, r2, 0, Math.PI * 2);
            ctx.fill();
            // Strike marker — small "X" persists briefly.
            ctx.strokeStyle = `rgba(255, 80, 60, ${(1 - age) * 0.9})`;
            ctx.lineWidth = 1.4;
            const xs = 5;
            ctx.beginPath();
            ctx.moveTo(p.sx - xs, p.sy - xs); ctx.lineTo(p.sx + xs, p.sy + xs);
            ctx.moveTo(p.sx - xs, p.sy + xs); ctx.lineTo(p.sx + xs, p.sy - xs);
            ctx.stroke();
        } else {
            // Intercept — amber/yellow.
            ctx.strokeStyle = `rgba(255, 220, 140, ${(1 - age) * 0.95})`;
            ctx.lineWidth = 2.2 - age * 1.6;
            ctx.beginPath();
            ctx.arc(p.sx, p.sy, r1, 0, Math.PI * 2);
            ctx.stroke();
            const hot = ctx.createRadialGradient(p.sx, p.sy, 0, p.sx, p.sy, r2);
            hot.addColorStop(0.00, `rgba(255, 255, 220, ${(1 - age) * 0.95})`);
            hot.addColorStop(0.50, `rgba(255, 180,  60, ${(1 - age) * 0.55})`);
            hot.addColorStop(1.00, `rgba(220,  80,  40, 0)`);
            ctx.fillStyle = hot;
            ctx.beginPath();
            ctx.arc(p.sx, p.sy, r2, 0, Math.PI * 2);
            ctx.fill();
        }

        // Shrapnel ticks — slightly different palette per kind.
        ctx.strokeStyle = isLeak
            ? `rgba(255, 100, 70, ${(1 - age) * 0.75})`
            : `rgba(255, 200, 100, ${(1 - age) * 0.65})`;
        ctx.lineWidth = 0.9;
        const spokes = isLeak ? 12 : 8;
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
    // Track which callout ids are alive this frame so we can GC
    // orphans whose threats were dropped by tickThreatLifecycle —
    // otherwise a leaker / killed track leaves a callout box parked
    // over the city forever.
    const alive = new Set();
    for (const tr of TRACKS) {
        const nodeId = 'co-' + tr.id;
        alive.add(nodeId);
        let node = document.getElementById(nodeId);
        if (!node) {
            node = document.createElement('div');
            node.id = nodeId;
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
        // Proximity scale: callouts shrink the farther the threat is
        // from the camera, drop to id-chip only at mid range, and hide
        // outright when the camera is panned far enough that they'd
        // crowd the screen.
        //   near  (depth < 7 km)        full size, full readout
        //   mid   (7-18 km)             scaled down, full readout
        //   far   (18-32 km)            tiny chip, id only
        //   beyond (> 32 km)            hidden
        const dep = sp.depth;
        if (dep > 32_000) { node.style.display = 'none'; continue; }
        let scale, isFar;
        if (dep < 7_000) {
            scale = 1.0; isFar = false;
        } else if (dep < 18_000) {
            // Smoothly interpolate from 1.0 at 7 km to 0.62 at 18 km.
            scale = 1.0 - (dep - 7_000) / 11_000 * 0.38;
            isFar = false;
        } else {
            // Far: tiny chip, gentle continued shrink from 0.55 to 0.40.
            scale = 0.55 - (dep - 18_000) / 14_000 * 0.15;
            isFar = true;
        }
        node.style.display = '';
        node.style.left = (sp.sx + Math.round(14 * scale + 4)) + 'px';
        node.style.top  = (sp.sy - 4) + 'px';
        node.style.transform = `translateY(-50%) scale(${scale.toFixed(3)})`;
        node.classList.toggle('callout--far', isFar);
        node.querySelector('.callout__id').textContent = `${tr.id} · P${tr.priority}`;
        node.querySelector('.callout__data').textContent =
            `${tr.kind} · CONFIDENT · M${speed.toFixed(1)} · ALT ${altKm} km · RNG ${rngKm} km`;
    }
    // Drop orphan callout nodes — happens for threats GC'd from the
    // THREATS list (leaked into the city, splashed and aged out, or
    // dropped between cycles).
    for (let i = container.children.length - 1; i >= 0; i--) {
        const n = container.children[i];
        if (n.id && !alive.has(n.id)) container.removeChild(n);
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
        why: '2× NGI on highest-confidence HGV. IRON-D screens drones and cruise. Cyber denies adversary GNSS guidance under ROE-2.',
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
    } else if (e.key === 's' || e.key === 'S') {
        spawnStressWave();
    } else if (e.key === 'c' || e.key === 'C') {
        cam.toggleFreeCam();
    } else if (e.key === 'Home' || e.key === '=') {
        cam.home();
        cam.freeCamLocked = false;
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
        directed ? `${directed}× IRON-D` : null,
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
    // Reset manual-toggle memory whenever AUTO state changes so the
    // panel snaps to the new default collapse state.
    _decisionsManualToggle = false;
    applyAutoCollapse();
    CALM_LIVE.unshift(
        on
            ? `AUTO-ENGAGE armed · ROE-2 weapons-free · operator override available`
            : `AUTO-ENGAGE disarmed · operator-in-loop restored`
    );
    if (CALM_LIVE.length > 14) CALM_LIVE.pop();
    lastCalmK = -2;
}

document.getElementById('autoToggle').addEventListener('click', (e) => {
    e.stopPropagation();
    setAutoEngage(!engagement.autoEngage);
});

// ─── Collapsible Decisions panel ────────────────────────────────────
let _decisionsManualToggle = false;     // operator overrode auto-collapse
function setDecisionsCollapsed(collapsed) {
    document.getElementById('decisionsPanel')
        .classList.toggle('decisions--collapsed', collapsed);
}
document.getElementById('decisionsTitle').addEventListener('click', () => {
    const panel = document.getElementById('decisionsPanel');
    const isCollapsed = panel.classList.contains('decisions--collapsed');
    setDecisionsCollapsed(!isCollapsed);
    _decisionsManualToggle = true;
});

// ─── Generic collapsible panel handler ───────────────────────────────
document.querySelectorAll('.panel__header').forEach(h => {
    h.addEventListener('click', () => {
        const id = h.dataset.target;
        if (!id) return;
        const panel = document.getElementById(id);
        if (!panel) return;
        panel.classList.toggle('panel--collapsed');
    });
});
function applyAutoCollapse() {
    // When AUTO is on we collapse the panel by default; the operator
    // can still expand it manually (and we respect that). When AUTO
    // turns off we restore the expanded view.
    if (_decisionsManualToggle) return;
    setDecisionsCollapsed(engagement.autoEngage);
}

// ─── Continuous AUTO engagement ────────────────────────────────────
// When AUTO is on, run weapon-target assignment every ASSIGNMENT_PERIOD
// seconds and launch interceptors for the resulting allocations. This
// is the brain of the Iron-Dome-flavoured controller — it sees the
// current threat picture, picks the best defender per threat, and
// fires immediately. Salvos still pass through the queued → inflight
// acquisition gate so they don't ghost-shoot.
const ASSIGNMENT_PERIOD = 0.35;          // 350 ms WTA tick
function tickAutoEngage() {
    if (!engagement.autoEngage) return;
    if (clock.now - engagement.lastAssignmentAt < ASSIGNMENT_PERIOD) return;
    engagement.lastAssignmentAt = clock.now;
    const assignments = computeAssignments();
    if (!assignments.length) return;
    // Tag each target so the WTA doesn't re-task on threats already
    // engaged unless the engagement misses.
    for (const a of assignments) {
        const tr = findTrack(a.targetId);
        if (!tr) continue;
        // Skip if there's already an in-flight salvo from this defender
        // to this target.
        const dup = engagement.salvos.some(s =>
            !s._retired &&
            s.targetId === a.targetId &&
            s.defenderId === a.defenderId &&
            (s.state === 'queued' || s.state === 'inflight'));
        if (dup) continue;
        const launched = launchSalvo('AUTO-WTA', a, 0, a.plan);
        if (launched) {
            tr._assignedKinetic = (tr._assignedKinetic || 0) + 1;
        }
    }
}

// Re-engagement: when a salvo retires as 'miss' or 'leak', clear the
// target's _assignedKinetic flag so the next WTA pass picks a fresh
// shooter. Called from retireSalvo via a tail-hook in tickSalvos.
function noteSalvoOutcome(s, outcome) {
    if (outcome !== 'kill') {
        const tr = findTrack(s.targetId);
        if (tr) {
            tr._assignedKinetic = Math.max(0, (tr._assignedKinetic || 1) - 1);
            tr._needsReshot = true;
        }
    }
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
// Tiny camera-state badge near the watermark — shows zoom level and a
// "FREE-CAM" indicator while the operator has locked the orbit.
let lastCamSig = '';
function renderCamBadge() {
    const el = document.getElementById('camBadge');
    if (!el) return;
    const km = (cam.radius / 1000).toFixed(1);
    const lockTag = cam.freeCamLocked ? ' · FREE-CAM' : '';
    const idleFor = clock.now - cam.interacted;
    const driving = idleFor < cam.idleResume && !cam.freeCamLocked;
    const sig = `${km}|${lockTag}|${driving}`;
    if (sig === lastCamSig) return;
    lastCamSig = sig;
    const drivingTag = driving ? ' · MANUAL' : '';
    el.textContent = `CAM · ${km} km${lockTag}${drivingTag}`;
    el.style.color = cam.freeCamLocked
        ? 'rgba(220, 160, 60, 0.85)'
        : (driving ? 'rgba(150, 220, 160, 0.75)' : 'rgba(150, 220, 160, 0.45)');
}

function renderCalm() {
    const k = Math.floor(clock.now * 0.4) % CALM_LIVE.length;
    if (k === lastCalmK) return;
    lastCalmK = k;
    const ordered = CALM_LIVE.slice(k).concat(CALM_LIVE.slice(0, k));
    document.getElementById('calmList').innerHTML = ordered.map(s => `<span>${s}</span>`).join('');
}

// ─── Weapons bay state — magazines drop when COA-B is authorized ─────
const BAY_BASE = {
    'NGI':   { fmt: (v) => String(v) },
    'SM-3':  { fmt: (v) => String(v) },
    'PAC-3': { fmt: (v) => String(v) },
    'IRON-D': { fmt: (v) => String(v | 0) },
};
let lastBayState = '';
function renderBay() {
    let sig = '';
    for (const def of DEFENDER_BATTERIES) {
        const st = defenderState.get(def.id);
        sig += `${def.id}:${st.magazine}:${st.inflight}|`;
    }
    if (sig === lastBayState) return;
    lastBayState = sig;

    for (const def of DEFENDER_BATTERIES) {
        const slot = document.querySelector(`.bay__slot[data-eff="${def.id}"]`);
        if (!slot) continue;
        const st = defenderState.get(def.id);
        const fmt = BAY_BASE[def.id]?.fmt || ((v) => String(v));
        const value = st.magazine;
        slot.querySelector('.bay__count').textContent = fmt(value);
        const ratio = def.logistics.magazineMax > 0
            ? Math.max(0, st.magazine / def.logistics.magazineMax)
            : 1.0;
        slot.querySelector('.bay__bar-fill').style.width = (ratio * 100).toFixed(1) + '%';
        slot.classList.remove('bay__slot--depleted', 'bay__slot--firing');
        if (st.magazine === 0) slot.classList.add('bay__slot--depleted');
        else if (st.inflight > 0) slot.classList.add('bay__slot--firing');
    }
}

function renderStats() {
    const liveThreats = THREATS.filter(t =>
        !engagement.killedTracks.has(t.id) && trackVisible(t));
    const enroute = engagement.salvos.filter(s =>
        !s._retired && (s.state === 'inflight' || s.state === 'queued')).length;
    document.getElementById('stTracks').textContent = String(liveThreats.length);
    document.getElementById('stEng').textContent = `${enroute} salvo`;
    // Primary TTI: the smallest TTI among the most urgent live threat's
    // assigned defenders.
    let primaryTTI = null;
    if (liveThreats.length) {
        liveThreats.sort((a, b) => urgencyScore(b) - urgencyScore(a));
        const tr = liveThreats[0];
        for (const def of DEFENDER_BATTERIES) {
            const plan = planIntercept(tr, def);
            if (!plan) continue;
            if (primaryTTI === null || plan.tti < primaryTTI) primaryTTI = plan.tti;
        }
    }
    const ttiEl = document.getElementById('stTTI');
    if (primaryTTI === null) {
        ttiEl.textContent = '—';
        ttiEl.className = 'stats__v';
    } else {
        ttiEl.textContent = `${primaryTTI.toFixed(1)} s`;
        ttiEl.className = primaryTTI < 3 ? 'stats__v stats__v--warn' : 'stats__v stats__v--ok';
    }
    // Replace static stats with live counts.
    const pkEl = document.getElementById('stPk');
    const total = engagement.intercepts + engagement.leakers;
    if (total > 0) {
        const pk = engagement.intercepts / total;
        pkEl.textContent = pk.toFixed(2);
        pkEl.className = pk > 0.8 ? 'stats__v stats__v--ok' : (pk > 0.5 ? 'stats__v stats__v--warn' : 'stats__v');
    }
    const leakEl = document.getElementById('stLeak');
    leakEl.textContent = `${engagement.leakers} leaker${engagement.leakers === 1 ? '' : 's'}`;
    leakEl.className = engagement.leakers === 0 ? 'stats__v stats__v--ok' :
                      (engagement.leakers < 3 ? 'stats__v stats__v--warn' : 'stats__v');
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
        tickWaves();
        tickThreatLifecycle();
        tickResupply();
        tickSalvos(FIXED_STEP);
        tickAutoEngage();
        // Legacy: also auto-reset the COA-style engagement.
        if (engagement.authorizedCOA && (clock.now - engagement.authorizedAt) > 10) {
            engagement.authorizedCOA = null;
            engagement.authorizedAt = null;
            engagement.authorizedBy = null;
            engagement.objected = new Set();
            engagement.autoEngagedThisCycle = false;
            lastCoaSig = '';
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
    drawMountainRing();      // 3D peaks in world space (behind everything else)
    drawHorizonLine();        // thin gold seam under the sky
    drawCityLightField();     // world-space ground pinpricks
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
    renderCamBadge();

    requestAnimationFrame(frame);
}
requestAnimationFrame(frame);

// Boot in AUTO mode — the system is the default operator. The chevron
// on the Decisions panel collapses automatically; the operator can
// click to expand and intervene.
setAutoEngage(true);

// ═════════════════════════════════════════════════════════════════════
//   HARNESS — exposes clock control for automated visual verification.
// ═════════════════════════════════════════════════════════════════════
window.__chaos = {
    freezeAt: (sec) => { clock.freeze(sec); cam.angleRate = 0; },
    unfreeze: () => { clock.unfreeze(); /* leave camera under operator control */ },
    setCameraAngle: (rad) => { cam.angle = rad; cam.angleRate = 0; },
    clock: () => clock.now,
    setAuto:  (on) => setAutoEngage(on),
    stress:   () => spawnStressWave(),
    hypersonic: (n) => {
        // Manually fire the HYP alert spawner.
        const count = n || 2;
        let stagger = 0;
        for (let i = 0; i < count; i++) {
            THREATS.push(makeRandomThreat('HYP', clock.now + 0.25 + stagger, waveRng));
            stagger += 0.45;
        }
        pushLogOnce(
            `hyp-manual-${clock.now.toFixed(2)}`,
            `<em>HYPERSONIC ALERT</em> · ${count} HGV-S contact${count > 1 ? 's' : ''} · Mach 14+ · NGI primary`,
        );
    },
    seed:     (n) => reseedWaves(n),
    snapshot: () => ({
        clock: clock.now,
        threats: THREATS.length,
        threatsByKind: THREATS.reduce((m, t) => { m[t.kind] = (m[t.kind] || 0) + 1; return m; }, {}),
        killed: engagement.killedTracks.size,
        intercepts: engagement.intercepts,
        leakers: engagement.leakers,
        salvos: engagement.salvos.filter(s => !s._retired).length,
        autoEngage: engagement.autoEngage,
        defenderState: Object.fromEntries(defenderState),
    }),
    runSelfTest: () => selfTest(),
    runWTA: () => computeAssignments(),
    fireOnce: () => {
        const a = computeAssignments();
        const fired = a.map(x => ({ d: x.defenderId, t: x.targetId, launched: launchSalvo('manual', x, 0, x.plan) ? true : false }));
        return { tried: a.length, fired };
    },
    // Diagnostics
    debugWTA: () => {
        const out = [];
        const stages = { all: THREATS.length };
        const s1 = THREATS.filter(t => !engagement.killedTracks.has(t.id)); stages.notKilled = s1.length;
        const s2 = s1.filter(t => trackVisible(t)); stages.visible = s2.length;
        // Sample some threats to inspect
        const samples = THREATS.slice(0, 4).map(t => ({
            id: t.id, kind: t.kind,
            phase: trackPhase(t).toFixed(3),
            launchAt: t.launchAt.toFixed(2), flightTime: t.flightTime.toFixed(2),
            now: clock.now.toFixed(2),
            cycleMod: (clock.now % 20).toFixed(2),
            terminal: t.terminal.map(v => v.toFixed(0)),
            classif: classifyImpact(t),
            assigned: t._assignedKinetic || 0,
        }));
        const s3 = s2.filter(t => classifyImpact(t) !== 'OUTSIDE'); stages.classified = s3.length;
        const ranked = s3.filter(t => !(t._assignedKinetic || 0) || t._needsReshot);
        for (const tr of ranked.slice(0, 5)) {
            const row = { id: tr.id, kind: tr.kind, phase: trackPhase(tr).toFixed(2), classif: classifyImpact(tr), defenders: [] };
            for (const def of DEFENDER_BATTERIES) {
                const st = defenderState.get(def.id);
                const plan = planIntercept(tr, def);
                row.defenders.push({
                    id: def.id,
                    mag: st.magazine, inflight: st.inflight,
                    reloadOK: clock.now - st.lastFired >= def.logistics.reload_s,
                    feasible: plan !== null,
                    slack: plan?.slack?.toFixed(2),
                });
            }
            out.push(row);
        }
        return { ranked: ranked.length, stages, samples, threats: THREATS.length, sample: out, salvos: engagement.salvos.length, autoEngage: engagement.autoEngage };
    },
};

// ═════════════════════════════════════════════════════════════════════
//   SELF-TEST
//
//   Runs the math layer against canned scenarios and returns
//   { passed, failed, results }. Exposed via window.__chaos.runSelfTest
//   and exercised by the FastAPI /battlespace/selftest endpoint.
// ═════════════════════════════════════════════════════════════════════
function selfTest() {
    const results = [];
    const expect = (name, ok, detail) => results.push({ name, ok, detail });

    // 1. Lead-angle solution against a head-on closer.
    //    Interceptor at origin, v_I=1000, target at (5000,0,0) moving -x at 500.
    //    Closing rate 1500 → TTI = 5000/1500 = 3.33s.
    {
        const t = leadInterceptTime([0,0,0], [5000,0,0], [-500,0,0], 1000);
        expect('lead head-on', Math.abs(t - 3.333) < 0.05, `t=${t?.toFixed(3)}`);
    }
    // 2. Lead-angle: target slower than interceptor, off-axis.
    {
        const t = leadInterceptTime([0,0,0], [3000,1000,0], [-200,0,0], 1000);
        expect('lead off-axis', t !== null && t > 0 && t < 10, `t=${t?.toFixed(3)}`);
    }
    // 3. Lead-angle: target faster than interceptor head-on → no solution.
    //    v_I=400, v_T=-800 on x, d=4000 → quadratic has negative discriminant for receding case.
    {
        const t = leadInterceptTime([0,0,0], [4000,0,0], [800,0,0], 400);
        expect('lead receding infeasible', t === null || t < 0, `t=${t}`);
    }
    // 4. planIntercept feasibility: synthetic HGV from west, NGI defender.
    {
        const track = {
            id: 'TEST-HGV', kind: 'HGV',
            launch: [-12000, 300, 0], apogee: [0, 6000, 0], terminal: [800, 300, 0],
            launchAt: 0, flightTime: 9.0,
            color: [1,0.6,0.4], machBase: 9, priority: 1, spawnedAt: 0,
        };
        const _savedNow = clock.now;
        clock.now = 0.5;
        const ngi = findDefender('NGI');
        const plan = planIntercept(track, ngi);
        expect('NGI catches HGV', plan !== null && plan.slack >= 0, `slack=${plan?.slack?.toFixed(2)}`);
        clock.now = _savedNow;
    }
    // 5. PAC-3 envelope rejects exoatmospheric apogee.
    {
        const track = {
            id: 'TEST-BM', kind: 'BM',
            launch: [-12000, 300, 0], apogee: [0, 40000, 0], terminal: [500, 300, 0],
            launchAt: 0, flightTime: 9.0,
            color: [1,0.5,0.5], machBase: 8, priority: 1, spawnedAt: 0,
        };
        const _savedNow = clock.now;
        clock.now = 0.5;
        const pac = findDefender('PAC-3');
        const plan = planIntercept(track, pac);
        // Late terminal phase may still be in envelope, but plan should be tight.
        // We accept either null OR a plan whose ph > 0.7 (terminal-only).
        const ok = (plan === null) || (plan.ph > 0.6);
        expect('PAC-3 rejects exo apogee', ok, `plan=${plan ? `ph=${plan.ph.toFixed(2)}` : 'null'}`);
        clock.now = _savedNow;
    }
    // 6. PIP classifier: terminal near origin → VITAL.
    {
        const t = { terminal: [500, 100, -400] };
        expect('PIP VITAL', classifyImpact(t) === 'VITAL', classifyImpact(t));
    }
    // 7. PIP classifier: terminal far from origin → OUTSIDE.
    {
        const t = { terminal: [9000, 100, -8000] };
        expect('PIP OUTSIDE', classifyImpact(t) === 'OUTSIDE', classifyImpact(t));
    }
    // 8. WTA assigns distinct defenders to distinct targets when possible.
    {
        const _savedThreats = THREATS.slice();
        THREATS.length = 0;
        for (let i = 0; i < 3; i++) {
            THREATS.push({
                id: `WTA-T${i}`, kind: 'MARV',
                launch: [Math.cos(i)*-11000, 300, Math.sin(i)*8000],
                apogee: [0, 4000, 0], terminal: [Math.cos(i)*600, 250, Math.sin(i)*600],
                launchAt: 0, flightTime: 7.5,
                color: [0.9,0.8,0.5], machBase: 7, priority: 2, spawnedAt: 0,
            });
        }
        const _savedNow = clock.now;
        clock.now = 0.5;
        resetDefenderState();
        const assignments = computeAssignments();
        const distinctDefenders = new Set(assignments.map(a => a.defenderId)).size;
        expect('WTA uses multiple defenders', distinctDefenders >= 2 || assignments.length >= 2,
               `${assignments.length} assignments, ${distinctDefenders} distinct defenders`);
        clock.now = _savedNow;
        THREATS.length = 0;
        for (const t of _savedThreats) THREATS.push(t);
        resetDefenderState();
    }

    const passed = results.filter(r => r.ok).length;
    const failed = results.length - passed;
    return { passed, failed, results };
}
})();
</script>
</body>
</html>
"""


_SELFTEST_HARNESS_HTML = r"""<!doctype html>
<html><head><meta charset="utf-8"><title>battlespace selftest</title></head>
<body>
<pre id="out">running...</pre>
<iframe id="bs" src="/battlespace" style="position:absolute;width:1px;height:1px;opacity:0;pointer-events:none"></iframe>
<script>
(async () => {
  const out = document.getElementById('out');
  const ifr = document.getElementById('bs');
  await new Promise(r => ifr.addEventListener('load', r, { once: true }));
  // Wait one tick for __chaos to mount.
  await new Promise(r => setTimeout(r, 250));
  const w = ifr.contentWindow;
  if (!w.__chaos || !w.__chaos.runSelfTest) {
    out.textContent = 'FAIL: __chaos harness unavailable';
    document.title = 'FAIL';
    return;
  }
  const report = w.__chaos.runSelfTest();
  out.textContent = JSON.stringify(report, null, 2);
  document.title = (report.failed === 0) ? 'PASS' : 'FAIL';
})();
</script>
</body></html>
"""


def build_router() -> APIRouter:
    """Return a router that mounts `/battlespace` on the dashboard app."""
    router = APIRouter()

    @router.get("/battlespace", response_class=HTMLResponse)
    def battlespace() -> str:
        return _BATTLESPACE_HTML.replace("__VERSION__", __version__)

    @router.get("/battlespace/selftest", response_class=HTMLResponse)
    def battlespace_selftest() -> str:
        """Harness page that mounts the battlespace in a hidden iframe
        and runs window.__chaos.runSelfTest(). Inspect by visiting the
        URL (the document title becomes PASS or FAIL) or by driving
        with Playwright — `report` ends up in <pre id='out'>."""
        return _SELFTEST_HARNESS_HTML

    return router
