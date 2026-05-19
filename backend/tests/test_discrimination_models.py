"""Tests for the feature-driven discrimination ensemble.

Each test pins one model's response under a specific input regime so
the ensemble's behavior across the kinematic feature space stays
predictable. Numbers chosen to land squarely inside their bands rather
than on the edges where small changes flip the classification.
"""

from __future__ import annotations

from chaos_backend.services.discrimination import DiscriminationService


def _classify(altitude_m: float, speed_mps: float, track_id: str = "TRK-X") -> str:
    service = DiscriminationService()
    result = service.classify(
        track_id=track_id,
        sample_count=1,
        observed_altitude_m=altitude_m,
        observed_speed_mps=speed_mps,
    )
    return result.consensus_class


def test_high_altitude_hypersonic_reads_as_hgv() -> None:
    assert _classify(altitude_m=60_000, speed_mps=2_500, track_id="TRK-HGV-1") == "HGV"


def test_low_slow_track_reads_as_uas() -> None:
    assert _classify(altitude_m=300, speed_mps=40, track_id="TRK-UAS-1") == "UAS"


def test_low_fast_track_reads_as_cruise_missile() -> None:
    # 600 m/s is well into the supersonic band; cruise missiles can sit
    # comfortably here. Picking 280 (the transonic-edge subsonic regime)
    # would land in the UAS bucket on most models in this ensemble.
    assert _classify(altitude_m=200, speed_mps=600, track_id="TRK-CM-1") == "CRUISE_MISSILE"


def test_midcourse_hypersonic_reads_as_hgv() -> None:
    assert _classify(altitude_m=25_000, speed_mps=2_200, track_id="TRK-HGV-2") == "HGV"


def test_classification_is_deterministic_for_same_inputs() -> None:
    a = _classify(altitude_m=60_000, speed_mps=2_500, track_id="TRK-DET")
    b = _classify(altitude_m=60_000, speed_mps=2_500, track_id="TRK-DET")
    assert a == b


def test_confidence_in_unit_interval_across_regimes() -> None:
    service = DiscriminationService()
    samples = [
        service.classify(
            track_id="A", sample_count=1, observed_altitude_m=300, observed_speed_mps=40
        ),
        service.classify(
            track_id="B", sample_count=1, observed_altitude_m=25_000, observed_speed_mps=2_400
        ),
        service.classify(
            track_id="C", sample_count=1, observed_altitude_m=60_000, observed_speed_mps=2_800
        ),
        service.classify(
            track_id="D", sample_count=1, observed_altitude_m=70_000, observed_speed_mps=300
        ),
    ]
    for s in samples:
        assert 0.0 <= s.calibrated_confidence <= 1.0
        assert 0.0 <= s.certified_radius_l2 <= 1.0


def test_consensus_class_matches_majority_weight() -> None:
    service = DiscriminationService()
    result = service.classify(
        track_id="TRK-MAJ",
        sample_count=1,
        observed_altitude_m=60_000,
        observed_speed_mps=2_500,
    )

    tally: dict[str, float] = {}
    for vote in result.votes:
        tally[vote.predicted_class] = tally.get(vote.predicted_class, 0.0) + vote.weight
    expected = max(tally.items(), key=lambda kv: kv[1])[0]
    assert result.consensus_class == expected
