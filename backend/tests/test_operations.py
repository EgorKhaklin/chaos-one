"""Tests for the live operations dashboard."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chaos_backend.operations import OperationalMode, OperationsState
from chaos_backend.operations.state import hypothesis
from chaos_backend.services.coa_generator import (
    CourseOfActionItem,
    MagazineDelta,
    OutcomeBand,
)
from chaos_backend.storage import EngagementRepository
from chaos_backend.web import build_app


def _coa(coa_id: str = "COA-X", countdown: float = 8.0) -> CourseOfActionItem:
    return CourseOfActionItem(
        id=coa_id,
        headline="mixed",
        description="why",
        expected_leakage=OutcomeBand(point=0.05, low=0.02, high=0.08),
        cost=MagazineDelta(ngi=2),
        escalation_level="LOW",
        releasability="NATO",
        countdown_seconds=countdown,
    )


@pytest.fixture
def isolated_client(tmp_path: Path) -> TestClient:
    repo = EngagementRepository(database_path=tmp_path / "engagements.db")
    repo.init()
    return TestClient(
        build_app(
            repository=repo,
            log_directory=tmp_path / "audit",
            configure_observability=False,
            start_operations_driver=False,
        ),
    )


async def test_state_publishes_mode_transition_to_subscribers() -> None:
    state = OperationsState()
    queue = await state.subscribe()
    # Drain the snapshot that subscribe() pre-puts on the queue.
    _ = await queue.get()

    await state.transition_mode(OperationalMode.SENSOR_DEGRADED)

    event = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert event.event_type == "mode_changed"
    assert event.payload["previous"] == "nominal"
    assert event.payload["current"] == "sensor_degraded"


async def test_state_caps_active_coas_at_three() -> None:
    state = OperationsState()
    await state.propose_coa(_coa("COA-A"))
    await state.propose_coa(_coa("COA-B"))
    await state.propose_coa(_coa("COA-C"))
    fourth = await state.propose_coa(_coa("COA-D"))

    assert fourth is None
    assert len(state.active_coas) == 3


async def test_authorize_removes_and_publishes() -> None:
    state = OperationsState()
    await state.propose_coa(_coa("COA-A"))
    queue = await state.subscribe()
    _ = await queue.get()  # drain snapshot

    ok = await state.authorize_coa("COA-A", source="test")
    assert ok is True
    assert len(state.active_coas) == 0

    event = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert event.event_type == "coa_authorized"
    assert event.payload["source"] == "test"


async def test_tick_countdowns_expires_at_zero() -> None:
    state = OperationsState()
    await state.propose_coa(_coa("COA-A", countdown=0.5))
    queue = await state.subscribe()
    _ = await queue.get()  # snapshot

    await state.tick_countdowns(1.0)

    seen: list[str] = []
    while not queue.empty():
        seen.append((await queue.get()).event_type)

    assert "coa_expired" in seen
    assert len(state.active_coas) == 0


async def test_adversary_update_broadcasts() -> None:
    state = OperationsState()
    queue = await state.subscribe()
    _ = await queue.get()  # snapshot

    await state.update_adversary(
        [hypothesis("c7", "Charlie-7", 0.7), hypothesis("u", "Unknown", 0.3)],
        cost_imposition_index=1.12,
    )

    event = await asyncio.wait_for(queue.get(), timeout=1.0)
    assert event.event_type == "adversary_updated"
    assert event.payload["cost_imposition_index"] == pytest.approx(1.12, rel=1e-3)
    assert len(event.payload["hypotheses"]) == 2


async def test_subscribe_replays_snapshot_to_late_joiner() -> None:
    state = OperationsState()
    await state.transition_mode(OperationalMode.SENSOR_DEGRADED)
    await state.propose_coa(_coa("COA-A"))

    queue = await state.subscribe()
    snap = await asyncio.wait_for(queue.get(), timeout=1.0)

    assert snap.event_type == "snapshot"
    assert snap.payload["mode"] == "sensor_degraded"
    assert any(coa["id"] == "COA-A" for coa in snap.payload["coas"])


def test_ops_landing_renders(isolated_client: TestClient) -> None:
    response = isolated_client.get("/ops")
    assert response.status_code == 200
    body = response.text
    assert "MODE" in body or "NOMINAL" in body
    assert "DECISIONS" in body
    assert "ADVERSARY MIRROR" in body
    assert "/ops/stream" in body


def test_ops_authorize_404_when_coa_missing(isolated_client: TestClient) -> None:
    response = isolated_client.post("/ops/coa/COA-NOPE/authorize")
    assert response.status_code == 404


def test_ops_object_404_when_coa_missing(isolated_client: TestClient) -> None:
    response = isolated_client.post(
        "/ops/coa/COA-NOPE/object",
        data={"reason": "nope"},
    )
    assert response.status_code == 404


def test_landing_includes_ops_link(isolated_client: TestClient) -> None:
    body = isolated_client.get("/").text
    assert "/ops" in body
