"""Double-click launcher.

Boots the FastAPI dashboard, waits for /health to return 200, opens the
browser to /battlespace, and stays in the foreground until killed. The
PyInstaller spec in `backend/chaos-one.spec` packages this entrypoint
together with all dependencies into a single binary so Chaos One
launches from one icon.
"""

from __future__ import annotations

import argparse
import os
import socket
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="chaos-one",
        description="Launch the Chaos One backend dashboard and open the browser.",
    )
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true", help="don't open the browser")
    args = parser.parse_args(argv)

    storage = _resolve_default_storage()
    storage.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("CHAOS_DB_PATH", str(storage / "engagements.db"))
    os.environ.setdefault("CHAOS_LOG_DIR", str(storage / "audit"))

    # Import here so PyInstaller's analyzer follows the chain from the
    # entrypoint instead of attempting it at module-load time.
    import uvicorn

    from chaos_backend.web import app

    def on_ready() -> None:
        if not _wait_for_port(args.host, args.port):
            print(
                f"[launcher] server did not bind on {args.host}:{args.port} in time; "
                "skipping browser open",
                file=sys.stderr,
            )
            return
        if not args.no_browser:
            url = f"http://{args.host}:{args.port}/battlespace"
            print(f"[launcher] opening {url}", file=sys.stderr)
            webbrowser.open(url)

    threading.Thread(target=on_ready, daemon=True).start()

    print(
        f"[launcher] storage: {storage}\n"
        f"[launcher] starting Chaos One on http://{args.host}:{args.port}/",
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
    server.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
