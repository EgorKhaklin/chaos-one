"""Scenario generator.

Three canonical scenarios drive the front-end demos. Each scenario is
parameterized and reproducible from a numeric seed; replay determinism
is load-bearing for the audit reel.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

import numpy as np


class ScenarioKind(StrEnum):
    PEER_SALVO = "peer_salvo"
    REGIONAL_CRISIS = "regional_crisis"
    AMBIGUOUS_LAUNCH = "ambiguous_launch"


@dataclass(slots=True)
class ScenarioEvent:
    timestamp_s: float
    event_type: str
    payload: dict[str, object] = field(default_factory=dict)


@dataclass(slots=True)
class Scenario:
    kind: ScenarioKind
    seed: int
    duration_s: float
    events: list[ScenarioEvent]


def build_peer_salvo(seed: int) -> Scenario:
    rng = np.random.default_rng(seed)
    events: list[ScenarioEvent] = []

    events.append(ScenarioEvent(0.0, "scenario_start", {"kind": ScenarioKind.PEER_SALVO}))

    base_launch_time = 10.0
    for index in range(4):
        jitter = float(rng.uniform(-0.3, 0.3))
        events.append(
            ScenarioEvent(
                timestamp_s=base_launch_time + index * 0.5 + jitter,
                event_type="plume_detected",
                payload={
                    "site_cluster": "HOTEL",
                    "missile_index": index,
                    "presumed_class": "HGV",
                },
            )
        )

    events.append(
        ScenarioEvent(
            timestamp_s=base_launch_time + 5.0,
            event_type="adversary_model_update",
            payload={"playbook_id": "charlie-7", "weight_delta": 0.28},
        )
    )

    events.append(
        ScenarioEvent(
            timestamp_s=base_launch_time + 8.0,
            event_type="sensor_spoof_detected",
            payload={"sensor_id": "LRDR-CLEAR", "domain": "surface"},
        )
    )

    events.append(
        ScenarioEvent(
            timestamp_s=base_launch_time + 9.0,
            event_type="mode_transition",
            payload={"from": "nominal", "to": "sensor_degraded"},
        )
    )

    events.append(
        ScenarioEvent(
            timestamp_s=base_launch_time + 12.0,
            event_type="discrimination_resolved",
            payload={
                "confident_threats": 4,
                "candidate_decoys": 8,
                "ensemble_uncertain": 60,
            },
        )
    )

    events.append(
        ScenarioEvent(
            timestamp_s=base_launch_time + 14.0,
            event_type="coa_generated",
            payload={"recommended_id": "COA-B"},
        )
    )

    events.append(ScenarioEvent(180.0, "scenario_end"))
    return Scenario(kind=ScenarioKind.PEER_SALVO, seed=seed, duration_s=180.0, events=events)


def build_regional_crisis(seed: int) -> Scenario:
    rng = np.random.default_rng(seed)
    _ = rng  # reserved for stochastic event placement in M3
    events = [
        ScenarioEvent(0.0, "scenario_start", {"kind": ScenarioKind.REGIONAL_CRISIS}),
        ScenarioEvent(8.0, "ew_jamming_detected", {"sensor_id": "COASTAL-SPY"}),
        ScenarioEvent(12.0, "mass_launch_over_horizon", {"cm_count": 8, "uas_count": 150}),
        ScenarioEvent(20.0, "discrimination_resolved", {"cm": 8, "uas_candidates": 150}),
        ScenarioEvent(180.0, "scenario_end"),
    ]
    return Scenario(
        kind=ScenarioKind.REGIONAL_CRISIS, seed=seed, duration_s=180.0, events=events
    )


def build_ambiguous_launch(seed: int) -> Scenario:
    _ = seed
    events = [
        ScenarioEvent(0.0, "scenario_start", {"kind": ScenarioKind.AMBIGUOUS_LAUNCH}),
        ScenarioEvent(5.0, "single_plume_detected", {"site_id": "INDIGO"}),
        ScenarioEvent(
            18.0,
            "trajectory_class_resolved",
            {"class": "depressed", "payload_class": "uncertain"},
        ),
        ScenarioEvent(
            25.0,
            "system_declines_recommendation",
            {
                "reason": (
                    "Adversary playbook hypotheses within 8 pts; ensemble"
                    " disagrees on payload class."
                )
            },
        ),
        ScenarioEvent(480.0, "scenario_end"),
    ]
    return Scenario(
        kind=ScenarioKind.AMBIGUOUS_LAUNCH, seed=seed, duration_s=480.0, events=events
    )


_BUILDERS = {
    ScenarioKind.PEER_SALVO: build_peer_salvo,
    ScenarioKind.REGIONAL_CRISIS: build_regional_crisis,
    ScenarioKind.AMBIGUOUS_LAUNCH: build_ambiguous_launch,
}


def build(kind: ScenarioKind, seed: int = 0) -> Scenario:
    return _BUILDERS[kind](seed)
