"""Smoke tests verifying the backend skeleton imports cleanly and the
mock services produce well-formed outputs."""

from __future__ import annotations

import numpy as np

from chaos_backend.services.adversary_model import AdversaryModelService
from chaos_backend.services.coa_generator import CourseOfActionService
from chaos_backend.services.discrimination import DiscriminationService
from chaos_backend.simulation.kinematics import ThreatState, trajectory
from chaos_backend.simulation.scenarios import ScenarioKind, build


def test_discrimination_returns_calibrated_votes() -> None:
    service = DiscriminationService()
    result = service.classify(track_id="TRK-001", sample_count=1)

    assert result.track_id == "TRK-001"
    assert len(result.votes) == 4
    assert 0.0 <= result.calibrated_confidence <= 1.0
    assert 0.0 <= result.certified_radius_l2 <= 1.0


def test_coa_service_returns_three_options_with_recommendation() -> None:
    service = CourseOfActionService()
    bundle = service.generate(classified_track_ids=["A", "B", "C", "D"], roe_envelope_id="ROE-2")

    assert len(bundle.items) == 3
    assert bundle.recommended_id == "COA-B"
    assert any(item.id == bundle.recommended_id for item in bundle.items)


def test_adversary_model_weights_sum_to_one_within_tolerance() -> None:
    service = AdversaryModelService()
    distribution = service.current()
    total = sum(h.weight for h in distribution.hypotheses)
    assert abs(total - 1.0) < 0.02


def test_kinematics_integrator_runs_a_depressed_trajectory() -> None:
    initial = ThreatState(
        position_m=np.array([0.0, 35_000.0, 0.0]),
        velocity_mps=np.array([2_500.0, -50.0, 0.0]),
        mass_kg=1_500.0,
    )
    samples = trajectory(initial, duration_s=60.0, dt_s=0.5)

    assert len(samples) > 100
    assert samples[-1].position_m[1] < samples[0].position_m[1]


def test_scenarios_are_deterministic_under_same_seed() -> None:
    scenario_a = build(ScenarioKind.PEER_SALVO, seed=42)
    scenario_b = build(ScenarioKind.PEER_SALVO, seed=42)

    assert len(scenario_a.events) == len(scenario_b.events)
    for left, right in zip(scenario_a.events, scenario_b.events, strict=True):
        assert left.event_type == right.event_type
        assert abs(left.timestamp_s - right.timestamp_s) < 1e-9
