"""Battlespace visualization — a Canvas-rendered, self-contained scene.

The page draws the missile-defense stage with real perspective math
(world -> view -> NDC -> pixel) and overlays the operator UI on top.
Everything is computed on the client; no server-side state is needed
beyond serving the HTML. The dashboard's other endpoints continue to
handle audit logs and engagements.
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
            --bg-deep:     #050B16;
            --bg-mid:      #0A1628;
            --bg-panel:    rgba(10, 22, 40, 0.82);
            --rule:        rgba(201, 169, 97, 0.32);
            --amber:       #DC9A3C;
            --crimson:     #DC5050;
            --mint:        #96DCA0;
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
            background: rgba(10, 22, 40, 0.92);
            border-bottom: 1px solid var(--rule);
            font-size: 11px;
            letter-spacing: 2.5px;
        }
        .mode-hud__letter {
            color: var(--gold);
            font-weight: 800;
            font-size: 16px;
            width: 24px;
        }
        .mode-hud__name {
            color: var(--bone);
            font-weight: 700;
            margin-right: 18px;
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
        }
        .decisions__title {
            color: var(--gold);
            font-size: 11px;
            letter-spacing: 5px;
            font-weight: 800;
            margin-bottom: 10px;
        }
        .decisions__rule {
            height: 1px;
            background: var(--rule);
            margin-bottom: 12px;
        }
        .coa {
            padding: 12px;
            margin-bottom: 10px;
            background: rgba(16, 28, 48, 0.92);
            border-left: 2px solid rgba(201, 169, 97, 0.45);
            border-top: 1px solid rgba(232, 226, 208, 0.08);
            border-right: 1px solid rgba(232, 226, 208, 0.08);
            border-bottom: 1px solid rgba(232, 226, 208, 0.08);
        }
        .coa--rec {
            border-left-color: var(--gold);
            background: rgba(22, 34, 56, 0.96);
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
            transition: width 100ms linear;
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
        }
        .coa__btn--p {
            background: var(--gold);
            color: var(--bg-mid);
        }
        .coa__btn--s {
            background: rgba(232, 226, 208, 0.06);
            color: rgba(232, 226, 208, 0.85);
            border: 1px solid rgba(232, 226, 208, 0.18);
        }
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
            transition: width 350ms ease;
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
        }

        /* ─── Calm Channel (bottom strip) ─── */
        .calm {
            bottom: 0; left: 0; right: 0;
            height: 32px;
            display: flex; align-items: center;
            padding: 0 24px;
            background: rgba(10, 22, 40, 0.92);
            border-top: 1px solid var(--rule);
            font-size: 10px;
            letter-spacing: 0.5px;
            overflow: hidden;
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
        }
        .callout__id {
            color: var(--gold);
            font-weight: 800;
            letter-spacing: 1.5px;
            font-size: 9.5px;
            display: block;
            margin-bottom: 1px;
        }

        /* ─── Watermark (lower-right) ─── */
        .wm {
            bottom: 44px; right: 24px;
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

        /* ─── Classification banner (top, between HUD and stage) ─── */
        .classbar {
            top: 38px; left: 0; right: 0;
            height: 18px;
            display: flex; align-items: center; justify-content: center;
            color: rgba(150, 220, 160, 0.85);
            background: rgba(8, 18, 30, 0.6);
            font-size: 9px;
            letter-spacing: 4px;
            font-weight: 800;
            border-bottom: 1px solid rgba(150, 220, 160, 0.18);
        }

        /* ─── Stats block (bottom-right) ─── */
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
        }
        .stats__v--ok   { color: rgb(150, 220, 160); }
        .stats__v--warn { color: rgb(220, 160, 60); }
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

    <div class="overlay decisions">
        <div class="decisions__title">DECISIONS</div>
        <div class="decisions__rule"></div>
        <div id="coaStack"></div>
        <div class="decisions__hint">ENTER AUTHORIZE · O OBJECT · E EXPLAIN</div>
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

    <div class="overlay calm">
        <span class="calm__label">LOG</span>
        <span class="calm__sep"></span>
        <div class="calm__list" id="calmList"></div>
    </div>

    <div class="overlay wm">
        <div class="wm__big">CHAOS ONE</div>
        <div>BATTLESPACE · v__VERSION__</div>
    </div>

    <div class="overlay classbar">UNCLASSIFIED // DEMO // FOR EVALUATION</div>

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

<script>
(() => {
'use strict';

// ─────────────────────────────────────────────────────────────────────
//   3D math — view + perspective projection
//   Right-handed world: +X east, +Y up, +Z north. Camera orbits the
//   origin. All distances in metres.
// ─────────────────────────────────────────────────────────────────────
const V = {
    sub: (a, b) => [a[0]-b[0], a[1]-b[1], a[2]-b[2]],
    add: (a, b) => [a[0]+b[0], a[1]+b[1], a[2]+b[2]],
    scale: (a, s) => [a[0]*s, a[1]*s, a[2]*s],
    dot: (a, b) => a[0]*b[0] + a[1]*b[1] + a[2]*b[2],
    cross: (a, b) => [
        a[1]*b[2] - a[2]*b[1],
        a[2]*b[0] - a[0]*b[2],
        a[0]*b[1] - a[1]*b[0],
    ],
    len: (a) => Math.hypot(a[0], a[1], a[2]),
    norm: (a) => {
        const L = Math.hypot(a[0], a[1], a[2]) || 1;
        return [a[0]/L, a[1]/L, a[2]/L];
    },
    lerp: (a, b, t) => [a[0]+(b[0]-a[0])*t, a[1]+(b[1]-a[1])*t, a[2]+(b[2]-a[2])*t],
    bezQ: (p0, p1, p2, t) => {
        const u = 1 - t;
        return [
            u*u*p0[0] + 2*u*t*p1[0] + t*t*p2[0],
            u*u*p0[1] + 2*u*t*p1[1] + t*t*p2[1],
            u*u*p0[2] + 2*u*t*p1[2] + t*t*p2[2],
        ];
    },
};

class Camera {
    constructor() {
        // Pivot is the origin of the battlespace (defender battery cluster).
        this.pivot     = [0, 0, 0];
        this.radius    = 14_000;    // metres back from pivot
        this.height    = 5_500;     // metres above pivot
        this.lookAtY   = 1_200;     // raise the look target so the camera tilts down slightly
        this.angle     = -2.05;     // radians; mild orbit
        this.angleRate = 0.020;     // radians per second
        this.fovDeg    = 42;
    }
    eye() {
        return [
            Math.sin(this.angle) * this.radius,
            this.height,
            Math.cos(this.angle) * this.radius,
        ];
    }
    target() { return [this.pivot[0], this.pivot[1] + this.lookAtY, this.pivot[2]]; }
    advance(dtSeconds) {
        this.angle += this.angleRate * dtSeconds;
    }
}

class Projector {
    constructor(camera, width, height) {
        this.cam = camera;
        this.w = width;
        this.h = height;
        // f = focal length in pixels. f = (h/2) / tan(fov/2).
        this.f = (height / 2) / Math.tan((camera.fovDeg * Math.PI / 180) / 2);
        this._rebuild();
    }
    _rebuild() {
        const eye = this.cam.eye();
        const tgt = this.cam.target();
        const forward = V.norm(V.sub(tgt, eye));
        const right = V.norm(V.cross(forward, [0, 1, 0]));
        const up = V.cross(right, forward);
        this.eye = eye;
        this.right = right;
        this.up = up;
        this.forward = forward;
    }
    resize(width, height) {
        this.w = width;
        this.h = height;
        this.f = (height / 2) / Math.tan((this.cam.fovDeg * Math.PI / 180) / 2);
    }
    refresh() { this._rebuild(); }
    project(p) {
        // Vector from eye to point, decomposed into the camera basis.
        const rel = V.sub(p, this.eye);
        const x =  V.dot(rel, this.right);
        const y =  V.dot(rel, this.up);
        const z =  V.dot(rel, this.forward);   // depth in front of camera
        if (z <= 1) return null;               // behind camera or too close
        return {
            sx: this.w / 2 + (x / z) * this.f,
            sy: this.h / 2 - (y / z) * this.f,
            depth: z,
        };
    }
}

// ─────────────────────────────────────────────────────────────────────
//   World content — range rings, defender batteries, threats
// ─────────────────────────────────────────────────────────────────────
const RING_RADII_M = [2_500, 5_000, 7_500, 10_000, 12_500];

const DEFENDER_BATTERIES = [
    { id: 'NGI',   pos: [-360, 0,    0], color: [0.55, 0.85, 1.00] },
    { id: 'SM-3',  pos: [   0, 0,  360], color: [0.55, 0.95, 0.78] },
    { id: 'PAC-3', pos: [ 360, 0,    0], color: [0.72, 0.95, 0.55] },
    { id: 'HEL',   pos: [   0, 0, -360], color: [1.00, 0.88, 0.55] },
];

const COMPASS = [
    { id: 'N', pos: [    0, 0,  13_200] },
    { id: 'E', pos: [13_200, 0,       0] },
    { id: 'S', pos: [    0, 0, -13_200] },
    { id: 'W', pos: [-13_200, 0,      0] },
];

// Three threats inbound from different bearings so the picture reads as
// a coordinated attack across multiple azimuths rather than one parallel
// stream. Terminal points clustered around 1.5 km of the defender cell.
const TRACKS = [
    {
        // West → East, far north of axis
        id: 'HGV-WRAITH-01',
        kind: 'HGV',
        launch:   [-12_400, 280,  4_200],
        apogee:   [ -1_400, 7_800,  1_700],
        terminal: [    900, 350,  -700],
        cycle: 16,
        phase: 0.00,
        color: [1.00, 0.66, 0.38],
        machBase: 9.4,
    },
    {
        // SW → NE through the cell
        id: 'HGV-WRAITH-02',
        kind: 'HGV',
        launch:   [ -8_600, 380, -10_400],
        apogee:   [ -1_000, 6_400,  -2_800],
        terminal: [    600, 360,    1_300],
        cycle: 18,
        phase: 0.34,
        color: [1.00, 0.55, 0.20],
        machBase: 8.8,
    },
    {
        // NE → SW, depressed trajectory
        id: 'MARV-VIPER-03',
        kind: 'MARV',
        launch:   [ 11_800, 240,  9_600],
        apogee:   [  3_400, 4_400,  3_800],
        terminal: [   -800, 320,   -500],
        cycle: 14,
        phase: 0.62,
        color: [0.95, 0.84, 0.55],
        machBase: 6.8,
    },
];

// Defended assets — civilian/critical sites that the operator is
// protecting. Rendered as faint hexagons offset from the defender cell.
const ASSETS = [
    { id: 'COMMAND',  pos: [-1_500, 0, -2_400] },
    { id: 'PORT',     pos: [ 2_800, 0, -3_400] },
    { id: 'GRID',     pos: [-3_400, 0,  2_200] },
];

const TRAIL_SAMPLES = 56;
const trails = TRACKS.map(() => []);

function trackPos(track, tNow) {
    // Cycle [0,1) — when t>1 the track has "splashed" and respawns.
    const phaseSec = ((tNow + track.phase * track.cycle) % (track.cycle + 1.5));
    const t = Math.min(1, phaseSec / track.cycle);
    return V.bezQ(track.launch, track.apogee, track.terminal, t);
}
function trackSpeedMach(track, tNow) {
    const phaseSec = ((tNow + track.phase * track.cycle) % (track.cycle + 1.5));
    const t = Math.min(1, phaseSec / track.cycle);
    // Mach number drops a little near apogee, peaks on the descent.
    const drop = 1 - 0.18 * Math.sin(Math.PI * t);
    return track.machBase * drop * (0.95 + 0.10 * t);
}

// ─────────────────────────────────────────────────────────────────────
//   Stars — deterministic by seed
// ─────────────────────────────────────────────────────────────────────
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
        // Stars only in the upper 70% of the sky (sub-horizon).
        out.push({
            x: rng() * width,
            y: rng() * (height * 0.62),
            r: 0.45 + rng() * 1.1,
            a: 0.18 + rng() * 0.48,
        });
    }
    return out;
}

// ─────────────────────────────────────────────────────────────────────
//   Canvas drawing
// ─────────────────────────────────────────────────────────────────────
const canvas = document.getElementById('stage');
const ctx = canvas.getContext('2d');
const cam = new Camera();
let proj = new Projector(cam, window.innerWidth, window.innerHeight);
let stars = [];
let starRng = mulberry32(0xC1A05);

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

function rgbStr(rgb, alpha) {
    const r = Math.max(0, Math.min(255, Math.round(rgb[0] * 255)));
    const g = Math.max(0, Math.min(255, Math.round(rgb[1] * 255)));
    const b = Math.max(0, Math.min(255, Math.round(rgb[2] * 255)));
    if (alpha === undefined) return `rgb(${r},${g},${b})`;
    return `rgba(${r},${g},${b},${alpha})`;
}

function drawSky(W, H) {
    const horizonY = horizonScreenY();
    // Upper sky: deep navy → mid navy → near-horizon dusk
    const grad = ctx.createLinearGradient(0, 0, 0, horizonY);
    grad.addColorStop(0.00, '#020815');
    grad.addColorStop(0.55, '#08182E');
    grad.addColorStop(1.00, '#0E2541');
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, W, horizonY);

    // Sub-horizon: graded ground panel that blends into bg
    const groundGrad = ctx.createLinearGradient(0, horizonY, 0, H);
    groundGrad.addColorStop(0.00, '#0A1B30');
    groundGrad.addColorStop(0.40, '#06101F');
    groundGrad.addColorStop(1.00, '#020815');
    ctx.fillStyle = groundGrad;
    ctx.fillRect(0, horizonY, W, H - horizonY);

    // Atmospheric halo at horizon
    const halo = ctx.createLinearGradient(0, horizonY - 36, 0, horizonY + 10);
    halo.addColorStop(0.00, 'rgba(201, 169, 97, 0.00)');
    halo.addColorStop(0.70, 'rgba(201, 169, 97, 0.05)');
    halo.addColorStop(1.00, 'rgba(201, 169, 97, 0.12)');
    ctx.fillStyle = halo;
    ctx.fillRect(0, horizonY - 36, W, 46);

    // Horizon hairline
    ctx.strokeStyle = 'rgba(201, 169, 97, 0.28)';
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(0, horizonY + 0.5);
    ctx.lineTo(W, horizonY + 0.5);
    ctx.stroke();
}

function horizonScreenY() {
    // Project a point at infinity on the ground plane. We approximate by
    // projecting a far world point along the camera's ground-plane forward.
    const eye = proj.eye;
    // direction projected onto ground plane
    const groundFwd = [proj.forward[0], 0, proj.forward[2]];
    const len = Math.hypot(groundFwd[0], groundFwd[2]) || 1;
    const dir = [groundFwd[0]/len, 0, groundFwd[2]/len];
    const farPoint = [eye[0] + dir[0]*200_000, 0, eye[2] + dir[2]*200_000];
    const p = proj.project(farPoint);
    if (!p) return proj.h * 0.5;
    return Math.max(60, Math.min(proj.h - 80, p.sy));
}

function drawStars() {
    ctx.save();
    for (const s of stars) {
        ctx.fillStyle = `rgba(232, 226, 208, ${s.a})`;
        ctx.beginPath();
        ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
        ctx.fill();
    }
    ctx.restore();
}

function drawRangeRings() {
    const segs = 96;
    for (let r = 0; r < RING_RADII_M.length; r++) {
        const radius = RING_RADII_M[r];
        const pts = [];
        for (let i = 0; i <= segs; i++) {
            const theta = (i / segs) * Math.PI * 2;
            const p = proj.project([Math.sin(theta) * radius, 0, Math.cos(theta) * radius]);
            pts.push(p);
        }
        // Alpha decreases with ring index (closest to widest), then by depth.
        const baseAlpha = 0.62 - r * 0.10;
        ctx.strokeStyle = `rgba(201, 169, 97, ${baseAlpha})`;
        ctx.lineWidth = r === 0 ? 1.4 : (r === RING_RADII_M.length - 1 ? 0.85 : 1.05);
        ctx.beginPath();
        let lastValid = false;
        for (let i = 0; i < pts.length; i++) {
            const p = pts[i];
            if (!p) { lastValid = false; continue; }
            if (!lastValid) ctx.moveTo(p.sx, p.sy);
            else            ctx.lineTo(p.sx, p.sy);
            lastValid = true;
        }
        ctx.stroke();

        // Tick label on the +X side (east).
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
    for (let i = 0; i < spokes; i++) {
        const theta = (i / spokes) * Math.PI * 2;
        const a = proj.project([0, 0, 0]);
        const b = proj.project([Math.sin(theta) * outer, 0, Math.cos(theta) * outer]);
        if (!a || !b) continue;
        ctx.strokeStyle = 'rgba(201, 169, 97, 0.14)';
        ctx.lineWidth = 0.7;
        ctx.beginPath();
        ctx.moveTo(a.sx, a.sy);
        ctx.lineTo(b.sx, b.sy);
        ctx.stroke();
    }
}

function drawCompass() {
    for (const c of COMPASS) {
        const head = proj.project([c.pos[0], 900, c.pos[2]]);
        const foot = proj.project([c.pos[0], -50,  c.pos[2]]);
        if (!head || !foot) continue;
        // Pillar
        const g = ctx.createLinearGradient(0, head.sy, 0, foot.sy);
        g.addColorStop(0.0, 'rgba(201, 169, 97, 0.0)');
        g.addColorStop(0.6, 'rgba(201, 169, 97, 0.85)');
        g.addColorStop(1.0, 'rgba(201, 169, 97, 0.45)');
        ctx.strokeStyle = g;
        ctx.lineWidth = 1.4;
        ctx.beginPath();
        ctx.moveTo(head.sx, head.sy);
        ctx.lineTo(foot.sx, foot.sy);
        ctx.stroke();

        // Letter
        ctx.fillStyle = 'rgba(201, 169, 97, 0.92)';
        ctx.font = '800 12px -apple-system, "SF Pro Display", sans-serif';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'alphabetic';
        ctx.fillText(c.id, head.sx, head.sy - 6);
        ctx.textAlign = 'start';
    }
}

function drawDefenderBatteries() {
    for (const b of DEFENDER_BATTERIES) {
        const base = proj.project(b.pos);
        const top  = proj.project([b.pos[0], 320, b.pos[2]]);
        if (!base || !top) continue;
        // Pedestal chevron — sized to read clearly from the orbit camera
        // without dominating the central cell.
        ctx.fillStyle = 'rgba(14, 26, 44, 0.96)';
        ctx.strokeStyle = rgbStr(b.color, 0.95);
        ctx.lineWidth = 1.3;
        const half = Math.max(4.0, 90 / Math.max(0.7, base.depth / 6500));
        ctx.beginPath();
        ctx.moveTo(base.sx - half, base.sy + half * 0.45);
        ctx.lineTo(base.sx + half, base.sy + half * 0.45);
        ctx.lineTo(top.sx,         top.sy);
        ctx.closePath();
        ctx.fill();
        ctx.stroke();

        // Halo at apex
        const glowR = half * 1.9;
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
        ctx.arc(top.sx, top.sy, 2.6, 0, Math.PI * 2);
        ctx.fill();

        // Label below pedestal
        const labelP = proj.project([b.pos[0], -110, b.pos[2]]);
        if (labelP) {
            ctx.fillStyle = rgbStr(b.color, 0.92);
            ctx.font = '800 9px ui-monospace, "SF Mono", Menlo, monospace';
            ctx.textAlign = 'center';
            ctx.textBaseline = 'top';
            ctx.fillText(b.id, labelP.sx, labelP.sy + 2);
            ctx.textAlign = 'start';
        }
    }
}

function drawAssets() {
    // Defended assets — small hex marks just above the ground plane,
    // muted bone color so they read as something to protect but don't
    // compete with the threats or defenders.
    for (const a of ASSETS) {
        const ground = proj.project(a.pos);
        if (!ground) continue;
        const half = Math.max(3, 22 / Math.max(0.5, ground.depth / 6500));
        // Hex
        ctx.strokeStyle = 'rgba(232, 226, 208, 0.55)';
        ctx.lineWidth = 1.0;
        ctx.beginPath();
        for (let i = 0; i < 6; i++) {
            const theta = (i / 6) * Math.PI * 2 + Math.PI / 6;
            const px = ground.sx + Math.cos(theta) * half;
            const py = ground.sy + Math.sin(theta) * half;
            if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
        }
        ctx.closePath();
        ctx.stroke();
        // Inner dot
        ctx.fillStyle = 'rgba(232, 226, 208, 0.72)';
        ctx.beginPath();
        ctx.arc(ground.sx, ground.sy, 1.5, 0, Math.PI * 2);
        ctx.fill();
        // Label
        ctx.fillStyle = 'rgba(232, 226, 208, 0.55)';
        ctx.font = '700 8px ui-monospace, "SF Mono", Menlo, monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'top';
        ctx.fillText(a.id, ground.sx, ground.sy + half + 2);
        ctx.textAlign = 'start';
    }
}

function drawSensorCoverage() {
    // Two notional sensor coverage arcs — a forward radar sector and a
    // mid-range engagement-zone arc. Drawn as faint ellipses on the
    // ground so the operator reads them as instruments, not solid geometry.
    const sectors = [
        { range: 11_000, halfAngle: Math.PI * 0.32, bearing: 0,                color: [0.78, 0.66, 0.38], alpha: 0.20 },
        { range:  7_000, halfAngle: Math.PI * 0.55, bearing: Math.PI * 0.72,   color: [0.55, 0.78, 0.95], alpha: 0.16 },
    ];
    const segs = 64;
    for (const s of sectors) {
        const start = s.bearing - s.halfAngle;
        const end   = s.bearing + s.halfAngle;
        const pts = [];
        for (let i = 0; i <= segs; i++) {
            const theta = start + (end - start) * (i / segs);
            pts.push(proj.project([Math.sin(theta) * s.range, 0, Math.cos(theta) * s.range]));
        }
        const a = proj.project([0, 0, 0]);
        if (!a) continue;

        // Fill the arc as a thin gradient slice
        ctx.beginPath();
        ctx.moveTo(a.sx, a.sy);
        let any = false;
        for (const p of pts) {
            if (!p) continue;
            ctx.lineTo(p.sx, p.sy);
            any = true;
        }
        if (any) {
            ctx.lineTo(a.sx, a.sy);
            ctx.fillStyle = rgbStr(s.color, s.alpha * 0.35);
            ctx.fill();
        }

        // Stroke the outer arc
        ctx.strokeStyle = rgbStr(s.color, s.alpha * 2.4);
        ctx.lineWidth = 0.9;
        ctx.beginPath();
        let started = false;
        for (const p of pts) {
            if (!p) { started = false; continue; }
            if (!started) ctx.moveTo(p.sx, p.sy);
            else          ctx.lineTo(p.sx, p.sy);
            started = true;
        }
        ctx.stroke();
    }
}

// ─────────────────────────────────────────────────────────────────────
//   Engagement allocation — defender↔target lines, intercept markers
// ─────────────────────────────────────────────────────────────────────
// COA-B allocates 2 NGI shots against the two HGVs + HEL screening.
// Allocations are list of {defender id, target id, kind}.
const ENGAGEMENT_ALLOC = [
    { defender: 'NGI',   target: 'HGV-WRAITH-01', kind: 'KINETIC' },
    { defender: 'NGI',   target: 'HGV-WRAITH-02', kind: 'KINETIC' },
    { defender: 'HEL',   target: 'MARV-VIPER-03', kind: 'DIRECTED' },
];

function findDefender(id) { return DEFENDER_BATTERIES.find(d => d.id === id); }
function findTrack(id)    { return TRACKS.find(t => t.id === id); }

// Solve interception with a simple iterative model:
//   - Interceptor leaves the defender now at constant speed v
//   - Threat follows its Bezier in time. Iterate: pick a candidate
//     time-of-intercept t_int, recompute threat position at that t,
//     compare travel time of interceptor to t_int. Converge in 4 steps.
function predictIntercept(track, defender, tNow, interceptorSpeedMps) {
    let tInt = 6.0; // initial guess in seconds
    for (let i = 0; i < 5; i++) {
        const target = trackPos(track, tNow + tInt);
        const travel = Math.hypot(
            target[0] - defender.pos[0],
            target[1] - defender.pos[1],
            target[2] - defender.pos[2],
        ) / interceptorSpeedMps;
        tInt = travel;
    }
    return { tti: tInt, point: trackPos(track, tNow + tInt) };
}

function drawEngagementAllocations(tNow) {
    const showAllocations = cyclePhase(tNow) >= 9 && cyclePhase(tNow) < 21;
    if (!showAllocations) return;

    for (const alloc of ENGAGEMENT_ALLOC) {
        const def = findDefender(alloc.defender);
        const tr  = findTrack(alloc.target);
        if (!def || !tr) continue;
        const interceptorV = alloc.kind === 'KINETIC' ? 5_400 : 299_792_458;  // m/s
        const { tti, point } = predictIntercept(tr, def, tNow, interceptorV);
        const defScreen = proj.project([def.pos[0], 240, def.pos[2]]);
        const intScreen = proj.project(point);
        if (!defScreen || !intScreen) continue;

        // Dashed allocation line, gold
        ctx.strokeStyle = 'rgba(201, 169, 97, 0.55)';
        ctx.setLineDash([6, 5]);
        ctx.lineWidth = 1.0;
        ctx.beginPath();
        ctx.moveTo(defScreen.sx, defScreen.sy);
        ctx.lineTo(intScreen.sx, intScreen.sy);
        ctx.stroke();
        ctx.setLineDash([]);

        // Intercept marker — diamond + bracket
        const r = 9;
        ctx.strokeStyle = 'rgba(201, 169, 97, 0.95)';
        ctx.lineWidth = 1.4;
        ctx.beginPath();
        ctx.moveTo(intScreen.sx,     intScreen.sy - r);
        ctx.lineTo(intScreen.sx + r, intScreen.sy);
        ctx.lineTo(intScreen.sx,     intScreen.sy + r);
        ctx.lineTo(intScreen.sx - r, intScreen.sy);
        ctx.closePath();
        ctx.stroke();

        // Label
        ctx.fillStyle = 'rgba(201, 169, 97, 0.95)';
        ctx.font = '800 9px ui-monospace, "SF Mono", Menlo, monospace';
        ctx.textAlign = 'start';
        ctx.textBaseline = 'middle';
        const txt = `${alloc.defender}→${alloc.target.split('-').slice(-1)[0]} · TTI ${tti.toFixed(1)}s`;
        // Background plate so text reads against any layer
        const m = ctx.measureText(txt);
        ctx.fillStyle = 'rgba(10, 22, 40, 0.78)';
        ctx.fillRect(intScreen.sx + r + 4, intScreen.sy - 8, m.width + 8, 14);
        ctx.fillStyle = 'rgba(201, 169, 97, 0.95)';
        ctx.fillText(txt, intScreen.sx + r + 8, intScreen.sy);
    }
}

function drawImpactPredictions(tNow) {
    // Draw an "X" + dashed ring at each track's predicted terminal point.
    // Pulses brighter as the track gets closer to that terminal.
    for (let ti = 0; ti < TRACKS.length; ti++) {
        const tr = TRACKS[ti];
        const phaseSec = ((tNow + tr.phase * tr.cycle) % (tr.cycle + 1.5));
        const t = Math.min(1, phaseSec / tr.cycle);
        const impact = proj.project([tr.terminal[0], 0, tr.terminal[2]]);
        if (!impact) continue;
        const urgency = Math.pow(t, 1.8);     // 0..1 — brighter near impact
        const alpha = 0.35 + urgency * 0.55;
        ctx.strokeStyle = rgbStr(tr.color, alpha);
        ctx.lineWidth = 0.9;
        // Dashed ring
        ctx.setLineDash([4, 4]);
        const r = 10 + urgency * 8;
        ctx.beginPath();
        ctx.arc(impact.sx, impact.sy, r, 0, Math.PI * 2);
        ctx.stroke();
        ctx.setLineDash([]);
        // Cross hairs
        ctx.beginPath();
        ctx.moveTo(impact.sx - r * 0.7, impact.sy);
        ctx.lineTo(impact.sx + r * 0.7, impact.sy);
        ctx.moveTo(impact.sx, impact.sy - r * 0.7);
        ctx.lineTo(impact.sx, impact.sy + r * 0.7);
        ctx.stroke();

        // Label
        ctx.fillStyle = rgbStr(tr.color, alpha);
        ctx.font = '700 8.5px ui-monospace, "SF Mono", Menlo, monospace';
        ctx.fillText(`PIP · ${tr.id.split('-').slice(-2).join('-')}`, impact.sx + r + 3, impact.sy - 2);
    }
}

function drawTrails(tNow) {
    for (let ti = 0; ti < TRACKS.length; ti++) {
        const tr = TRACKS[ti];
        const samples = trails[ti];
        if (samples.length < 2) continue;
        for (let i = 1; i < samples.length; i++) {
            const a = proj.project(samples[i - 1]);
            const b = proj.project(samples[i]);
            if (!a || !b) continue;
            const tAge = i / samples.length;        // 0 = oldest, 1 = newest
            const alpha = Math.pow(tAge, 1.6);      // bias toward fresh end
            const width = 0.6 + tAge * 2.4;
            // Fade hot color into deep-navy sky
            const c = [
                tr.color[0] * (0.30 + 0.70 * tAge),
                tr.color[1] * (0.30 + 0.70 * tAge),
                tr.color[2] * (0.30 + 0.70 * tAge),
            ];
            ctx.strokeStyle = rgbStr(c, alpha * 0.95);
            ctx.lineWidth = width;
            ctx.beginPath();
            ctx.moveTo(a.sx, a.sy);
            ctx.lineTo(b.sx, b.sy);
            ctx.stroke();
        }
    }
}

function drawTracks(tNow) {
    for (let ti = 0; ti < TRACKS.length; ti++) {
        const tr = TRACKS[ti];
        const p = trackPos(tr, tNow);
        const proj1 = proj.project(p);
        if (!proj1) continue;

        // depth-scaled "size"
        const r = Math.max(2.5, 220 / Math.max(0.5, proj1.depth / 800));

        // outer glow
        const g = ctx.createRadialGradient(proj1.sx, proj1.sy, 0, proj1.sx, proj1.sy, r * 4);
        g.addColorStop(0.00, rgbStr(tr.color, 0.95));
        g.addColorStop(0.35, rgbStr(tr.color, 0.42));
        g.addColorStop(1.00, rgbStr(tr.color, 0.00));
        ctx.fillStyle = g;
        ctx.beginPath();
        ctx.arc(proj1.sx, proj1.sy, r * 4, 0, Math.PI * 2);
        ctx.fill();

        // hot core
        ctx.fillStyle = rgbStr([1, 1, 1], 0.98);
        ctx.beginPath();
        ctx.arc(proj1.sx, proj1.sy, r * 0.55, 0, Math.PI * 2);
        ctx.fill();

        // colored ring around core
        ctx.strokeStyle = rgbStr(tr.color, 0.95);
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.arc(proj1.sx, proj1.sy, r * 1.05, 0, Math.PI * 2);
        ctx.stroke();
    }
}

function positionCallouts(tNow) {
    const container = document.getElementById('callouts');
    // Re-use existing nodes by id; create lazily.
    for (let ti = 0; ti < TRACKS.length; ti++) {
        const tr = TRACKS[ti];
        const p = trackPos(tr, tNow);
        const proj1 = proj.project(p);
        const speed = trackSpeedMach(tr, tNow);
        const altKm = (p[1] / 1000).toFixed(1);
        const rangeKm = (Math.hypot(p[0], p[2]) / 1000).toFixed(1);
        let node = document.getElementById('co-' + tr.id);
        if (!node) {
            node = document.createElement('div');
            node.id = 'co-' + tr.id;
            node.className = 'callout';
            node.innerHTML = `
                <span class="callout__id"></span>
                <span class="callout__data"></span>
            `;
            container.appendChild(node);
        }
        if (!proj1) { node.style.display = 'none'; continue; }
        node.style.display = '';
        node.style.left = (proj1.sx + 18) + 'px';
        node.style.top  = (proj1.sy - 4) + 'px';
        node.querySelector('.callout__id').textContent = tr.id;
        node.querySelector('.callout__data').textContent =
            `${tr.kind} · CONFIDENT · M${speed.toFixed(1)} · ALT ${altKm} km · RNG ${rangeKm} km`;
    }
}

// ─────────────────────────────────────────────────────────────────────
//   UI panels — Mode HUD, Decisions, Adversary Mirror, Calm Channel
// ─────────────────────────────────────────────────────────────────────
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

// Demo cycle — Mode A → B at 6s, propose COAs at 9s, authorize COA-B at 18s,
// expire others at 21s, restore A at 24s, restart 27s.
const CYCLE = 28;
let cycleStart = performance.now() / 1000;
let frozenPhase = null;

function cyclePhase(now) {
    if (frozenPhase !== null) return frozenPhase;
    return (now - cycleStart) % CYCLE;
}

function modeAt(t) {
    if (t >= 5 && t < 24) return { letter: 'B', name: 'SENSOR DEGRADED', color: 'amber' };
    return { letter: 'A', name: 'NOMINAL', color: 'gold' };
}

function activeCOAs(t) {
    if (t < 9 || t >= 21) return [];
    const out = [];
    if (t < 18) {
        out.push({ ...COAS['COA-B'], remaining: clamp(COAS['COA-B'].countdownSec - (t - 9), 0, COAS['COA-B'].countdownSec) });
        out.push({ ...COAS['COA-A'], remaining: clamp(COAS['COA-A'].countdownSec - (t - 9), 0, COAS['COA-A'].countdownSec) });
        out.push({ ...COAS['COA-C'], remaining: clamp(COAS['COA-C'].countdownSec - (t - 9), 0, COAS['COA-C'].countdownSec) });
    }
    return out;
}
function clamp(v, lo, hi) { return Math.max(lo, Math.min(hi, v)); }

function renderHUD(t) {
    const m = modeAt(t);
    const ltr = document.getElementById('modeLetter');
    const nm  = document.getElementById('modeName');
    const hud = document.getElementById('modeHud');
    ltr.textContent = m.letter;
    nm.textContent = m.name;
    hud.style.borderBottomColor = m.color === 'amber' ? 'rgba(220, 160, 60, 0.85)' : 'var(--rule)';
    ltr.style.color = m.color === 'amber' ? '#DC9A3C' : 'var(--gold)';
}

function renderDecisions(t) {
    const stack = document.getElementById('coaStack');
    const coas = activeCOAs(t);
    if (coas.length === 0) {
        stack.innerHTML = `<div class="decisions__empty">STAND BY — NO ACTIVE COA</div>`;
        return;
    }
    stack.innerHTML = coas.map(c => {
        const remPct = (c.remaining / c.countdownSec) * 100;
        const badge = c.rec ? '<span class="coa__badge">RECOMMENDED</span>' : '';
        return `
            <div class="coa ${c.rec ? 'coa--rec' : ''}">
                <div class="coa__top">
                    <span class="coa__id">${c.id}</span>
                    ${badge}
                </div>
                <div class="coa__head">${c.head}</div>
                <div class="coa__why">${c.why}</div>
                <div class="coa__metrics">
                    ${c.metrics.map(m => `<div>${m}</div>`).join('')}
                </div>
                <div class="coa__bar"><div class="coa__bar-fill" style="width:${remPct}%"></div></div>
                <div class="coa__btns">
                    <button class="coa__btn coa__btn--p">AUTHORIZE</button>
                    <button class="coa__btn coa__btn--s">OBJECT</button>
                </div>
            </div>
        `;
    }).join('');
}

const HYPS_BASE = [
    { name: 'Charlie-7 saturation HGV + decoy cloud', weight: 0.63 },
    { name: 'Bravo-3 probe, no follow-on',             weight: 0.24 },
    { name: 'Off-distribution / unknown',              weight: 0.13 },
];
const sparkHistory = [];
for (let i = 0; i < 32; i++) sparkHistory.push(1.0 + (Math.sin(i*0.42) + Math.cos(i*0.17)) * 0.08);

function renderAdversary(t) {
    // Weights drift slowly so it doesn't look static.
    const drift = Math.sin(t * 0.5) * 0.04;
    const hyps = HYPS_BASE.map((h, i) => ({
        name: h.name,
        weight: clamp(h.weight + (i === 0 ? drift : -drift / 2), 0.04, 0.92),
        delta: (i === 0 ? drift : -drift) > 0.005 ? '↑' : (i === 0 ? drift : -drift) < -0.005 ? '↓' : '→',
    }));
    // Renormalize
    const sum = hyps.reduce((s, h) => s + h.weight, 0);
    hyps.forEach(h => h.weight /= sum);

    document.getElementById('hypStack').innerHTML = hyps.map(h => `
        <div class="hyp">
            <span class="hyp__w">${Math.round(h.weight * 100)}%</span>
            <span class="hyp__n">${h.name}</span>
            <span class="hyp__d">${h.delta}</span>
            <span class="hyp__bar"><span class="hyp__bar-fill" style="width:${h.weight * 100}%"></span></span>
        </div>
    `).join('');

    // Cost imposition advances ~once per second.
    const cost = 1.0 + 0.18 * Math.sin(t * 0.20) + 0.05 * Math.cos(t * 0.83);
    sparkHistory.push(cost);
    while (sparkHistory.length > 32) sparkHistory.shift();
    const min = Math.min(...sparkHistory);
    const max = Math.max(...sparkHistory);
    const range = Math.max(0.05, max - min);
    document.getElementById('costSpark').innerHTML = sparkHistory.map(v => {
        const h = 15 + ((v - min) / range) * 85;
        return `<div style="height:${h}%"></div>`;
    }).join('');
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
    'COA authorized <em>COA-B</em> · 2× NGI + HEL release',
    'mode B → A  <em>NOMINAL</em>',
    'audit chain  <em>OK · 14 entries</em>',
];
function renderStats(now) {
    const t = cyclePhase(now);
    const engaging = (t >= 9 && t < 21) ? ENGAGEMENT_ALLOC.length : 0;
    document.getElementById('stEng').textContent = `${engaging} / ${TRACKS.length}`;

    // Primary TTI = the smallest TTI among allocations against the
    // highest-priority threat (HGV-WRAITH-01).
    let primaryTTI = null;
    for (const alloc of ENGAGEMENT_ALLOC) {
        if (alloc.target !== 'HGV-WRAITH-01') continue;
        const def = findDefender(alloc.defender);
        const tr  = findTrack(alloc.target);
        if (!def || !tr) continue;
        const v = alloc.kind === 'KINETIC' ? 5_400 : 299_792_458;
        const { tti } = predictIntercept(tr, def, now, v);
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

function renderCalm(t) {
    // Rotate the list so it reads as a recent-events ticker.
    const k = Math.floor(t * 0.4) % CALM_BASE.length;
    const ordered = CALM_BASE.slice(k).concat(CALM_BASE.slice(0, k));
    document.getElementById('calmList').innerHTML = ordered.map(s => `<span>${s}</span>`).join('');
}

// ─────────────────────────────────────────────────────────────────────
//   Frame loop
// ─────────────────────────────────────────────────────────────────────
let lastTs = performance.now();
let trailAccum = 0;

function frame(ts) {
    const now = ts / 1000;
    const dt = (ts - lastTs) / 1000;
    lastTs = ts;

    cam.advance(dt);
    proj.refresh();

    // Update trails at ~30Hz
    trailAccum += dt;
    if (trailAccum > 1 / 30) {
        trailAccum = 0;
        for (let ti = 0; ti < TRACKS.length; ti++) {
            trails[ti].push(trackPos(TRACKS[ti], now));
            if (trails[ti].length > TRAIL_SAMPLES) trails[ti].shift();
        }
    }

    // Draw
    drawSky(proj.w, proj.h);
    drawStars();
    drawRadialSpokes();
    drawRangeRings();
    drawSensorCoverage();
    drawImpactPredictions(now);
    drawAssets();
    drawCompass();
    drawDefenderBatteries();
    drawTrails(now);
    drawEngagementAllocations(now);
    drawTracks(now);
    positionCallouts(now);

    // Panels
    const t = cyclePhase(now);
    renderHUD(t);
    renderDecisions(t);
    renderAdversary(now);
    renderStats(now);
    renderCalm(now);

    requestAnimationFrame(frame);
}
requestAnimationFrame(frame);

// Expose for the harness: lets the test runner freeze time / pump frames.
window.__chaos = {
    setCycle: (sec) => { cycleStart = (performance.now() / 1000) - sec; },
    setCameraAngle: (rad) => { cam.angle = rad; cam.angleRate = 0; },
    freezeAt: (sec) => {
        frozenPhase = sec;
        cam.angleRate = 0;
    },
    unfreeze: () => {
        frozenPhase = null;
        cam.angleRate = 0.020;
        cycleStart = performance.now() / 1000;
    },
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
