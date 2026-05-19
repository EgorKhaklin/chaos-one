"""Tests for the chaos-one launcher entrypoint."""

from __future__ import annotations

import socket
from pathlib import Path

from chaos_backend.launcher import _resolve_default_storage, _wait_for_port


def test_resolve_default_storage_returns_writable_path(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.delenv("APPDATA", raising=False)

    storage = _resolve_default_storage()
    assert storage.name == ".chaos-one"
    assert storage.parent == tmp_path


def test_wait_for_port_returns_true_when_listener_is_up() -> None:
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(1)
    try:
        port = listener.getsockname()[1]
        assert _wait_for_port("127.0.0.1", port, timeout_s=2.0) is True
    finally:
        listener.close()


def test_wait_for_port_returns_false_when_nothing_listens() -> None:
    # Bind to a port and close immediately so it's almost certainly free.
    probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    probe.bind(("127.0.0.1", 0))
    free_port = probe.getsockname()[1]
    probe.close()

    assert _wait_for_port("127.0.0.1", free_port, timeout_s=0.6) is False


def test_resolve_unity_app_prefers_explicit_argument(tmp_path: Path) -> None:
    from chaos_backend.launcher import _resolve_unity_app

    fake_app = tmp_path / "MyUnity.app"
    fake_app.mkdir()  # macOS .app bundles are directories

    assert _resolve_unity_app(str(fake_app)) == fake_app


def test_resolve_unity_app_falls_back_to_environment(tmp_path: Path, monkeypatch) -> None:
    from chaos_backend.launcher import _resolve_unity_app

    fake_app = tmp_path / "MyUnity.app"
    fake_app.mkdir()

    monkeypatch.setenv("CHAOS_UNITY_APP", str(fake_app))
    assert _resolve_unity_app(None) == fake_app


def test_resolve_unity_app_returns_none_when_nothing_present(tmp_path: Path, monkeypatch) -> None:
    from chaos_backend.launcher import _resolve_unity_app

    monkeypatch.delenv("CHAOS_UNITY_APP", raising=False)
    monkeypatch.setattr(
        "chaos_backend.launcher._executable_directory",
        lambda: tmp_path,
    )

    assert _resolve_unity_app(None) is None


def test_resolve_unity_app_auto_discovers_sibling_app(tmp_path: Path, monkeypatch) -> None:
    from chaos_backend.launcher import _resolve_unity_app

    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    unity_dir = bin_dir / "unity-build"
    unity_dir.mkdir()
    bundled = unity_dir / "ChaosOne.app"
    bundled.mkdir()

    monkeypatch.delenv("CHAOS_UNITY_APP", raising=False)
    monkeypatch.setattr(
        "chaos_backend.launcher._executable_directory",
        lambda: bin_dir,
    )

    assert _resolve_unity_app(None) == bundled
