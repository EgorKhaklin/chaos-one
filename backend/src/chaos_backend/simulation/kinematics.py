"""Threat kinematics.

A bare RK4 integrator over a 6-DoF translational state vector
(position, velocity). Drag and gravity modeled at a level sufficient
for visually-credible trajectories but not for live targeting.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

_EARTH_RADIUS_M = 6_371_000.0
_GRAVITY_AT_SEA_LEVEL = 9.80665
_AIR_DENSITY_SEA_LEVEL = 1.225  # kg/m^3
_SCALE_HEIGHT_M = 8_500.0


@dataclass(slots=True)
class ThreatState:
    position_m: np.ndarray
    velocity_mps: np.ndarray
    mass_kg: float = 1_500.0
    drag_area_m2: float = 0.2
    drag_coefficient: float = 0.3

    def copy(self) -> "ThreatState":
        return ThreatState(
            position_m=self.position_m.copy(),
            velocity_mps=self.velocity_mps.copy(),
            mass_kg=self.mass_kg,
            drag_area_m2=self.drag_area_m2,
            drag_coefficient=self.drag_coefficient,
        )


def _air_density(altitude_m: float) -> float:
    if altitude_m < 0.0:
        return _AIR_DENSITY_SEA_LEVEL
    return _AIR_DENSITY_SEA_LEVEL * float(np.exp(-altitude_m / _SCALE_HEIGHT_M))


def _gravity(altitude_m: float) -> float:
    r = _EARTH_RADIUS_M + max(0.0, altitude_m)
    return _GRAVITY_AT_SEA_LEVEL * (_EARTH_RADIUS_M / r) ** 2


def _acceleration(state: ThreatState) -> np.ndarray:
    altitude = float(state.position_m[1])
    rho = _air_density(altitude)
    speed = float(np.linalg.norm(state.velocity_mps))

    if speed > 1e-3:
        unit_velocity = state.velocity_mps / speed
        drag_magnitude = 0.5 * rho * speed * speed * state.drag_coefficient * state.drag_area_m2
        drag_accel = -unit_velocity * (drag_magnitude / state.mass_kg)
    else:
        drag_accel = np.zeros(3)

    gravity_accel = np.array([0.0, -_gravity(altitude), 0.0])
    return drag_accel + gravity_accel


def step_rk4(state: ThreatState, dt_seconds: float) -> ThreatState:
    """Advance state by one RK4 step. Returns a new state; input untouched."""

    def derivative(s: ThreatState) -> tuple[np.ndarray, np.ndarray]:
        return s.velocity_mps.copy(), _acceleration(s)

    def with_offset(s: ThreatState, dp: np.ndarray, dv: np.ndarray) -> ThreatState:
        return ThreatState(
            position_m=s.position_m + dp,
            velocity_mps=s.velocity_mps + dv,
            mass_kg=s.mass_kg,
            drag_area_m2=s.drag_area_m2,
            drag_coefficient=s.drag_coefficient,
        )

    k1_p, k1_v = derivative(state)
    k2_p, k2_v = derivative(with_offset(state, k1_p * dt_seconds / 2, k1_v * dt_seconds / 2))
    k3_p, k3_v = derivative(with_offset(state, k2_p * dt_seconds / 2, k2_v * dt_seconds / 2))
    k4_p, k4_v = derivative(with_offset(state, k3_p * dt_seconds, k3_v * dt_seconds))

    new_position = state.position_m + (dt_seconds / 6.0) * (k1_p + 2 * k2_p + 2 * k3_p + k4_p)
    new_velocity = state.velocity_mps + (dt_seconds / 6.0) * (k1_v + 2 * k2_v + 2 * k3_v + k4_v)

    return ThreatState(
        position_m=new_position,
        velocity_mps=new_velocity,
        mass_kg=state.mass_kg,
        drag_area_m2=state.drag_area_m2,
        drag_coefficient=state.drag_coefficient,
    )


def trajectory(
    initial: ThreatState,
    duration_s: float,
    dt_s: float = 0.1,
) -> list[ThreatState]:
    """Run the integrator forward and return the sampled state history."""
    if dt_s <= 0:
        raise ValueError("dt_s must be positive")

    samples: list[ThreatState] = [initial.copy()]
    current = initial.copy()
    elapsed = 0.0

    while elapsed < duration_s:
        step_dt = min(dt_s, duration_s - elapsed)
        current = step_rk4(current, step_dt)
        samples.append(current)
        elapsed += step_dt

        if current.position_m[1] < 0.0:
            break

    return samples
