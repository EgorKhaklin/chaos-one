"""Tests for the SQLite engagement catalog."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from chaos_backend.storage import EngagementRepository


@pytest.fixture
def repo(tmp_path: Path) -> EngagementRepository:
    db_path = tmp_path / "engagements.db"
    repository = EngagementRepository(database_path=db_path)
    repository.init()
    return repository


def _insert(
    repo: EngagementRepository,
    *,
    scenario: str = "peer_salvo",
    seed: int = 42,
    events: int = 11,
    verified: bool = True,
    log_path: str = "/tmp/log.jsonl",
) -> str:
    record = repo.insert(
        scenario=scenario,
        seed=seed,
        started_at=datetime.now(UTC),
        ended_at=datetime.now(UTC),
        events=events,
        verified=verified,
        log_path=log_path,
    )
    return record.id


def test_init_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "engagements.db"
    EngagementRepository(database_path=db_path).init()
    EngagementRepository(database_path=db_path).init()
    assert db_path.exists()


def test_insert_returns_record_with_generated_id(repo: EngagementRepository) -> None:
    record = repo.insert(
        scenario="peer_salvo",
        seed=42,
        started_at=datetime.now(UTC),
        ended_at=datetime.now(UTC),
        events=11,
        verified=True,
        log_path="/tmp/log.jsonl",
    )
    assert record.id.startswith("eng_")
    assert record.scenario == "peer_salvo"
    assert record.verified is True


def test_get_round_trips_the_record(repo: EngagementRepository) -> None:
    inserted_id = _insert(repo)
    fetched = repo.get(inserted_id)
    assert fetched is not None
    assert fetched.id == inserted_id


def test_get_unknown_id_returns_none(repo: EngagementRepository) -> None:
    assert repo.get("eng_does_not_exist") is None


def test_recent_returns_records_in_descending_order(repo: EngagementRepository) -> None:
    import time

    first = _insert(repo, scenario="peer_salvo")
    time.sleep(1.01)  # ISO timestamps have 1-second resolution
    second = _insert(repo, scenario="regional_crisis")

    records = repo.recent(limit=10)
    assert [r.id for r in records[:2]] == [second, first]


def test_recent_respects_limit(repo: EngagementRepository) -> None:
    for _ in range(5):
        _insert(repo)
    assert len(repo.recent(limit=3)) == 3


def test_count_reflects_inserts(repo: EngagementRepository) -> None:
    assert repo.count() == 0
    _insert(repo)
    _insert(repo)
    assert repo.count() == 2


def test_delete_removes_the_record(repo: EngagementRepository) -> None:
    inserted = _insert(repo)
    assert repo.delete(inserted) is True
    assert repo.get(inserted) is None
    assert repo.delete(inserted) is False


def test_naive_datetimes_get_treated_as_utc(repo: EngagementRepository) -> None:
    record = repo.insert(
        scenario="peer_salvo",
        seed=0,
        started_at=datetime(2026, 5, 19, 9, 25, 0),
        ended_at=datetime(2026, 5, 19, 9, 25, 30),
        events=2,
        verified=True,
        log_path="/tmp/log.jsonl",
    )
    assert record.started_at.endswith("+00:00")
    assert record.ended_at.endswith("+00:00")
