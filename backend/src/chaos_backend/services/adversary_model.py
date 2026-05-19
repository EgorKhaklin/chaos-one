"""Adversary playbook estimator.

Maintains a distribution over named adversary playbooks and a cost-imposition
index that rolls forward over a 24h window. Real implementation uses a
Bayesian network with online updates; this stub returns a scripted
distribution that visibly shifts over time so the front-end's delta
indicators and sparkline have something to render.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PlaybookHypothesis:
    playbook_id: str
    display_name: str
    weight: float
    delta_30s: float


@dataclass(frozen=True, slots=True)
class PlaybookDistribution:
    timestamp_s: float
    hypotheses: tuple[PlaybookHypothesis, ...]
    cost_imposition_index: float


class AdversaryModelService:
    """Mock adversary model. Three hypotheses with sinusoidally-shifting weights."""

    _started_at: float

    def __init__(self) -> None:
        self._started_at = time.monotonic()

    def current(self) -> PlaybookDistribution:
        elapsed = time.monotonic() - self._started_at
        oscillation = (math.sin(elapsed * 0.05) + 1.0) / 2.0  # 0..1

        charlie7_weight = 0.55 + 0.15 * oscillation
        bravo3_weight = 0.30 - 0.10 * oscillation
        unknown_weight = max(0.0, 1.0 - charlie7_weight - bravo3_weight)

        hypotheses = (
            PlaybookHypothesis(
                playbook_id="charlie-7",
                display_name="Charlie-7 saturation HGV + decoy cloud",
                weight=charlie7_weight,
                delta_30s=0.10 * math.cos(elapsed * 0.05),
            ),
            PlaybookHypothesis(
                playbook_id="bravo-3",
                display_name="Bravo-3 probe, no follow-on",
                weight=bravo3_weight,
                delta_30s=-0.06 * math.cos(elapsed * 0.05),
            ),
            PlaybookHypothesis(
                playbook_id="unknown",
                display_name="Off-distribution / unknown",
                weight=unknown_weight,
                delta_30s=0.0,
            ),
        )

        cost_imposition = 1.10 + 0.08 * math.sin(elapsed * 0.02)

        return PlaybookDistribution(
            timestamp_s=time.time(),
            hypotheses=hypotheses,
            cost_imposition_index=cost_imposition,
        )
