"""Course-of-action generator.

Returns a ranked list of COAs given the current classified threat set
and the active ROE envelope. The real implementation uses CP-SAT
(OR-Tools) over a stochastic engagement program; this stub returns
scripted COAs that exercise the front-end card layout, countdown, and
recommendation highlighting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True, slots=True)
class MagazineDelta:
    ngi: int = 0
    sm3: int = 0
    sm6: int = 0
    pac3: int = 0
    hel_megajoules: float = 0.0


@dataclass(frozen=True, slots=True)
class OutcomeBand:
    point: float
    low: float
    high: float


@dataclass(frozen=True, slots=True)
class CourseOfActionItem:
    id: str
    headline: str
    description: str
    expected_leakage: OutcomeBand
    cost: MagazineDelta
    escalation_level: str
    releasability: str
    countdown_seconds: float


@dataclass(frozen=True, slots=True)
class COABundle:
    items: tuple[CourseOfActionItem, ...]
    recommended_id: str


class CourseOfActionService:
    """Mock COA generator. Returns three canned COAs against any input."""

    def generate(
        self,
        classified_track_ids: Iterable[str],
        roe_envelope_id: str,
    ) -> COABundle:
        track_count = len(list(classified_track_ids))

        coa_a = CourseOfActionItem(
            id="COA-A",
            headline="Pure kinetic",
            description=(
                f"Engage {track_count} confirmed threats with NGI midcourse."
                " No directed-energy or non-kinetic component."
            ),
            expected_leakage=OutcomeBand(point=0.07, low=0.03, high=0.11),
            cost=MagazineDelta(ngi=max(1, track_count)),
            escalation_level="MODERATE",
            releasability="NATO",
            countdown_seconds=10.0,
        )

        coa_b = CourseOfActionItem(
            id="COA-B",
            headline="Mixed engagement",
            description=(
                "NGI on highest-confidence midcourse threats."
                " HEL warmed for swarm screen. Non-attributable cyber denial"
                " of adversary GNSS guidance under ROE-2."
            ),
            expected_leakage=OutcomeBand(point=0.05, low=0.02, high=0.08),
            cost=MagazineDelta(ngi=max(1, track_count - 2), hel_megajoules=1.2),
            escalation_level="LOW",
            releasability="NATO",
            countdown_seconds=8.0,
        )

        coa_c = CourseOfActionItem(
            id="COA-C",
            headline="Conservative reserve",
            description=(
                "Engage two threats now. Reserve magazine for projected"
                " Wave-2 launch within next 5 minutes per adversary model."
            ),
            expected_leakage=OutcomeBand(point=0.11, low=0.06, high=0.17),
            cost=MagazineDelta(ngi=2),
            escalation_level="LOW",
            releasability="NATO",
            countdown_seconds=12.0,
        )

        return COABundle(items=(coa_a, coa_b, coa_c), recommended_id="COA-B")
