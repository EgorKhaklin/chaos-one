"""Command-line interface to the chaos-backend services.

Lets the Python side be exercised end-to-end without Unity attached:

    chaos-backend-cli scenario peer_salvo --seed 42
    chaos-backend-cli classify --track-id TRK-001 --sample-count 1
    chaos-backend-cli generate-coa --tracks A B C D --envelope ROE-2
    chaos-backend-cli playbook
    chaos-backend-cli trajectory --apogee 35000 --duration 120 --dt 0.5

All commands print stable JSON to stdout so they can be piped into jq.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from typing import Any

import numpy as np

from chaos_backend.audit import (
    AuditLogReader,
    AuditLogVerifier,
    AuditLogWriter,
    render_html_from_path,
)
from chaos_backend.services.adversary_model import AdversaryModelService
from chaos_backend.services.coa_generator import CourseOfActionService
from chaos_backend.services.discrimination import DiscriminationService
from chaos_backend.simulation import scenarios
from chaos_backend.simulation.kinematics import ThreatState, trajectory
from chaos_backend.simulation.scenario_runner import run as run_scenario


def _json_default(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        return asdict(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return str(obj)


def _emit(payload: Any) -> None:
    json.dump(payload, sys.stdout, indent=2, default=_json_default)
    sys.stdout.write("\n")


def cmd_scenario(args: argparse.Namespace) -> int:
    try:
        kind = scenarios.ScenarioKind(args.kind)
    except ValueError:
        print(f"unknown scenario kind: {args.kind}", file=sys.stderr)
        return 2

    scenario = scenarios.build(kind, seed=args.seed)
    _emit(
        {
            "kind": scenario.kind.value,
            "seed": scenario.seed,
            "duration_s": scenario.duration_s,
            "event_count": len(scenario.events),
            "events": [
                {
                    "t": round(event.timestamp_s, 3),
                    "type": event.event_type,
                    "payload": event.payload,
                }
                for event in scenario.events
            ],
        }
    )
    return 0


def cmd_classify(args: argparse.Namespace) -> int:
    service = DiscriminationService()
    result = service.classify(
        track_id=args.track_id,
        sample_count=args.sample_count,
        observed_speed_mps=args.speed,
        observed_altitude_m=args.altitude,
    )
    _emit(
        {
            "track_id": result.track_id,
            "consensus_class": result.consensus_class,
            "calibrated_confidence": round(result.calibrated_confidence, 4),
            "certified_radius_l2": round(result.certified_radius_l2, 4),
            "votes": [
                {
                    "model_id": vote.model_id,
                    "predicted": vote.predicted_class,
                    "weight": round(vote.weight, 4),
                }
                for vote in result.votes
            ],
        }
    )
    return 0


def cmd_generate_coa(args: argparse.Namespace) -> int:
    service = CourseOfActionService()
    bundle = service.generate(classified_track_ids=args.tracks, roe_envelope_id=args.envelope)
    _emit(
        {
            "recommended_id": bundle.recommended_id,
            "coa": [
                {
                    "id": item.id,
                    "headline": item.headline,
                    "description": item.description,
                    "expected_leakage": asdict(item.expected_leakage),
                    "cost": asdict(item.cost),
                    "escalation": item.escalation_level,
                    "releasability": item.releasability,
                    "countdown_seconds": item.countdown_seconds,
                }
                for item in bundle.items
            ],
        }
    )
    return 0


def cmd_playbook(args: argparse.Namespace) -> int:
    _ = args
    service = AdversaryModelService()
    distribution = service.current()
    _emit(
        {
            "timestamp_s": distribution.timestamp_s,
            "cost_imposition_index": round(distribution.cost_imposition_index, 4),
            "hypotheses": [
                {
                    "playbook_id": h.playbook_id,
                    "display_name": h.display_name,
                    "weight": round(h.weight, 4),
                    "delta_30s": round(h.delta_30s, 4),
                }
                for h in distribution.hypotheses
            ],
        }
    )
    return 0


def cmd_trajectory(args: argparse.Namespace) -> int:
    initial = ThreatState(
        position_m=np.array([0.0, float(args.apogee), 0.0]),
        velocity_mps=np.array([float(args.speed), -50.0, 0.0]),
        mass_kg=float(args.mass),
        drag_area_m2=float(args.drag_area),
        drag_coefficient=float(args.drag_coefficient),
    )
    samples = trajectory(initial, duration_s=float(args.duration), dt_s=float(args.dt))

    summary = {
        "sample_count": len(samples),
        "duration_s": args.duration,
        "dt_s": args.dt,
        "initial_altitude_m": float(samples[0].position_m[1]),
        "final_altitude_m": float(samples[-1].position_m[1]),
        "max_altitude_m": float(max(s.position_m[1] for s in samples)),
        "ground_impact": float(samples[-1].position_m[1]) <= 0.0,
        "first_5_samples": [
            {
                "t": round(i * float(args.dt), 3),
                "x": round(float(samples[i].position_m[0]), 1),
                "y": round(float(samples[i].position_m[1]), 1),
                "vx": round(float(samples[i].velocity_mps[0]), 2),
                "vy": round(float(samples[i].velocity_mps[1]), 2),
            }
            for i in range(min(5, len(samples)))
        ],
    }
    _emit(summary)
    return 0


def cmd_demo(args: argparse.Namespace) -> int:
    """Run a complete simulated engagement end-to-end."""
    try:
        kind = scenarios.ScenarioKind(args.scenario)
    except ValueError:
        print(f"unknown scenario kind: {args.scenario}", file=sys.stderr)
        return 2

    scenario = scenarios.build(kind, seed=args.seed)
    track_ids = [f"TRK-{i:03d}" for i in range(args.tracks)]

    discrim_service = DiscriminationService()
    coa_service = CourseOfActionService()
    playbook_service = AdversaryModelService()

    classifications = [discrim_service.classify(track_id=tid, sample_count=1) for tid in track_ids]

    coa_bundle = coa_service.generate(
        classified_track_ids=track_ids,
        roe_envelope_id=args.envelope,
    )

    playbook = playbook_service.current()

    initial_state = ThreatState(
        position_m=np.array([0.0, 32_000.0, 0.0]),
        velocity_mps=np.array([2_400.0, -40.0, 0.0]),
    )
    samples = trajectory(initial_state, duration_s=60.0, dt_s=1.0)

    _emit(
        {
            "scenario": {
                "kind": scenario.kind.value,
                "seed": scenario.seed,
                "event_count": len(scenario.events),
                "first_event": {
                    "t": scenario.events[0].timestamp_s,
                    "type": scenario.events[0].event_type,
                },
            },
            "discrimination": {
                "track_count": len(classifications),
                "consensus": {
                    c.track_id: {
                        "class": c.consensus_class,
                        "confidence": round(c.calibrated_confidence, 3),
                    }
                    for c in classifications
                },
            },
            "course_of_action": {
                "recommended_id": coa_bundle.recommended_id,
                "options": [
                    {
                        "id": item.id,
                        "headline": item.headline,
                        "leakage": round(item.expected_leakage.point, 3),
                        "escalation": item.escalation_level,
                    }
                    for item in coa_bundle.items
                ],
            },
            "adversary": {
                "cost_imposition_index": round(playbook.cost_imposition_index, 3),
                "top_hypothesis": {
                    "playbook_id": playbook.hypotheses[0].playbook_id,
                    "weight": round(playbook.hypotheses[0].weight, 3),
                },
            },
            "kinematics": {
                "sample_count": len(samples),
                "initial_altitude_m": float(samples[0].position_m[1]),
                "final_altitude_m": float(samples[-1].position_m[1]),
                "ground_impact": float(samples[-1].position_m[1]) <= 0.0,
            },
        }
    )
    return 0


def cmd_audit_verify(args: argparse.Namespace) -> int:
    entries = AuditLogReader.load(args.path)
    result = AuditLogVerifier.verify(entries)
    _emit(
        {
            "path": args.path,
            "entry_count": len(entries),
            "valid": result.valid,
            "failed_at_sequence": result.failed_at_sequence,
            "failure_reason": result.failure_reason,
        }
    )
    return 0 if result.valid else 1


def cmd_audit_query(args: argparse.Namespace) -> int:
    entries = AuditLogReader.load(args.path)
    filtered = (
        entries
        if args.event_type is None
        else [e for e in entries if e.event_type == args.event_type]
    )
    _emit(
        {
            "path": args.path,
            "total_entries": len(entries),
            "filter": args.event_type,
            "matches": len(filtered),
            "entries": [
                {
                    "sequence": e.sequence,
                    "utc_iso": e.utc_iso,
                    "event_type": e.event_type,
                    "payload": json.loads(e.payload_json),
                }
                for e in filtered
            ],
        }
    )
    return 0


def cmd_audit_demo(args: argparse.Namespace) -> int:
    path = args.path
    with AuditLogWriter(path) as writer:
        writer.append("engagement_begin", {"scenario": "peer_salvo"})
        writer.append("mode_changed", {"previous": "Nominal", "current": "SensorDegraded"})
        writer.append("coa_proposed", {"id": "COA-B", "recommended": True})
        writer.append("coa_authorized", {"id": "COA-B", "source": "Operator"})
        writer.append("engagement_end", {})

    entries = AuditLogReader.load(path)
    result = AuditLogVerifier.verify(entries)
    _emit(
        {
            "wrote": str(path),
            "entries": len(entries),
            "verified": result.valid,
        }
    )
    return 0


def cmd_audit_html(args: argparse.Namespace) -> int:
    rendered = render_html_from_path(args.input)
    from pathlib import Path

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")
    _emit(
        {
            "input": str(args.input),
            "output": str(output_path),
            "bytes": len(rendered),
        }
    )
    return 0


def cmd_web(args: argparse.Namespace) -> int:
    try:
        import uvicorn
    except ImportError:
        print(
            "the web command requires the [web] extras: pip install -e '.[web]'",
            file=sys.stderr,
        )
        return 2

    uvicorn.run(
        "chaos_backend.web:app",
        host=args.host,
        port=args.port,
        reload=bool(args.reload),
        log_level="info",
    )
    return 0


def cmd_play(args: argparse.Namespace) -> int:
    from pathlib import Path

    try:
        kind = scenarios.ScenarioKind(args.scenario)
    except ValueError:
        print(f"unknown scenario kind: {args.scenario}", file=sys.stderr)
        return 2

    scenario = scenarios.build(kind, seed=args.seed)
    result = run_scenario(scenario, log_path=args.output, realtime=False)

    response: dict[str, object] = {
        "scenario": result.scenario_kind,
        "seed": result.seed,
        "events_emitted": result.events_emitted,
        "log_path": str(result.log_path),
    }

    if args.html:
        html_path = Path(args.html)
        html_path.parent.mkdir(parents=True, exist_ok=True)
        html_path.write_text(render_html_from_path(result.log_path), encoding="utf-8")
        response["html_path"] = str(html_path)

    _emit(response)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="chaos-backend-cli")
    sub = parser.add_subparsers(dest="command", required=True)

    audit = sub.add_parser("audit", help="audit log read/verify/demo utilities")
    audit_sub = audit.add_subparsers(dest="audit_command", required=True)

    audit_verify = audit_sub.add_parser("verify", help="verify a JSONL audit log's hash chain")
    audit_verify.add_argument("path")
    audit_verify.set_defaults(func=cmd_audit_verify)

    audit_query = audit_sub.add_parser("query", help="filter an audit log by event type")
    audit_query.add_argument("path")
    audit_query.add_argument("--event-type", default=None)
    audit_query.set_defaults(func=cmd_audit_query)

    audit_demo = audit_sub.add_parser(
        "demo",
        help="write a small sample audit log and verify it",
    )
    audit_demo.add_argument("path")
    audit_demo.set_defaults(func=cmd_audit_demo)

    audit_html = audit_sub.add_parser(
        "html",
        help="render an audit log to a self-contained HTML page",
    )
    audit_html.add_argument("input")
    audit_html.add_argument("output")
    audit_html.set_defaults(func=cmd_audit_html)

    play = sub.add_parser(
        "play",
        help="play a scenario into an audit log; optionally render HTML",
    )
    play.add_argument(
        "scenario",
        choices=[k.value for k in scenarios.ScenarioKind],
    )
    play.add_argument("--seed", type=int, default=42)
    play.add_argument("--output", required=True, help="path to the JSONL audit log to write")
    play.add_argument("--html", default=None, help="optional HTML output path")
    play.set_defaults(func=cmd_play)

    web = sub.add_parser(
        "web",
        help="serve the FastAPI dashboard (requires [web] or [dev] extras)",
    )
    web.add_argument("--host", default="127.0.0.1")
    web.add_argument("--port", type=int, default=8000)
    web.add_argument("--reload", action="store_true", help="auto-reload on file change")
    web.set_defaults(func=cmd_web)

    d = sub.add_parser(
        "demo",
        help="run a complete simulated engagement end-to-end",
    )
    d.add_argument(
        "--scenario",
        choices=[k.value for k in scenarios.ScenarioKind],
        default="peer_salvo",
    )
    d.add_argument("--seed", type=int, default=42)
    d.add_argument("--tracks", type=int, default=4)
    d.add_argument("--envelope", default="ROE-2")
    d.set_defaults(func=cmd_demo)

    s = sub.add_parser("scenario", help="emit a scenario event sequence")
    s.add_argument("kind", choices=[k.value for k in scenarios.ScenarioKind])
    s.add_argument("--seed", type=int, default=0)
    s.set_defaults(func=cmd_scenario)

    c = sub.add_parser("classify", help="run the mock discriminator on a single track")
    c.add_argument("--track-id", required=True)
    c.add_argument("--sample-count", type=int, default=1)
    c.add_argument("--speed", type=float, default=None, help="observed speed m/s")
    c.add_argument("--altitude", type=float, default=None, help="observed altitude m")
    c.set_defaults(func=cmd_classify)

    g = sub.add_parser("generate-coa", help="generate a COA bundle for a set of track ids")
    g.add_argument("--tracks", nargs="+", required=True)
    g.add_argument("--envelope", default="ROE-2")
    g.set_defaults(func=cmd_generate_coa)

    p = sub.add_parser("playbook", help="emit the current adversary playbook distribution")
    p.set_defaults(func=cmd_playbook)

    t = sub.add_parser("trajectory", help="run the RK4 integrator and summarize")
    t.add_argument("--apogee", type=float, default=35_000.0, help="initial altitude m")
    t.add_argument("--speed", type=float, default=2_500.0, help="initial horizontal speed m/s")
    t.add_argument("--mass", type=float, default=1_500.0)
    t.add_argument("--drag-area", type=float, default=0.2)
    t.add_argument("--drag-coefficient", type=float, default=0.3)
    t.add_argument("--duration", type=float, default=120.0)
    t.add_argument("--dt", type=float, default=0.5)
    t.set_defaults(func=cmd_trajectory)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    func = getattr(args, "func", None)
    if func is None:
        parser.print_help(sys.stderr)
        return 2
    return int(func(args))


if __name__ == "__main__":
    raise SystemExit(main())
