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
