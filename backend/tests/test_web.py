"""Tests for the FastAPI dashboard."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from chaos_backend.storage import EngagementRepository
from chaos_backend.web import build_app


def _client() -> TestClient:
    return TestClient(build_app())


@pytest.fixture
def isolated_client(tmp_path: Path) -> TestClient:
    repo = EngagementRepository(database_path=tmp_path / "engagements.db")
    repo.init()
    return TestClient(
        build_app(repository=repo, log_directory=tmp_path / "audit"),
    )


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


def test_engagements_list_is_empty_initially(isolated_client: TestClient) -> None:
    response = isolated_client.get("/engagements")
    assert response.status_code == 200
    assert response.json() == {"count": 0, "engagements": []}


def test_play_records_and_engagements_lists_it(isolated_client: TestClient) -> None:
    play_response = isolated_client.post(
        "/play",
        data={"scenario": "peer_salvo", "seed": "42"},
    )
    assert play_response.status_code == 200

    listing = isolated_client.get("/engagements").json()
    assert listing["count"] == 1
    record = listing["engagements"][0]
    assert record["scenario"] == "peer_salvo"
    assert record["seed"] == 42
    assert record["verified"] is True


def test_engagement_detail_round_trips(isolated_client: TestClient) -> None:
    isolated_client.post("/play", data={"scenario": "regional_crisis", "seed": "9"})
    listing = isolated_client.get("/engagements").json()
    record = listing["engagements"][0]

    detail = isolated_client.get(f"/engagements/{record['id']}").json()
    assert detail["id"] == record["id"]
    assert detail["scenario"] == "regional_crisis"


def test_engagement_audit_html_renders_from_stored_log(isolated_client: TestClient) -> None:
    isolated_client.post("/play", data={"scenario": "peer_salvo", "seed": "1"})
    record = isolated_client.get("/engagements").json()["engagements"][0]

    html_response = isolated_client.get(f"/engagements/{record['id']}/audit.html")
    assert html_response.status_code == 200
    assert "AUDIT REEL" in html_response.text
    assert "CHAIN VERIFIED" in html_response.text


def test_engagement_detail_404_for_unknown_id(isolated_client: TestClient) -> None:
    response = isolated_client.get("/engagements/eng_nope")
    assert response.status_code == 404


def test_landing_shows_recent_engagements_table_after_run(
    isolated_client: TestClient,
) -> None:
    isolated_client.post("/play", data={"scenario": "peer_salvo", "seed": "2"})
    body = isolated_client.get("/").text
    assert "RECENT ENGAGEMENTS" in body
    assert "peer_salvo" in body


def test_engagement_diff_identical_runs(isolated_client: TestClient) -> None:
    isolated_client.post("/play", data={"scenario": "peer_salvo", "seed": "42"})
    isolated_client.post("/play", data={"scenario": "peer_salvo", "seed": "42"})

    records = isolated_client.get("/engagements").json()["engagements"]
    a_id, b_id = records[0]["id"], records[1]["id"]

    response = isolated_client.get(f"/engagements/{a_id}/diff/{b_id}")
    assert response.status_code == 200
    assert "IDENTICAL" in response.text


def test_engagement_diff_divergent_seeds(isolated_client: TestClient) -> None:
    isolated_client.post("/play", data={"scenario": "peer_salvo", "seed": "1"})
    isolated_client.post("/play", data={"scenario": "peer_salvo", "seed": "2"})

    records = isolated_client.get("/engagements").json()["engagements"]
    a_id, b_id = records[0]["id"], records[1]["id"]

    response = isolated_client.get(f"/engagements/{a_id}/diff/{b_id}")
    assert response.status_code == 200
    assert "DIVERGENT" in response.text


def test_engagement_diff_404_when_either_missing(isolated_client: TestClient) -> None:
    isolated_client.post("/play", data={"scenario": "peer_salvo", "seed": "0"})
    real_id = isolated_client.get("/engagements").json()["engagements"][0]["id"]

    a_missing = isolated_client.get(f"/engagements/eng_nope/diff/{real_id}")
    b_missing = isolated_client.get(f"/engagements/{real_id}/diff/eng_nope")
    assert a_missing.status_code == 404
    assert b_missing.status_code == 404


def test_landing_inline_diff_link_appears_for_repeated_scenario(
    isolated_client: TestClient,
) -> None:
    # Two runs of the same scenario; the newer row should get a
    # "diff prev" link pointing at the older one.
    isolated_client.post("/play", data={"scenario": "peer_salvo", "seed": "1"})
    isolated_client.post("/play", data={"scenario": "peer_salvo", "seed": "2"})

    records = isolated_client.get("/engagements").json()["engagements"]
    newest, oldest = records[0]["id"], records[1]["id"]

    body = isolated_client.get("/").text
    assert "DIFF" in body
    assert f"/engagements/{newest}/diff/{oldest}" in body


def test_landing_no_diff_link_when_scenario_appears_only_once(
    isolated_client: TestClient,
) -> None:
    isolated_client.post("/play", data={"scenario": "peer_salvo", "seed": "1"})
    isolated_client.post("/play", data={"scenario": "regional_crisis", "seed": "1"})

    body = isolated_client.get("/").text
    assert 'class="muted"' in body


def test_engagement_rerun_creates_a_second_record(isolated_client: TestClient) -> None:
    isolated_client.post("/play", data={"scenario": "peer_salvo", "seed": "7"})
    original = isolated_client.get("/engagements").json()["engagements"][0]

    response = isolated_client.post(f"/engagements/{original['id']}/rerun")
    assert response.status_code == 200
    assert "AUDIT REEL" in response.text

    listing = isolated_client.get("/engagements").json()
    assert listing["count"] == 2
    # newest record matches the rerun (same scenario + seed, different id)
    newest = listing["engagements"][0]
    assert newest["scenario"] == original["scenario"]
    assert newest["seed"] == original["seed"]
    assert newest["id"] != original["id"]


def test_engagement_rerun_404_when_missing(isolated_client: TestClient) -> None:
    response = isolated_client.post("/engagements/eng_nope/rerun")
    assert response.status_code == 404


def test_landing_includes_rerun_buttons(isolated_client: TestClient) -> None:
    isolated_client.post("/play", data={"scenario": "peer_salvo", "seed": "1"})
    record = isolated_client.get("/engagements").json()["engagements"][0]

    body = isolated_client.get("/").text
    assert f'action="/engagements/{record["id"]}/rerun"' in body
    assert ">rerun</button>" in body


def test_engagement_delete_removes_record_and_log(
    isolated_client: TestClient, tmp_path: Path
) -> None:
    isolated_client.post("/play", data={"scenario": "peer_salvo", "seed": "1"})
    record = isolated_client.get("/engagements").json()["engagements"][0]
    log_path = Path(record["log_path"])
    assert log_path.exists()

    response = isolated_client.delete(f"/engagements/{record['id']}")
    assert response.status_code == 200
    payload = response.json()
    assert payload["deleted"] is True
    assert payload["log_removed"] is True

    assert isolated_client.get(f"/engagements/{record['id']}").status_code == 404
    assert not log_path.exists()


def test_engagement_delete_404_when_missing(isolated_client: TestClient) -> None:
    response = isolated_client.delete("/engagements/eng_nope")
    assert response.status_code == 404


def test_engagement_delete_keep_log_flag(isolated_client: TestClient) -> None:
    isolated_client.post("/play", data={"scenario": "peer_salvo", "seed": "1"})
    record = isolated_client.get("/engagements").json()["engagements"][0]
    log_path = Path(record["log_path"])
    assert log_path.exists()

    response = isolated_client.delete(f"/engagements/{record['id']}?delete_log=false")
    assert response.status_code == 200
    assert response.json()["log_removed"] is False
    assert log_path.exists()


def test_engagement_delete_post_form_redirects_to_landing(
    isolated_client: TestClient,
) -> None:
    isolated_client.post("/play", data={"scenario": "peer_salvo", "seed": "1"})
    record = isolated_client.get("/engagements").json()["engagements"][0]

    # follow_redirects=False so we can inspect the 303 directly.
    response = isolated_client.post(
        f"/engagements/{record['id']}/delete",
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert response.headers["location"] == "/"

    assert isolated_client.get("/engagements").json()["count"] == 0


def test_landing_includes_delete_buttons(isolated_client: TestClient) -> None:
    isolated_client.post("/play", data={"scenario": "peer_salvo", "seed": "1"})
    record = isolated_client.get("/engagements").json()["engagements"][0]

    body = isolated_client.get("/").text
    assert f'action="/engagements/{record["id"]}/delete"' in body
    assert ">delete</button>" in body
