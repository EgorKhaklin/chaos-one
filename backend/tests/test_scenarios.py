"""Coverage for the regional-crisis and ambiguous-launch scenario builders
plus the dispatch table in `scenarios.build`."""

from __future__ import annotations

import pytest

from chaos_backend.simulation.scenarios import ScenarioKind, build


def test_regional_crisis_builds_a_finite_scenario() -> None:
    scenario = build(ScenarioKind.REGIONAL_CRISIS, seed=11)
    assert scenario.kind == ScenarioKind.REGIONAL_CRISIS
    assert scenario.seed == 11
    assert scenario.duration_s > 0
    assert any(event.event_type == "mass_launch_over_horizon" for event in scenario.events)
    assert scenario.events[-1].event_type == "scenario_end"


def test_ambiguous_launch_has_decline_recommendation_event() -> None:
    scenario = build(ScenarioKind.AMBIGUOUS_LAUNCH, seed=0)
    decline = [
        event for event in scenario.events if event.event_type == "system_declines_recommendation"
    ]
    assert len(decline) == 1
    assert "playbook hypotheses" in decline[0].payload["reason"].lower()


def test_build_dispatch_routes_by_kind() -> None:
    salvo = build(ScenarioKind.PEER_SALVO, seed=3)
    crisis = build(ScenarioKind.REGIONAL_CRISIS, seed=3)
    ambig = build(ScenarioKind.AMBIGUOUS_LAUNCH, seed=3)

    assert salvo.kind == ScenarioKind.PEER_SALVO
    assert crisis.kind == ScenarioKind.REGIONAL_CRISIS
    assert ambig.kind == ScenarioKind.AMBIGUOUS_LAUNCH


def test_scenario_kind_string_values_are_stable() -> None:
    # CLI surfaces these as choice arguments; changing them is a breaking
    # change for any tooling that pipes scenarios by name.
    assert ScenarioKind.PEER_SALVO.value == "peer_salvo"
    assert ScenarioKind.REGIONAL_CRISIS.value == "regional_crisis"
    assert ScenarioKind.AMBIGUOUS_LAUNCH.value == "ambiguous_launch"


def test_unknown_kind_raises_value_error() -> None:
    with pytest.raises(ValueError):
        ScenarioKind("unknown")
