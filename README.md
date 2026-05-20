<p align="center">
  <img src="assets/Chaos.jpg" alt="Chaos One" width="280" />
</p>

<h1 align="center">Chaos One</h1>

<p align="center">
  <a href="https://github.com/EgorKhaklin/chaos-one/actions/workflows/backend.yml"><img src="https://github.com/EgorKhaklin/chaos-one/actions/workflows/backend.yml/badge.svg?branch=main" alt="backend" /></a>
  <a href="https://github.com/EgorKhaklin/chaos-one/actions/workflows/codeql.yml"><img src="https://github.com/EgorKhaklin/chaos-one/actions/workflows/codeql.yml/badge.svg?branch=main" alt="codeql" /></a>
  <a href="https://github.com/EgorKhaklin/chaos-one/blob/main/backend/pyproject.toml"><img src="https://img.shields.io/badge/python-3.11%20%7C%203.12-3776AB?logo=python&logoColor=white" alt="python" /></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-blue" alt="license" /></a>
</p>

Conceptual decision-support interface for next-generation air and missile
defense — a real-time Iron-Dome-flavoured battlespace renderer driven by
explicit linear algebra in the browser, backed by a Python FastAPI service
for audit, scenario replay, and operator state.

The system addresses the late-2020s threat environment — hypersonic glide
vehicles, drone and missile swarms, saturation attacks, electronic warfare,
cyber-degraded sensors — as **decision superiority under uncertainty**.
Calm under tempo, honest uncertainty, operator-owned authority,
cryptographically signed audit.

---

## What you see at `/battlespace`

The headline surface. Open `http://127.0.0.1:8124/battlespace` and you
get a continuous, never-resetting battlespace driven by a procedural
threat picture and an Iron Dome doctrine controller. The system is
**armed in AUTO on page load** — the four batteries engage incoming
threats without operator input. You can intervene, zoom, orbit,
collapse panels, drop stress waves on demand.

| Layer | What it shows |
|---|---|
| **3D city** | ~74 procedural cuboid buildings on a 180-m street grid inside the defender ring. Four named landmark towers (COMMAND / PORT / GRID / NODE-7). Lit windows flicker per building. Painter's-algorithm depth sort. |
| **3D defender pyramids** | Four batteries on a 3 km circle — NGI, SM-3, PAC-3, IRON-D. Each is a Lambertian-shaded tetrahedron projected through the same 4×4 view/projection matrices as the rest of the world. |
| **3D mountain ring** | 72 procedural tetrahedra in a band at 18-42 km. Near + far ranges, distance fade into atmospheric haze. |
| **3D threats** | Procedural waves of HGV / BM / MARV / CRUISE / DRONE / HYP, each on its own Bezier trajectory. Spawn from beyond the mountains (22-92 km). |
| **Salvos** | Real interceptor physics — boost + pitchover + finite turn-rate + proportional-navigation lead-angle guidance. Per-defender interceptor profiles. |
| **Mode HUD / Decisions / Adversary Mirror / Engagement State / Calm Channel / Weapons Bay / Compass tape / Radar inset** | Operator surfaces, all collapsible via chevron headers. |

---

## Doctrine

### Threats

Six classes — each with its own apogee band, flight time, spawn radius, Mach range, priority:

| Class | Mach | Apogee | Spawn | Priority |
|---|---|---|---|---|
| HGV | 9.0 | 7.5–11 km | 46–62 km | 1 |
| BM | 7.5 | 10–16 km | 48–65 km | 1 |
| HYP | **14.0+** | 16–24 km | **70–92 km** | 1 |
| MARV | 6.8 | 5–8 km | 36–50 km | 2 |
| CRUISE | 0.85 | 0.3–0.7 km | 28–42 km | 3 |
| DRONE | 0.3 | 0.2–0.4 km | 22–36 km | 4 |

Two parallel spawners — a WAVE of 3-6 threats every 6-10 s, and a
constant DRIZZLE of 1 low-priority threat every 1.4-2.6 s — so the
picture is never empty. A dedicated HYPERSONIC alert fires 1-2
Mach-14+ HYP threats every 38-68 s for stress-test value.

### Defenders

Four batteries at the cardinal points of a 3 km circle. Each carries an
explicit envelope, interceptor profile, magazine, reload window, and
per-class kill-probability matrix:

| Battery | Cruise | Range | Magazine | Best vs |
|---|---|---|---|---|
| **NGI** | Mach 10 | 14 km / 100 km alt | 24 | HGV / BM / HYP (Pk 0.58) |
| **SM-3** | Mach 7.6 | 11 km / 60 km alt | 32 | MARV / BM upper-tier |
| **PAC-3** | Mach 5 | 7 km / 25 km alt | 48 | MARV terminal / CRUISE |
| **IRON-D** | Mach 4.4 | 9 km / 18 km alt | 60 | CRUISE / DRONE |

