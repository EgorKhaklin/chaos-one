"""Tests for the kinematic feature extractor."""

from __future__ import annotations

import numpy as np

from chaos_backend.services.features import extract


def test_altitude_bands_cover_each_regime() -> None:
    assert extract(altitude_m=500, speed_mps=0).altitude_band == 0
    assert extract(altitude_m=5_000, speed_mps=0).altitude_band == 1
    assert extract(altitude_m=20_000, speed_mps=0).altitude_band == 2
    assert extract(altitude_m=70_000, speed_mps=0).altitude_band == 3
    assert extract(altitude_m=150_000, speed_mps=0).altitude_band == 4


def test_speed_bands_cover_each_regime() -> None:
    assert extract(altitude_m=0, speed_mps=100).speed_band == 0  # subsonic
    assert extract(altitude_m=0, speed_mps=350).speed_band == 1  # transonic
    assert extract(altitude_m=0, speed_mps=600).speed_band == 2  # supersonic
    assert extract(altitude_m=0, speed_mps=2_500).speed_band == 3  # hypersonic


def test_atmospheric_density_falls_off_with_altitude() -> None:
    sea_level = extract(altitude_m=0, speed_mps=0)
    upper = extract(altitude_m=40_000, speed_mps=0)
    exo = extract(altitude_m=120_000, speed_mps=0)

    assert sea_level.atmospheric_density > upper.atmospheric_density
    assert upper.atmospheric_density > exo.atmospheric_density
    assert exo.atmospheric_density < 0.01


def test_atmospheric_density_clamps_at_or_below_sea_level() -> None:
    underground = extract(altitude_m=-100, speed_mps=0)
    sea_level = extract(altitude_m=0, speed_mps=0)
    assert underground.atmospheric_density == sea_level.atmospheric_density


def test_ballistic_indicator_for_vertical_velocity() -> None:
    feats = extract(
        altitude_m=10_000,
        speed_mps=500,
        velocity_mps=np.array([0.0, -500.0, 0.0]),
    )
    assert feats.ballistic_indicator == 1.0


def test_ballistic_indicator_for_horizontal_velocity() -> None:
    feats = extract(
        altitude_m=10_000,
        speed_mps=500,
        velocity_mps=np.array([500.0, 0.0, 0.0]),
    )
    assert feats.ballistic_indicator == 0.0


def test_ballistic_indicator_is_zero_when_velocity_unknown() -> None:
    feats = extract(altitude_m=10_000, speed_mps=500)
    assert feats.ballistic_indicator == 0.0


def test_ballistic_indicator_is_zero_for_stationary_track() -> None:
    feats = extract(
        altitude_m=0,
        speed_mps=0,
        velocity_mps=np.array([0.0, 0.0, 0.0]),
    )
    assert feats.ballistic_indicator == 0.0


def test_altitude_normalized_clamps_to_unit_interval() -> None:
    above = extract(altitude_m=500_000, speed_mps=0).altitude_normalized
    below = extract(altitude_m=-100, speed_mps=0).altitude_normalized
    assert above == 1.0
    assert below == 0.0


def test_extract_handles_missing_values() -> None:
    feats = extract(altitude_m=None, speed_mps=None)
    assert feats.altitude_m == 0.0
    assert feats.speed_mps == 0.0
    assert feats.altitude_band == 0
    assert feats.speed_band == 0
