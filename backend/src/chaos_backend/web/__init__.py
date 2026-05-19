"""FastAPI dashboard that hosts the HTML audit viewer.

A small web surface that lets a reviewer pick a scenario, play it
through the audit pipeline, and read the resulting hash-chained log
in a browser without installing Unity or running the gRPC server.

Install with `pip install -e ".[web]"` (or `[dev]`) and run with
`chaos-backend-cli web` or `uvicorn chaos_backend.web:app`.
"""

from chaos_backend.web.app import app, build_app

__all__ = ["app", "build_app"]