Logistics tail: each battery trickles one round back into its magazine
every 2.5–6 s, so the system reaches a drain/refill equilibrium and can
operate indefinitely.

### Engagement controller

Three layers of math, all running every fixed 60 Hz step:

1. **PIP filter** — `classifyImpact(track)` drops threats whose predicted
   impact lies outside the 8 km defended bubble. Iron Dome's signature
   efficiency move: don't spend an interceptor on something that won't
   hit anything.
2. **Weapon-target assignment** — priority-greedy with Iron-Dome biases.
   Urgency score combines time-to-impact, classification (VITAL /
   PERIPHERAL), and threat priority. Per (threat, defender) pair we
   score `Pk × (slack + 0.4)` under envelope + magazine + reload +
   max-in-flight gates. High-value targets in the vital bubble get a
   **2-interceptor salvo** (shoot-shoot-look doctrine). Re-engages on
   miss automatically.
3. **Lead-angle guidance** — each interceptor solves the quadratic
   collision-course equation every frame:

   `(v_I² − |v_T|²) t² − 2(d · v_T) t − |d|² = 0`,  `d = r_T(now) − r_I(now)`

   target velocity `v_T` is the numerical derivative of the threat's
   Bezier trajectory. Smallest positive root `t*` is the lead time;
   missile aims at `r_T(now + t*)` and recomputes.

### Salvo state machine

| State | Meaning |
|---|---|
| `queued` | Committed, waiting for radar acquisition. Magazine already debited. Pulsing amber arming reticle on the launcher. |
| `inflight` | Acquired and flying. Lead-pursuit guidance, trail at 30 Hz. |
| **`orphaned`** | Target was killed by another interceptor, leaked, or fuze-missed. Coasts on last velocity for 1.4 s, then safety-fuze self-destruct splash. **A missile is only retired on a confirmed hit** — everything else coasts visibly. |
| `splash` | Confirmed kill. Splash effect plays then GC'd. |
| `done` | Fully retired. |

### Splash kinds (visually distinct)

| Kind | Look | Meaning |
|---|---|---|
| `kill` | Amber/yellow ring, 60 px max, 1.1 s | Successful intercept |
| `leak` | Crimson + black smoke ring, 90 px max, 1.6 s, red X marker | Threat hit the city |
| `selfdestruct` | Compact white-blue flash | Interceptor self-destructed (orphan / fuze-miss) |

---

## Math (browser-side)

The renderer is a single self-contained HTML page served from FastAPI —
no external assets — implementing its own:

- **4×4 view/projection matrices** (`M4.perspective`, `M4.lookAt`,
  `M4.multiply`, `M4.apply`) — the same pipeline a hardware GPU
  uses, no ad-hoc tricks.
- **Catmull-Rom interpolation** between trail samples for
  C¹-continuous curves regardless of the sampling rate.
- **Painter's algorithm** for face-sorted depth on the city,
  mountain ring, and defender pyramids.
- **Procedural noise** (seeded mulberry32) for deterministic
  reproducible waves (`window.__chaos.seed(n)`).
- **Lambertian shading** with global sun-direction normal-dot
  computation on every 3D surface.
- **Proximity-fuze Pk** rolled on detonation — misses don't claim
  ghost kills.

Self-test: `GET /battlespace/selftest` opens a hidden iframe and runs
`window.__chaos.runSelfTest()` against canned scenarios — lead-angle
(head-on, off-axis, receding-infeasible), `planIntercept` feasibility
(NGI vs HGV catch, PAC-3 envelope reject), PIP classification, and
WTA optimality (4 distinct defenders distributed across 3 threats).
Document title becomes `PASS` or `FAIL`.

---

## Controls

| Input | Effect |
|---|---|
| Mouse wheel on canvas | Zoom (clamped 2.5–60 km) |
| Left-drag canvas | Orbit + elevation |
| **C** | Toggle FREE-CAM lock |
| **Home** / `=` | Reset camera |
| **T** | Toggle AUTO-ENGAGE |
| **S** | Drop a 14-threat stress wave |
| **Enter** / **A** | Authorize the recommended COA (operator-in-loop) |
| **O** | Object to the recommended COA |
| Click panel chevrons | Collapse / expand Decisions / Adversary Mirror / Engagement State |

Browser console harness (`window.__chaos`):

