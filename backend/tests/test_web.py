"""Tests for the FastAPI dashboard."""

from __future__ import annotations

from fastapi.testclient import TestClient

from chaos_backend.web import build_app


def _client() -> TestClient:
    return TestClient(build_app())


def test_health_returns_ok() -> None:
    response = _client().get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_version_lists_scenarios() -> None:
    response = _client().get("/version")
    assert response.status_code == 200
    body = response.json()
    assert "version" in body
    assert set(body["scenarios"]) == {"peer_salvo", "regional_crisis", "ambiguous_launch"}


def test_landing_renders_form_with_scenario_options() -> None:
    response = _client().get("/")
    assert response.status_code == 200
    body = response.text
    assert "CHAOS ONE" in body
    assert 'name="scenario"' in body
    assert "peer_salvo" in body
    assert "regional_crisis" in body
    assert "ambiguous_launch" in body


def test_play_returns_rendered_audit_html() -> None:
    response = _client().post(
        "/play",
        data={"scenario": "peer_salvo", "seed": "42"},
    )
    assert response.status_code == 200
    body = response.text
    assert "AUDIT REEL" in body
    assert "CHAIN VERIFIED" in body
    assert "scenario_run_begin" in body


def test_play_rejects_unknown_scenario() -> None:
    response = _client().post(
        "/play",
        data={"scenario": "not_a_real_kind", "seed": "0"},
    )
    assert response.status_code == 400
    assert "unknown scenario" in response.text


def test_unknown_path_returns_json_error() -> None:
    response = _client().get("/nonexistent")
    assert response.status_code == 404
    assert response.json() == {"error": "not found"}


def test_play_stream_emits_sse_frames() -> None:
    response = _client().get("/play/stream?scenario=peer_salvo&seed=42&speed=999")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    body = response.text
    # SSE frame format: lines starting with "event: " followed by "data: ".
    assert "event: audit" in body
    assert "event: done" in body
    assert "scenario_run_begin" in body
    assert "scenario_run_end" in body


def test_play_stream_rejects_unknown_scenario() -> None:
    response = _client().get("/play/stream?scenario=not_a_real_kind")
    assert response.status_code == 400
    assert "event: error" in response.text
    assert "unknown scenario" in response.text


def test_landing_includes_stream_button_and_event_source_js() -> None:
    body = _client().get("/").text
    assert 'id="stream-btn"' in body
    assert "EventSource" in body
