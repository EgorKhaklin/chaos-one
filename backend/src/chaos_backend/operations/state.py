"""In-memory operator state with async pub/sub.

`OperationsState` holds the current mode, the active COA queue (capped
at three per the Phase 2 cognitive-load constraint), and the latest
adversary distribution. Every mutation publishes an event to each
subscribed `asyncio.Queue`; the SSE endpoint creates one queue per
connected browser and yields events as they arrive.

Single-process: this state is not durable across restarts. Audit
records still go to the SQLite engagement catalog through the
existing AuditLogWriter path.
"""

from __future__ import annotations

import asyncio
import secrets
import time
from collections.abc import AsyncIterator, Iterable
from dataclasses import asdict, dataclass
from enum import StrEnum

from chaos_backend.services.coa_generator import CourseOfActionItem


class OperationalMode(StrEnum):
    NOMINAL = "nominal"
    SENSOR_DEGRADED = "sensor_degraded"
    COMMS_DEGRADED = "comms_degraded"
    CYBER_SUSPECT = "cyber_suspect"
    ADVISORY_ONLY = "advisory_only"
    AUTONOMOUS_FIRE = "autonomous_fire"


@dataclass(frozen=True, slots=True)
class OperationsEvent:
    event_type: str
    payload: dict[str, object]
    timestamp_s: float


@dataclass(slots=True)
class ActiveCoa:
    id: str
    headline: str
    why: str
    expected_leakage: float
    expected_leakage_band: float
    escalation: str
    releasability: str
    countdown_seconds_initial: float
    countdown_seconds_remaining: float
    is_recommended: bool

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(slots=True)
class _AdversaryHypothesis:
    playbook_id: str
    display_name: str
    weight: float
    delta_30s: float

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


