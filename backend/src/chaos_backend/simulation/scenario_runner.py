"""Run a scenario into an audit log.

Bridges the scenario builders to the audit writer: each ScenarioEvent
becomes one audit entry, in scenario-time order. The resulting JSONL is
a hash-chained record of the engagement that can be verified, queried,
and rendered to HTML through the rest of the audit pipeline.

By default the runner is unmetered — it walks the event list and writes
each entry back-to-back. Use `realtime=True` to sleep between events so
the wall-clock matches scenario time (useful for live demos; never use
in tests).
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from chaos_backend.audit.log import AuditLogWriter
from chaos_backend.simulation.scenarios import Scenario


@dataclass(slots=True)
class RunResult:
    scenario_kind: str
    seed: int
    events_emitted: int
    log_path: Path


def run(
    scenario: Scenario,
    *,
    log_path: str | Path,
    realtime: bool = False,
    speed: float = 1.0,
) -> RunResult:
    """Walk scenario events into an audit log at `log_path`.

    Parameters
    ----------
    scenario:
        The Scenario to play. Events are emitted in the order returned
        by the builder; the runner does not reorder by timestamp.
    log_path:
        Where to write the JSONL log. Parent directory is created.
    realtime:
        When True, sleep between events so wall-clock advances at
        `speed` x scenario rate. False (default) makes the runner
        unmetered, suitable for batch use and tests.
    speed:
        Real-time multiplier. Only consulted when realtime=True.
        speed > 1 plays faster than scenario time; speed < 1 slower.
    """

    target = Path(log_path)
    target.parent.mkdir(parents=True, exist_ok=True)

    previous_event_time = 0.0
    emitted = 0

    with AuditLogWriter(target) as writer:
        writer.append(
            "scenario_run_begin",
            {
                "kind": scenario.kind.value,
                "seed": scenario.seed,
                "duration_s": scenario.duration_s,
            },
        )

        for event in scenario.events:
            if realtime and speed > 0:
                gap = max(0.0, event.timestamp_s - previous_event_time)
                if gap > 0:
                    time.sleep(gap / speed)

            writer.append(
                event.event_type,
                {
                    "scenario_t": event.timestamp_s,
                    **event.payload,
                },
            )
            previous_event_time = event.timestamp_s
            emitted += 1

        writer.append(
            "scenario_run_end",
            {"kind": scenario.kind.value, "events_emitted": emitted},
        )

    return RunResult(
        scenario_kind=scenario.kind.value,
        seed=scenario.seed,
        events_emitted=emitted,
        log_path=target,
    )
