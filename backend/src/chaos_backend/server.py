"""gRPC server entry point.

Generated stubs from `proto/chaos_one.proto` are expected under
`chaos_backend.generated`. To produce them:

    python -m grpc_tools.protoc \\
        -I proto \\
        --python_out=src/chaos_backend/generated \\
        --grpc_python_out=src/chaos_backend/generated \\
        proto/chaos_one.proto

The server can run without generated stubs in `--no-stubs` mode for
front-end smoke testing.
"""

from __future__ import annotations

import argparse
import asyncio
import importlib
import logging
import signal

import grpc  # type: ignore[import-untyped]
import structlog

logger = structlog.get_logger(__name__)


async def serve(host: str, port: int, *, with_stubs: bool) -> None:
    server = grpc.aio.server()

    if with_stubs:
        try:
            adapters = importlib.import_module("chaos_backend.grpc_adapters")
        except ImportError:
            logger.warning("generated_stubs_missing", hint="run grpc_tools.protoc")
        else:
            adapters.register_all(server)
            logger.info("services_registered")
    else:
        logger.info("running_without_stubs")

    address = f"{host}:{port}"
    server.add_insecure_port(address)
    await server.start()
    logger.info("listening", address=address)

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()

    def request_shutdown() -> None:
        logger.info("shutdown_requested")
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, request_shutdown)

    await stop_event.wait()
    await server.stop(grace=2.0)
    logger.info("server_stopped")


def main() -> None:
    parser = argparse.ArgumentParser(description="Chaos One backend gRPC server")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=50_051, type=int)
    parser.add_argument(
        "--no-stubs",
        action="store_true",
        help="Run without registering generated gRPC stubs (smoke mode)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
    )

    asyncio.run(serve(args.host, args.port, with_stubs=not args.no_stubs))


if __name__ == "__main__":
    main()
