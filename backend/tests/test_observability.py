"""Tests for the structured-logging layer."""

from __future__ import annotations

import json
from pathlib import Path

import structlog
from fastapi.testclient import TestClient

from chaos_backend.observability import configure_logging, new_request_id
from chaos_backend.storage import EngagementRepository
from chaos_backend.web import build_app


def test_new_request_id_has_short_prefixed_form() -> None:
    rid = new_request_id()
    assert rid.startswith("rq_")
    assert len(rid) == 3 + 8


def test_configure_logging_emits_json_lines(capsys: object) -> None:
    configure_logging(level="INFO", pretty=False)
    logger = structlog.get_logger("test")
    logger.info("hello", k="v")
    captured = capsys.readouterr()  # type: ignore[attr-defined]
    body = captured.out or captured.err
    line = body.strip().splitlines()[-1]
    payload = json.loads(line)
    assert payload["event"] == "hello"
    assert payload["k"] == "v"
    assert payload["level"] == "info"
    assert "timestamp" in payload


def test_request_logging_middleware_attaches_request_id(tmp_path: Path) -> None:
    repo = EngagementRepository(database_path=tmp_path / "engagements.db")
    repo.init()
    app = build_app(
        repository=repo,
        log_directory=tmp_path / "audit",
        configure_observability=False,
    )
    client = TestClient(app)

    response = client.get("/health")
    assert response.status_code == 200
    rid = response.headers.get("X-Request-ID")
    assert rid is not None
    assert rid.startswith("rq_")


def test_request_logging_middleware_respects_inbound_request_id(tmp_path: Path) -> None:
    repo = EngagementRepository(database_path=tmp_path / "engagements.db")
    repo.init()
    app = build_app(
        repository=repo,
        log_directory=tmp_path / "audit",
        configure_observability=False,
    )
    client = TestClient(app)

    inbound = "rq_caller_xyz"
    response = client.get("/health", headers={"X-Request-ID": inbound})
    assert response.headers["X-Request-ID"] == inbound


def test_request_logger_emits_one_access_line_per_request(
    tmp_path: Path,
) -> None:
    configure_logging(level="INFO", pretty=False)

    repo = EngagementRepository(database_path=tmp_path / "engagements.db")
    repo.init()
    app = build_app(
        repository=repo,
        log_directory=tmp_path / "audit",
        configure_observability=False,
    )
    client = TestClient(app)

    with structlog.testing.capture_logs() as captured:
        client.get("/health")
        client.get("/version")

    request_events = [e for e in captured if e.get("event") == "request"]
    paths = {e["path"] for e in request_events}
    assert "/health" in paths
    assert "/version" in paths
    statuses = {e["status"] for e in request_events}
    assert statuses == {200}
