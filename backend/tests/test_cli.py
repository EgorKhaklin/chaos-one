"""Smoke tests for the chaos-backend CLI."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stdout

from chaos_backend.cli import main


def _run(*args: str) -> dict[str, object]:
    buffer = io.StringIO()
    with redirect_stdout(buffer):
        code = main(list(args))
    assert code == 0, f"cli exited non-zero: {code}"
    return json.loads(buffer.getvalue())


def test_scenario_emits_event_list() -> None:
    payload = _run("scenario", "peer_salvo", "--seed", "42")
    assert payload["kind"] == "peer_salvo"
    assert payload["event_count"] > 0
    assert isinstance(payload["events"], list)


def test_classify_returns_consensus_class() -> None:
    payload = _run("classify", "--track-id", "TRK-001", "--sample-count", "1")
    assert payload["track_id"] == "TRK-001"
    assert "consensus_class" in payload
    assert 0.0 <= float(payload["calibrated_confidence"]) <= 1.0


def test_generate_coa_returns_three_options() -> None:
    payload = _run("generate-coa", "--tracks", "A", "B", "C", "--envelope", "ROE-2")
    assert payload["recommended_id"] == "COA-B"
    assert len(payload["coa"]) == 3


def test_playbook_emits_weighted_hypotheses() -> None:
    payload = _run("playbook")
    weights = [h["weight"] for h in payload["hypotheses"]]
    assert all(0.0 <= w <= 1.0 for w in weights)


def test_trajectory_runs_and_falls() -> None:
    payload = _run("trajectory", "--apogee", "30000", "--duration", "30", "--dt", "0.5")
    assert payload["sample_count"] > 1
    assert payload["initial_altitude_m"] >= payload["final_altitude_m"]