class OperationsState:
    """Singleton-shaped store of operator-visible state.

    Construct one per app; FastAPI dependency-injection keeps the
    instance alive for the application's lifetime.
    """

    MAX_ACTIVE_COAS = 3

    def __init__(self) -> None:
        self._mode = OperationalMode.NOMINAL
        self._coas: dict[str, ActiveCoa] = {}
        self._adversary: list[_AdversaryHypothesis] = []
        self._cost_imposition_index: float = 1.0
        self._subscribers: set[asyncio.Queue[OperationsEvent]] = set()
        self._lock = asyncio.Lock()

    # ── subscriptions ───────────────────────────────────────────────

    async def subscribe(self) -> asyncio.Queue[OperationsEvent]:
        queue: asyncio.Queue[OperationsEvent] = asyncio.Queue(maxsize=128)
        async with self._lock:
            self._subscribers.add(queue)
        # Replay the current snapshot so a freshly-connected client
        # doesn't render an empty UI until the next event lands.
        await queue.put(self._snapshot_event())
        return queue

    async def unsubscribe(self, queue: asyncio.Queue[OperationsEvent]) -> None:
        async with self._lock:
            self._subscribers.discard(queue)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)

    async def _publish(self, event_type: str, payload: dict[str, object]) -> None:
        event = OperationsEvent(
            event_type=event_type,
            payload=payload,
            timestamp_s=time.time(),
        )
        async with self._lock:
            dead: list[asyncio.Queue[OperationsEvent]] = []
            for queue in self._subscribers:
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    dead.append(queue)
            for queue in dead:
                self._subscribers.discard(queue)

    # ── mode ────────────────────────────────────────────────────────

    @property
    def mode(self) -> OperationalMode:
        return self._mode

    async def transition_mode(self, new_mode: OperationalMode) -> None:
        if new_mode == self._mode:
            return
        previous = self._mode
        self._mode = new_mode
        await self._publish(
            "mode_changed",
            {"previous": previous.value, "current": new_mode.value},
        )

    # ── coa queue ───────────────────────────────────────────────────

    @property
    def active_coas(self) -> list[ActiveCoa]:
        return list(self._coas.values())

    async def propose_coa(
        self, item: CourseOfActionItem, *, is_recommended: bool = False
    ) -> ActiveCoa | None:
        if len(self._coas) >= self.MAX_ACTIVE_COAS:
            return None
        coa = ActiveCoa(
            id=item.id,
            headline=item.headline,
            why=item.description,
            expected_leakage=item.expected_leakage.point,
            expected_leakage_band=item.expected_leakage.high - item.expected_leakage.low,
            escalation=item.escalation_level,
            releasability=item.releasability,
            countdown_seconds_initial=item.countdown_seconds,
            countdown_seconds_remaining=item.countdown_seconds,
            is_recommended=is_recommended,
        )
        self._coas[coa.id] = coa
        await self._publish("coa_proposed", {"coa": coa.as_dict()})
        return coa

    async def authorize_coa(self, coa_id: str, *, source: str = "operator") -> bool:
        coa = self._coas.pop(coa_id, None)
        if coa is None:
            return False
        await self._publish(
            "coa_authorized",
            {"id": coa_id, "headline": coa.headline, "source": source},
        )
        return True

    async def object_coa(self, coa_id: str, reason: str) -> bool:
        coa = self._coas.pop(coa_id, None)
        if coa is None:
            return False
        await self._publish(
            "coa_objected",
            {"id": coa_id, "headline": coa.headline, "reason": reason},
        )
        return True

    async def tick_countdowns(self, dt_seconds: float) -> None:
        expired: list[str] = []
        for coa in self._coas.values():
            coa.countdown_seconds_remaining = max(0.0, coa.countdown_seconds_remaining - dt_seconds)
            if coa.countdown_seconds_remaining <= 0.0:
                expired.append(coa.id)
        for coa_id in expired:
            coa = self._coas.pop(coa_id)
            await self._publish(
                "coa_expired",
                {"id": coa.id, "headline": coa.headline, "auto_authorized": coa.is_recommended},
            )
        if self._coas:
            await self._publish(
                "coa_tick",
                {
                    "remaining": {
                        coa.id: round(coa.countdown_seconds_remaining, 1)
                        for coa in self._coas.values()
                    }
                },
            )

    # ── adversary mirror ────────────────────────────────────────────

    @property
    def adversary_hypotheses(self) -> list[_AdversaryHypothesis]:
        return list(self._adversary)

    @property
    def cost_imposition_index(self) -> float:
        return self._cost_imposition_index

    async def update_adversary(
        self,
        hypotheses: Iterable[_AdversaryHypothesis],
        cost_imposition_index: float,
    ) -> None:
        self._adversary = list(hypotheses)
        self._cost_imposition_index = cost_imposition_index
        await self._publish(
            "adversary_updated",
            {
                "hypotheses": [h.as_dict() for h in self._adversary],
                "cost_imposition_index": round(cost_imposition_index, 4),
            },
        )

    # ── snapshot for new subscribers ────────────────────────────────

    def _snapshot_event(self) -> OperationsEvent:
        return OperationsEvent(
            event_type="snapshot",
            payload={
                "mode": self._mode.value,
                "coas": [coa.as_dict() for coa in self._coas.values()],
                "adversary": {
                    "hypotheses": [h.as_dict() for h in self._adversary],
                    "cost_imposition_index": round(self._cost_imposition_index, 4),
                },
            },
            timestamp_s=time.time(),
        )


def hypothesis(
    playbook_id: str, display_name: str, weight: float, delta_30s: float = 0.0
) -> _AdversaryHypothesis:
    return _AdversaryHypothesis(
        playbook_id=playbook_id,
        display_name=display_name,
        weight=weight,
        delta_30s=delta_30s,
    )


def new_coa_id() -> str:
    return "COA-" + secrets.token_hex(2).upper()


async def drain(queue: asyncio.Queue[OperationsEvent]) -> AsyncIterator[OperationsEvent]:
    """Yield events from a subscriber queue until cancelled."""
    while True:
        event = await queue.get()
        yield event
