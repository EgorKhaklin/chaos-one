"""Background driver that animates the operations state.

Without a real engagement feeding it, the OperationsState would just
sit at its initial values. The driver runs a small asyncio task that
cycles through interesting moments — mode transitions, COA proposals,
adversary drift — so a fresh visitor to the dashboard sees the
surfaces in motion.

In a real deployment the driver would be replaced by gRPC streams
from the discrimination + COA + adversary services. The shape of
state mutations is identical either way.
"""

from __future__ import annotations

import asyncio
import math
from dataclasses import dataclass

from chaos_backend.operations.state import (
    OperationalMode,
    OperationsState,
    hypothesis,
)
from chaos_backend.services.coa_generator import CourseOfActionService


@dataclass(slots=True)
class DriverConfig:
    tick_seconds: float = 1.0
    adversary_interval_seconds: float = 3.0
    coa_interval_seconds: float = 18.0
    mode_cycle_seconds: float = 40.0


class OperationsDriver:
    """asyncio task wrapper. Call start() during app lifespan startup
    and stop() during shutdown."""

    def __init__(
        self,
        state: OperationsState,
        *,
        coa_service: CourseOfActionService | None = None,
        config: DriverConfig | None = None,
    ) -> None:
        self._state = state
        self._coa_service = coa_service or CourseOfActionService()
        self._config = config or DriverConfig()
        self._task: asyncio.Task[None] | None = None
        self._cancel = asyncio.Event()

    async def start(self) -> None:
        if self._task is not None:
            return
        self._cancel.clear()
        self._task = asyncio.create_task(self._run(), name="operations-driver")

    async def stop(self) -> None:
        if self._task is None:
            return
        self._cancel.set()
        try:
            await asyncio.wait_for(self._task, timeout=3.0)
        except (TimeoutError, asyncio.CancelledError):
            self._task.cancel()
        self._task = None

    async def _run(self) -> None:
        elapsed = 0.0
        last_adversary = -math.inf
        last_coa = -math.inf
        last_mode_cycle = -math.inf

        while not self._cancel.is_set():
            tick = self._config.tick_seconds

            await self._state.tick_countdowns(tick)

            if elapsed - last_adversary >= self._config.adversary_interval_seconds:
                await self._emit_adversary(elapsed)
                last_adversary = elapsed

            if elapsed - last_coa >= self._config.coa_interval_seconds:
                await self._emit_coa_set()
                last_coa = elapsed

            if elapsed - last_mode_cycle >= self._config.mode_cycle_seconds:
                await self._advance_mode_cycle()
                last_mode_cycle = elapsed

            try:
                await asyncio.wait_for(self._cancel.wait(), timeout=tick)
            except TimeoutError:
                pass
            elapsed += tick

    async def _emit_adversary(self, elapsed: float) -> None:
        oscillation = (math.sin(elapsed * 0.05) + 1.0) / 2.0
        charlie7 = 0.55 + 0.15 * oscillation
        bravo3 = 0.30 - 0.10 * oscillation
        unknown = max(0.0, 1.0 - charlie7 - bravo3)

        await self._state.update_adversary(
            [
                hypothesis(
                    "charlie-7",
                    "Charlie-7 saturation HGV + decoy cloud",
                    charlie7,
                    0.10 * math.cos(elapsed * 0.05),
                ),
                hypothesis(
                    "bravo-3",
                    "Bravo-3 probe, no follow-on",
                    bravo3,
                    -0.06 * math.cos(elapsed * 0.05),
                ),
                hypothesis("unknown", "Off-distribution / unknown", unknown, 0.0),
            ],
            cost_imposition_index=1.10 + 0.08 * math.sin(elapsed * 0.02),
        )

    async def _emit_coa_set(self) -> None:
        if len(self._state.active_coas) >= self._state.MAX_ACTIVE_COAS:
            return
        bundle = self._coa_service.generate(
            classified_track_ids=["TRK-001", "TRK-002", "TRK-003", "TRK-004"],
            roe_envelope_id="ROE-2",
        )
        for item in bundle.items:
            await self._state.propose_coa(
                item,
                is_recommended=(item.id == bundle.recommended_id),
            )

    async def _advance_mode_cycle(self) -> None:
        cycle = [
            OperationalMode.NOMINAL,
            OperationalMode.SENSOR_DEGRADED,
            OperationalMode.NOMINAL,
            OperationalMode.ADVISORY_ONLY,
        ]
        current = self._state.mode
        try:
            index = cycle.index(current)
        except ValueError:
            index = 0
        next_mode = cycle[(index + 1) % len(cycle)]
        await self._state.transition_mode(next_mode)
