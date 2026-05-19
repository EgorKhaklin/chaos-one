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

from chaos_backend.services.adversary_model import AdversaryModelService
from chaos_backend.services.coa_generator import CourseOfActionService
from chaos_backend.services.discrimination import DiscriminationService
from chaos_backend.simulation import scenarios
from chaos_backend.simulation.kinematics import ThreatState, trajectory


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


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="chaos-backend-cli")
    sub = parser.add_subparsers(dest="command", required=True)

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
