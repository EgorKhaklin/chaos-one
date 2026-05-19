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


def test_demo_runs_full_engagement() -> None:
    payload = _run("demo", "--scenario", "peer_salvo", "--seed", "7", "--tracks", "3")
    assert payload["scenario"]["kind"] == "peer_salvo"
    assert payload["discrimination"]["track_count"] == 3
    assert payload["course_of_action"]["recommended_id"] == "COA-B"
    assert len(payload["course_of_action"]["options"]) == 3
    assert "cost_imposition_index" in payload["adversary"]
    assert payload["kinematics"]["sample_count"] > 1


def test_demo_runs_against_ambiguous_launch() -> None:
    payload = _run("demo", "--scenario", "ambiguous_launch", "--seed", "5", "--tracks", "1")
    assert payload["scenario"]["kind"] == "ambiguous_launch"
    assert payload["discrimination"]["track_count"] == 1


def test_main_without_subcommand_returns_help() -> None:
    # argparse with required=True on subparsers raises SystemExit(2) on
    # missing subcommand; verifying the exit code keeps that behavior
    # locked in.
    import pytest

    from chaos_backend.cli import main

    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2


def test_scenario_unknown_kind_emits_stderr_and_returns_2() -> None:
    # argparse rejects unknown choices before our handler runs; this
    # exercises the SystemExit path with the choice validator.
    import pytest

    from chaos_backend.cli import main

    with pytest.raises(SystemExit) as exc:
        main(["scenario", "not_a_real_kind"])
    assert exc.value.code == 2


def test_json_default_falls_back_for_unknown_types() -> None:
    from chaos_backend.cli import _json_default

    class HasDict:
        def __init__(self) -> None:
            self.field = "value"

    class StrFallback:
        __slots__ = ()

        def __repr__(self) -> str:
            return "<stringified>"

    assert _json_default(HasDict()) == {"field": "value"}
    assert _json_default(StrFallback()) == "<stringified>"


def test_emit_writes_newline_terminated_json() -> None:
    import io
    from contextlib import redirect_stdout

    from chaos_backend.cli import _emit

    buffer = io.StringIO()
    with redirect_stdout(buffer):
        _emit({"k": "v"})

    output = buffer.getvalue()
    assert output.endswith("\n")
    assert '"k": "v"' in output
