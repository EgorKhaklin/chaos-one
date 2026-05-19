"""Micro-benchmarks for the backend hot paths.

Not unit tests. Run with `make bench` to get a single structured report
of throughput numbers for each service plus the kinematics integrator.
Numbers vary by host; the point is to have a reproducible measurement
attached to the repo so any future change can be compared against a
known baseline.

Usage:
    python -m benchmarks.run_all
    python -m benchmarks.run_all --iterations 5000
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from chaos_backend.services.adversary_model import AdversaryModelService
from chaos_backend.services.coa_generator import CourseOfActionService
from chaos_backend.services.discrimination import DiscriminationService
from chaos_backend.simulation.kinematics import ThreatState, step_rk4, trajectory
from chaos_backend.simulation.scenarios import ScenarioKind, build


@dataclass(slots=True)
class BenchResult:
    name: str
    iterations: int
    elapsed_s: float
    per_op_us: float
    ops_per_s: float
    notes: str = ""


def _bench(name: str, iterations: int, body: Callable[[], None], notes: str = "") -> BenchResult:
    # Warm up: one untimed iteration.
    body()

    start = time.perf_counter()
    for _ in range(iterations):
        body()
    elapsed = time.perf_counter() - start

    per_op = elapsed / iterations
    return BenchResult(
        name=name,
        iterations=iterations,
        elapsed_s=elapsed,
        per_op_us=per_op * 1_000_000.0,
        ops_per_s=1.0 / per_op if per_op > 0 else float("inf"),
        notes=notes,
    )


def bench_kinematics_step(iterations: int) -> BenchResult:
    state = ThreatState(
        position_m=np.array([0.0, 30_000.0, 0.0]),
        velocity_mps=np.array([2_400.0, -40.0, 0.0]),
    )

    def body() -> None:
        step_rk4(state, dt_seconds=0.1)

    return _bench("kinematics.step_rk4", iterations, body, notes="single RK4 step")


def bench_kinematics_trajectory(iterations: int) -> BenchResult:
    initial = ThreatState(
        position_m=np.array([0.0, 30_000.0, 0.0]),
        velocity_mps=np.array([2_400.0, -40.0, 0.0]),
    )

    def body() -> None:
        trajectory(initial, duration_s=10.0, dt_s=0.1)

    return _bench(
        "kinematics.trajectory_100steps",
        iterations,
        body,
        notes="10s @ dt=0.1s = 100 RK4 steps",
    )


def bench_discrimination_classify(iterations: int) -> BenchResult:
    service = DiscriminationService()

    def body() -> None:
        service.classify(track_id="TRK-BENCH-001", sample_count=1)

    return _bench("discrimination.classify", iterations, body)


def bench_coa_generate(iterations: int) -> BenchResult:
    service = CourseOfActionService()
    tracks = [f"TRK-{i:03d}" for i in range(8)]

    def body() -> None:
        service.generate(classified_track_ids=tracks, roe_envelope_id="ROE-2")

    return _bench("course_of_action.generate", iterations, body, notes="8 tracks, ROE-2")


def bench_adversary_current(iterations: int) -> BenchResult:
    service = AdversaryModelService()

    def body() -> None:
        service.current()

    return _bench("adversary_model.current", iterations, body)


def bench_scenario_build(iterations: int) -> BenchResult:
    def body() -> None:
        build(ScenarioKind.PEER_SALVO, seed=42)

    return _bench("scenarios.build_peer_salvo", iterations, body, notes="seed=42")


_BENCHMARKS: list[tuple[str, Callable[[int], BenchResult]]] = [
    ("kinematics_step", bench_kinematics_step),
    ("kinematics_trajectory", bench_kinematics_trajectory),
    ("discrimination_classify", bench_discrimination_classify),
    ("coa_generate", bench_coa_generate),
    ("adversary_current", bench_adversary_current),
    ("scenario_build", bench_scenario_build),
]


def _format_row(result: BenchResult) -> str:
    return (
        f"  {result.name:32s}"
        f"  {result.iterations:>7d}"
        f"  {result.elapsed_s:>8.3f}s"
        f"  {result.per_op_us:>10.2f}us/op"
        f"  {result.ops_per_s:>12,.0f}/s"
        f"  {result.notes}"
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="bench")
    parser.add_argument(
        "--iterations",
        type=int,
        default=1000,
        help="iterations per benchmark (default 1000)",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=3,
        help="how many times to run each bench (best result kept)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit JSON instead of the formatted table",
    )
    args = parser.parse_args(argv)

    results: list[BenchResult] = []
    for _, runner in _BENCHMARKS:
        repeated = [runner(args.iterations) for _ in range(args.repeats)]
        best = min(repeated, key=lambda r: r.per_op_us)
        results.append(best)

    if args.json:
        json.dump(
            [
                {
                    "name": r.name,
                    "iterations": r.iterations,
                    "elapsed_s": round(r.elapsed_s, 6),
                    "per_op_us": round(r.per_op_us, 3),
                    "ops_per_s": round(r.ops_per_s, 1),
                    "notes": r.notes,
                }
                for r in results
            ],
            sys.stdout,
            indent=2,
        )
        sys.stdout.write("\n")
    else:
        print("chaos-backend benchmarks")
        print(f"  iterations per bench: {args.iterations}, repeats: {args.repeats} (best kept)")
        print(
            f"  {'name':32s}  {'iters':>7s}  {'elapsed':>8s}  {'per op':>12s}  {'ops/s':>12s}  notes"
        )
        print(f"  {'-' * 32}  {'-' * 7}  {'-' * 9}  {'-' * 12}  {'-' * 12}  {'-' * 5}")
        for result in results:
            print(_format_row(result))

        total_ops = sum(r.iterations for r in results)
        total_elapsed = sum(r.elapsed_s for r in results)
        print()
        print(
            f"  total: {total_ops:,} operations across {len(results)} benches "
            f"in {total_elapsed:.3f}s (best repeats kept)"
        )
        ops_per_s = [r.ops_per_s for r in results]
        print(f"  geomean ops/s: {statistics.geometric_mean(ops_per_s):,.0f}" if ops_per_s else "")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