```js
__chaos.snapshot()           // engagement state JSON
__chaos.runSelfTest()        // 8-test math suite
__chaos.runWTA()             // current assignment list
__chaos.fireOnce()           // fire one WTA pass manually
__chaos.stress()             // 14-threat saturation wave
__chaos.hypersonic(n)        // drop n HYP threats now
__chaos.seed(n)              // reseed the wave generator
__chaos.freezeAt(sec)        // pin clock + camera for testing
__chaos.unfreeze()           // resume
```

---

## Quickstart

```
git clone https://github.com/EgorKhaklin/chaos-one.git
cd chaos-one/backend
make install               # .venv + dev extras
make protos                # generate gRPC stubs
.venv/bin/uvicorn chaos_backend.web.app:app --port 8124 --host 127.0.0.1 --reload
open http://127.0.0.1:8124/battlespace
```

Or build the single-binary launcher:

```
cd backend
make package               # PyInstaller → dist/chaos-one
./dist/chaos-one --port 8123
```

---

## Architecture

```
                    browser
                       │
                       │  /battlespace        canvas + math + JS
                       │  /battlespace/selftest
                       │  /ops                operator dashboard
                       │  /play /play/stream  scenario runner + SSE
                       │  /engagements*       audit / diff / rerun
                       │
                    FastAPI
                  ┌────┴────┐
                  │ web/    │ landing + battlespace + operations
                  │ audit/  │ SHA-256 Merkle-chained JSONL writer / reader / verifier
                  │ storage/│ SQLite engagement catalog
                  │ simulation/  RK4 kinematics, scenario builders
                  │ services/    discrimination / COA / adversary stubs
                  │ proto/  │ gRPC contracts (for external integrations)
                  └─────────┘
```

The battlespace renderer is **client-side** — once the HTML is served,
the math layer, threat generator, defender doctrine, WTA, and physics
all run in the browser. The FastAPI app owns audit, scenario replay,
the engagement catalog, and the operator dashboard. They communicate
only via the bus of HTML / SSE / JSON.

---

## Repository layout

```
chaos-one/
  backend/
    src/chaos_backend/
      web/
        battlespace.py       Iron Dome renderer (single self-contained HTML + JS)
        operations.py        Live operator dashboard (/ops)
        app.py               FastAPI application
      audit/                 SHA-256 Merkle-chained JSONL writer + verifier
      simulation/            RK4 kinematics, scenario builders, gRPC streaming
      services/              Discrimination / COA / adversary stubs
      storage/               SQLite engagement catalog
      grpc_adapters.py       proto ↔ dataclass translation
      server.py              gRPC server entry
      cli.py                 chaos-backend-cli
      launcher.py            chaos-one (single-binary entrypoint)
      observability.py       structlog + request_id middleware
    tests/                   pytest suite (140+ tests)
    Makefile                 install / protos / lint / type / test / ci / bench / package / clean
    chaos-one.spec           PyInstaller spec for the launcher
  unity/                     Unity 6 HDRP scaffold (deprecated front-end;
                             retained because some HDRP-shader patterns
                             informed the canvas pipeline)
  .github/workflows/         CI: ruff + mypy + pytest + CodeQL
  LICENSE                    Apache 2.0
```

> **Note on Unity.** Earlier versions of Chaos One used Unity 6 HDRP
> as the front end. The canvas-based browser renderer at
> `/battlespace` superseded it — same architectural concepts (event
> bus, audit chain, decision layers) but with deterministic math
> that's self-testable in any browser. The Unity tree is kept as a
> reference but is not the active surface.

---

## CI / quality

- GitHub Actions runs `ruff check`, `ruff format`, `mypy strict`, and
  `pytest` with coverage on Python 3.11 + 3.12 against `backend/`.
- CodeQL security analysis on every push.
- Pre-commit hooks: ruff + whitespace + YAML/TOML/JSON validation +
  large-file guard. Enable with
  `pip install pre-commit && pre-commit install`.
- Browser math layer has its own 8-test self-test via
  `/battlespace/selftest`.

---

## Status

Conceptual prototype. The system is **not deployed**, has not been
adjudicated against operational standards, and is not a substitute for
real-world fielded systems. Discrimination is a mock ensemble that
returns deterministic scripted votes; the COA generator returns canned
bundles; the adversary model produces sinusoidally drifting weights.
These are placeholders for the ML and game-theoretic work that would
replace them in a production system.

What is real: the math (4×4 projection, lead-angle quadratic, WTA
greedy assignment, painter's-algorithm depth sort), the engagement
flow (procedural waves → WTA → lead-pursuit physics → splash / leak /
self-destruct), the audit chain (SHA-256 Merkle JSONL), the test
discipline. The shape of the system is what the prototype
demonstrates; the inside of each box is intentionally stubbed.

---

## License

Apache 2.0. See [LICENSE](LICENSE).
