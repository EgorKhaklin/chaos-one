"""Tests for the scenario runner and its CLI surface."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout
from pathlib import Path

from chaos_backend.audit import AuditLogReader, AuditLogVerifier
from chaos_backend.cli import main
from chaos_backend.simulation.scenario_runner import run
from chaos_backend.simulation.scenarios import ScenarioKind, build


def test_runner_writes_one_audit_entry_per_event_plus_begin_end(tmp_path: Path) -> None:
    scenario = build(ScenarioKind.PEER_SALVO, seed=11)
    log_path = tmp_path / "engagement.jsonl"

    result = run(scenario, log_path=log_path)

    entries = AuditLogReader.load(log_path)
    # begin + per-event + end
    assert len(entries) == len(scenario.events) + 2
    assert entries[0].event_type == "scenario_run_begin"
    assert entries[-1].event_type == "scenario_run_end"
    assert result.events_emitted == len(scenario.events)
    assert result.log_path == log_path


def test_runner_output_verifies(tmp_path: Path) -> None:
    scenario = build(ScenarioKind.REGIONAL_CRISIS, seed=3)
    log_path = tmp_path / "engagement.jsonl"

    run(scenario, log_path=log_path)

    entries = AuditLogReader.load(log_path)
    verification = AuditLogVerifier.verify(entries)
    assert verification.valid is True


def test_runner_preserves_event_order_and_scenario_t(tmp_path: Path) -> None:
    scenario = build(ScenarioKind.PEER_SALVO, seed=7)
    log_path = tmp_path / "engagement.jsonl"

    run(scenario, log_path=log_path)

    entries = AuditLogReader.load(log_path)
    payload_events = entries[1:-1]
    timestamps = [json.loads(e.payload_json)["scenario_t"] for e in payload_events]
    assert timestamps == sorted(timestamps)


def test_cli_play_emits_log_and_optionally_html(tmp_path: Path) -> None:
    log_path = tmp_path / "engagement.jsonl"
    html_path = tmp_path / "engagement.html"

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = main(
            [
                "play",
                "peer_salvo",
                "--seed",
                "42",
                "--output",
                str(log_path),
                "--html",
                str(html_path),
            ]
        )

    assert code == 0
    response = json.loads(buffer.getvalue())
    assert response["scenario"] == "peer_salvo"
    assert response["seed"] == 42
    assert response["html_path"] == str(html_path)
    assert log_path.exists()
    assert html_path.exists()
    assert "AUDIT REEL" in html_path.read_text(encoding="utf-8")


def test_cli_play_rejects_unknown_kind(tmp_path: Path) -> None:
    import pytest

    log_path = tmp_path / "engagement.jsonl"
    with pytest.raises(SystemExit) as exc:
        main(["play", "not_a_real_kind", "--output", str(log_path)])
    assert exc.value.code == 2
