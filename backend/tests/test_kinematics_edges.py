"""Edge-case coverage for the kinematics integrator."""

from __future__ import annotations

import numpy as np
import pytest

from chaos_backend.simulation.kinematics import (
    ThreatState,
    _air_density,
    step_rk4,
    trajectory,
)


def test_air_density_below_zero_clamps_to_sea_level() -> None:
    # Underground or negative altitudes shouldn't extrapolate into
    # unphysical regimes; the integrator clamps to sea-level density.
    rho = _air_density(-100.0)
    assert rho == pytest.approx(1.225, rel=1e-6)


def test_step_rk4_handles_zero_velocity() -> None:
    state = ThreatState(
        position_m=np.array([0.0, 10_000.0, 0.0]),
        velocity_mps=np.array([0.0, 0.0, 0.0]),
    )
    advanced = step_rk4(state, dt_seconds=0.1)
    # A stationary object accelerates only by gravity; no drag.
    assert advanced.velocity_mps[1] < state.velocity_mps[1]


def test_trajectory_requires_positive_dt() -> None:
    initial = ThreatState(
        position_m=np.array([0.0, 1_000.0, 0.0]),
        velocity_mps=np.array([100.0, 0.0, 0.0]),
    )
    with pytest.raises(ValueError):
        trajectory(initial, duration_s=10.0, dt_s=0.0)


def test_trajectory_breaks_on_ground_impact() -> None:
    # Launch with a small downward velocity at very low altitude. The
    # loop must short-circuit when y crosses zero rather than emit an
    # endless sequence of underground samples.
    initial = ThreatState(
        position_m=np.array([0.0, 50.0, 0.0]),
        velocity_mps=np.array([10.0, -20.0, 0.0]),
    )
    samples = trajectory(initial, duration_s=120.0, dt_s=0.1)
    # If the impact early-exit didn't fire, we'd see ~1200 samples here.
    assert len(samples) < 200
    assert samples[-1].position_m[1] < 0.0
