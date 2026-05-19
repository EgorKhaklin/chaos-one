"""Kinematic feature extraction for the discrimination ensemble.

Hand-engineered features that map raw track observations into the
quantities each model in the ensemble votes on. Real ML lands in
milestone 4+; until then these features are the substrate that gives
the rule-based ensemble its plausible behavior.

All features are dimensionless or in SI; nothing here is unit-magical.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Approximate speed of sound at sea level (m/s).
_SPEED_OF_SOUND_SL = 343.0

# Atmospheric scale height (m). Density falls by 1/e per scale height.
_SCALE_HEIGHT_M = 8_500.0
_RHO_SL = 1.225  # kg/m^3 at sea level


@dataclass(frozen=True, slots=True)
class TrackFeatures:
    altitude_m: float
    speed_mps: float
    altitude_band: int  # 0..4: ground/low/mid/upper/exo
    speed_band: int  # 0..3: sub/transonic/supersonic/hypersonic
    specific_kinetic_energy: float  # m^2/s^2 (per unit mass: 0.5 v^2)
    atmospheric_density: float  # kg/m^3 at altitude
    ballistic_indicator: float  # 0..1, ~1 when the velocity is mostly vertical
    altitude_normalized: float  # 0..1 over the [0, 100 km] band


def _altitude_band(altitude_m: float) -> int:
    if altitude_m < 1_000:
        return 0
    if altitude_m < 12_000:
        return 1
    if altitude_m < 40_000:
        return 2
    if altitude_m < 100_000:
        return 3
    return 4


def _speed_band(speed_mps: float) -> int:
    mach = speed_mps / _SPEED_OF_SOUND_SL
    if mach < 0.8:
        return 0
    if mach < 1.2:
        return 1
    if mach < 5.0:
        return 2
    return 3


def _atmospheric_density(altitude_m: float) -> float:
    if altitude_m < 0:
        return _RHO_SL
    return _RHO_SL * float(np.exp(-altitude_m / _SCALE_HEIGHT_M))


def _ballistic_indicator(velocity_mps: np.ndarray | None) -> float:
    """Fraction of the velocity vector aligned with the vertical axis.

    Returns 0.0 when velocity is unknown or zero. A pure ballistic
    coast looks close to 1.0; a horizontal cruise is near 0.0.
    """
    if velocity_mps is None:
        return 0.0
    speed = float(np.linalg.norm(velocity_mps))
    if speed < 1e-3:
        return 0.0
    return abs(float(velocity_mps[1])) / speed


def extract(
    *,
    altitude_m: float | None,
    speed_mps: float | None,
    velocity_mps: np.ndarray | None = None,
) -> TrackFeatures:
    """Build a TrackFeatures from whatever observations are available.

    Missing fields default to physically-neutral values (sea-level
    altitude, zero speed) so downstream models can vote consistently.
    """
    alt = float(altitude_m) if altitude_m is not None else 0.0
    speed = float(speed_mps) if speed_mps is not None else 0.0

    return TrackFeatures(
        altitude_m=alt,
        speed_mps=speed,
        altitude_band=_altitude_band(alt),
        speed_band=_speed_band(speed),
        specific_kinetic_energy=0.5 * speed * speed,
        atmospheric_density=_atmospheric_density(alt),
        ballistic_indicator=_ballistic_indicator(velocity_mps),
        altitude_normalized=min(1.0, max(0.0, alt / 100_000.0)),
    )
