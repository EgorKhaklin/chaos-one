"""Discrimination service.

Ensemble of classifiers vote on threat class. Each vote carries a model
identifier and a weight; the aggregate distribution is what the UI renders.
Disagreement among models surfaces as ensemble striping on the envelope.

The mock implementation here returns deterministic scripted votes so the
front-end can develop against a stable contract. The real ensemble
(physics-informed NN + GBDT + transformer-on-timeseries + rule baseline)
replaces this in milestone 4+.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass

import structlog

logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class EnsembleVote:
    model_id: str
    predicted_class: str
    weight: float


@dataclass(frozen=True, slots=True)
class Classification:
    track_id: str
    votes: tuple[EnsembleVote, ...]
    calibrated_confidence: float
    certified_radius_l2: float

    @property
    def consensus_class(self) -> str:
        tally: dict[str, float] = {}
        for vote in self.votes:
            tally[vote.predicted_class] = tally.get(vote.predicted_class, 0.0) + vote.weight
        return max(tally.items(), key=lambda kv: kv[1])[0]


_MODEL_IDS = ("pinn_v1", "lgbm_v1", "ts_transformer_v1", "rule_baseline_v1")


class DiscriminationService:
    """Mock discriminator. Deterministic given (track_id, sample_count)."""

    def classify(
        self,
        track_id: str,
        sample_count: int,
        *,
        observed_speed_mps: float | None = None,
        observed_altitude_m: float | None = None,
    ) -> Classification:
        rng_seed = abs(hash((track_id, sample_count // 10))) % 2**31
        deterministic = (rng_seed % 1000) / 1000.0

        # Cheap heuristic to make the mock behave somewhat like the real thing:
        # high-altitude + high-speed lean RV; low-altitude lean cruise / UAS.
        primary = "HGV"
        if observed_altitude_m is not None and observed_altitude_m < 2000:
            primary = "CRUISE_MISSILE" if (observed_speed_mps or 0) > 250 else "UAS"

        secondary = "DECOY"

        if deterministic < 0.15:
            primary, secondary = secondary, primary

        votes = (
            EnsembleVote(_MODEL_IDS[0], primary, 0.34 + 0.06 * math.sin(rng_seed)),
            EnsembleVote(_MODEL_IDS[1], primary, 0.28 + 0.04 * math.cos(rng_seed)),
            EnsembleVote(_MODEL_IDS[2], primary if deterministic > 0.20 else secondary, 0.22),
            EnsembleVote(_MODEL_IDS[3], primary, 0.16),
        )

        agreement_fraction = sum(v.weight for v in votes if v.predicted_class == primary)
        confidence = min(0.97, max(0.55, agreement_fraction))
        radius = 0.05 + 0.15 * (confidence - 0.5)

        return Classification(
            track_id=track_id,
            votes=votes,
            calibrated_confidence=confidence,
            certified_radius_l2=radius,
        )

    def classify_many(self, track_ids: Iterable[str]) -> list[Classification]:
        return [self.classify(track_id=tid, sample_count=1) for tid in track_ids]
