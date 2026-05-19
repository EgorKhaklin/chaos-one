"""Double-click launcher.

Boots the FastAPI dashboard, waits for /health to return 200, opens the
browser, and stays in the foreground until killed. The PyInstaller spec
in `backend/chaos-one.spec` packages this entrypoint together with all
dependencies into a single binary, so the whole Python side of Chaos
One launches from one icon.
"""

from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path


def _wait_for_port(host: str, port: int, *, timeout_s: float = 30.0) -> bool:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.4):
                return True
        except OSError:
            time.sleep(0.15)
    return False


def _resolve_default_storage() -> Path:
    """Pick a sensible per-user place for the SQLite catalog and audit logs.

    When running as a PyInstaller bundle, ~/.chaos-one is still the right
    answer on macOS/Linux. On Windows, %LOCALAPPDATA% is more native.
    """
    if sys.platform.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or os.environ.get("APPDATA")
        if base:
            return Path(base) / "chaos-one"
    return Path.home() / ".chaos-one"


def _resolve_unity_app(explicit: str | None) -> Path | None:
    """Find the Unity build binary, if any.

    Resolution order:
      1. --unity-app argument on the CLI.
      2. CHAOS_UNITY_APP environment variable.
      3. A sibling `unity-build/` directory next to the chaos-one binary
         containing a *.app (macOS), *.exe (Windows), or executable
         binary (Linux).

    Returns None when no Unity build is present; the launcher runs
    backend-only in that case.
    """
    candidates: list[Path] = []
    if explicit:
        candidates.append(Path(explicit))
    env = os.environ.get("CHAOS_UNITY_APP")
    if env:
        candidates.append(Path(env))

    sibling = _executable_directory() / "unity-build"
    if sibling.is_dir():
        for entry in sorted(sibling.iterdir()):
            if entry.suffix == ".app" or entry.suffix == ".exe":
                candidates.append(entry)
            elif entry.is_file() and os.access(entry, os.X_OK):
                candidates.append(entry)

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _executable_directory() -> Path:
    """Directory containing the running binary (PyInstaller-aware)."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def _spawn_unity(unity_app: Path) -> subprocess.Popen[bytes] | None:
    """Launch the Unity build as a child process.

    macOS .app bundles use `open -W -a`; everything else just executes
    the binary directly. Returns the Popen handle so the caller can
    terminate the child on shutdown.
    """
    print(f"[launcher] starting Unity build: {unity_app}", file=sys.stderr)
    try:
        if unity_app.suffix == ".app" and sys.platform == "darwin":
            return subprocess.Popen(["open", "-n", "-a", str(unity_app)])
        return subprocess.Popen([str(unity_app)])
    except OSError as exc:
        print(f"[launcher] failed to spawn Unity build: {exc}", file=sys.stderr)
        return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="chaos-one",
        description="Launch the Chaos One backend dashboard and open the browser.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true", help="don't open the browser")
    parser.add_argument(
        "--unity-app",
        default=None,
        help="path to a Unity build to launch alongside the backend",
    )
    parser.add_argument(
        "--no-unity",
        action="store_true",
        help="ignore any auto-discovered Unity build",
    )
    args = parser.parse_args(argv)

    storage = _resolve_default_storage()
    storage.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("CHAOS_DB_PATH", str(storage / "engagements.db"))
    os.environ.setdefault("CHAOS_LOG_DIR", str(storage / "audit"))

    # Import here so PyInstaller's analyzer follows the chain from the
    # entrypoint instead of attempting it at module-load time.
    import uvicorn

    from chaos_backend.web import app

    unity_app = None if args.no_unity else _resolve_unity_app(args.unity_app)
    unity_process: subprocess.Popen[bytes] | None = None

    def on_ready() -> None:
        nonlocal unity_process
        if not _wait_for_port(args.host, args.port):
            print(
                f"[launcher] server did not bind on {args.host}:{args.port} in time; "
                "skipping browser + Unity spawn",
                file=sys.stderr,
            )
            return
        if not args.no_browser:
            url = f"http://{args.host}:{args.port}/"
            print(f"[launcher] opening {url}", file=sys.stderr)
            webbrowser.open(url)
        if unity_app is not None:
            unity_process = _spawn_unity(unity_app)

    threading.Thread(target=on_ready, daemon=True).start()

    print(
        f"[launcher] storage: {storage}\n"
        f"[launcher] starting Chaos One on http://{args.host}:{args.port}/",
        file=sys.stderr,
    )

    if unity_app is not None:
        print(
            f"[launcher] will spawn Unity build once backend is healthy: {unity_app}",
            file=sys.stderr,
        )
    elif not args.no_unity:
        print(
            "[launcher] no Unity build found (set CHAOS_UNITY_APP or drop one into unity-build/)",
            file=sys.stderr,
        )

    config = uvicorn.Config(
        app,
        host=args.host,
        port=args.port,
        log_level="info",
        access_log=False,  # the middleware emits structured access lines
    )
    server = uvicorn.Server(config)
    try:
        server.run()
    finally:
        if unity_process is not None and unity_process.poll() is None:
            print("[launcher] terminating Unity child process", file=sys.stderr)
            try:
                unity_process.terminate()
                unity_process.wait(timeout=3.0)
            except (OSError, subprocess.TimeoutExpired):
                unity_process.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
