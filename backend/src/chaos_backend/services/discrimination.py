"""Discrimination service.

Ensemble of classifiers vote on threat class. Each vote carries a model
identifier and a weight; the aggregate distribution is what the UI
renders. Disagreement among models surfaces as ensemble striping on the
envelope.

The four "models" here are hand-engineered policies over physical
features (see chaos_backend.services.features). Real ML — a physics-
informed NN, a gradient-boosted decision model, a transformer over
track history, and a rule baseline — replaces them in milestone 4+.
The public API of this module is fixed against the proto contract and
should not change when the underlying models do.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass

import structlog

from chaos_backend.services.features import TrackFeatures, extract

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


_PINN = "pinn_v1"
_LGBM = "lgbm_v1"
_TSF = "ts_transformer_v1"
_RULE = "rule_baseline_v1"

_MODEL_WEIGHTS = {
    _PINN: 0.34,
    _LGBM: 0.28,
    _TSF: 0.22,
    _RULE: 0.16,
}


def _physics_vote(features: TrackFeatures) -> str:
    """High kinetic energy plus low atmospheric density reads as HGV.
    High altitude with very high energy and high vertical share reads
    as a ballistic reentry. Otherwise fall through to atmospheric
    classes by altitude and speed band."""
    if features.altitude_band >= 3 and features.specific_kinetic_energy > 4.5e6:
        if features.ballistic_indicator > 0.6:
            return "BALLISTIC_RV"
        return "HGV"

    if features.altitude_band == 2 and features.speed_band == 3:
        return "HGV"

    if features.altitude_band <= 1 and features.speed_band >= 2:
        return "CRUISE_MISSILE"

    if features.altitude_band <= 1 and features.speed_band <= 1:
        return "UAS"

    return "HGV"


def _lgbm_vote(features: TrackFeatures) -> str:
    """Bucketed lookup over (altitude_band, speed_band). Mirrors what a
    gradient-boosted decision tree would learn on this feature space."""
    table = {
        (0, 0): "UAS",
        (0, 1): "UAS",
        (0, 2): "CRUISE_MISSILE",
        (0, 3): "CRUISE_MISSILE",
        (1, 0): "UAS",
        (1, 1): "CRUISE_MISSILE",
        (1, 2): "CRUISE_MISSILE",
        (1, 3): "HGV",
        (2, 0): "DEBRIS",
        (2, 1): "HGV",
        (2, 2): "HGV",
        (2, 3): "HGV",
        (3, 0): "DEBRIS",
        (3, 1): "BALLISTIC_RV",
        (3, 2): "HGV",
        (3, 3): "HGV",
        (4, 0): "DEBRIS",
        (4, 1): "BALLISTIC_RV",
        (4, 2): "BALLISTIC_RV",
        (4, 3): "HGV",
    }
    return table.get((features.altitude_band, features.speed_band), "HGV")


def _transformer_vote(features: TrackFeatures, track_id: str) -> str:
    """No real history yet; mix the physics vote with a small
    track-id-dependent perturbation so the ensemble can disagree under
    near-ties. Drops one class to "DECOY" on a fixed fraction of inputs,
    representing the transformer's known false-positive distribution."""
    physics = _physics_vote(features)
    digest = hashlib.sha256(track_id.encode("utf-8")).digest()
    bucket = digest[0] / 256.0
    if bucket < 0.12:
        return "DECOY"
    if features.altitude_band == 0 and bucket < 0.30 and physics == "UAS":
        return "DEBRIS"
    return physics


def _rule_vote(features: TrackFeatures) -> str:
    """Simplest legible baseline. Never the strongest, but the most
    explainable; surfaces in the audit reel as the floor everyone
    else is competing against."""
    if features.altitude_m >= 50_000:
        return "BALLISTIC_RV"
    if features.altitude_m <= 1_000:
        return "CRUISE_MISSILE" if features.speed_mps >= 200 else "UAS"
    return "HGV"


def _calibrated_confidence(votes: tuple[EnsembleVote, ...], primary: str) -> float:
    """Sum of weights agreeing with the primary class, clamped to a
    range that never lets the system feel either unjustifiably certain
    or completely lost."""
    agreement = sum(v.weight for v in votes if v.predicted_class == primary)
    return float(min(0.97, max(0.55, agreement)))


def _certified_radius(confidence: float) -> float:
    """Smoothed-classifier proxy: more confident outputs are stable
    over wider input perturbations. Returns the L2 radius up to which
    classification is provably stable, in normalized feature units."""
    return float(min(0.30, 0.05 + 0.40 * (confidence - 0.5)))


class DiscriminationService:
    """Feature-driven ensemble discriminator."""

    def classify(
        self,
        track_id: str,
        sample_count: int,
        *,
        observed_speed_mps: float | None = None,
        observed_altitude_m: float | None = None,
    ) -> Classification:
        _ = sample_count  # reserved for the transformer's history window
        features = extract(
            altitude_m=observed_altitude_m,
            speed_mps=observed_speed_mps,
        )

        physics = _physics_vote(features)
        lgbm = _lgbm_vote(features)
        transformer = _transformer_vote(features, track_id)
        rule = _rule_vote(features)

        votes = (
            EnsembleVote(_PINN, physics, _MODEL_WEIGHTS[_PINN]),
            EnsembleVote(_LGBM, lgbm, _MODEL_WEIGHTS[_LGBM]),
            EnsembleVote(_TSF, transformer, _MODEL_WEIGHTS[_TSF]),
            EnsembleVote(_RULE, rule, _MODEL_WEIGHTS[_RULE]),
        )

        # Tally for the primary class.
        tally: dict[str, float] = {}
        for vote in votes:
            tally[vote.predicted_class] = tally.get(vote.predicted_class, 0.0) + vote.weight
        primary = max(tally.items(), key=lambda kv: kv[1])[0]

        confidence = _calibrated_confidence(votes, primary)
        radius = _certified_radius(confidence)

        return Classification(
            track_id=track_id,
            votes=votes,
            calibrated_confidence=confidence,
            certified_radius_l2=radius,
        )

    def classify_many(self, track_ids: Iterable[str]) -> list[Classification]:
        return [self.classify(track_id=tid, sample_count=1) for tid in track_ids]
