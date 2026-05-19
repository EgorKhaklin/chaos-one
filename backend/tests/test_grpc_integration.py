"""End-to-end gRPC integration test.

Boots an in-process server bound to a random localhost port, registers
the three adapters against the real services, and exercises one RPC per
service. The point is to prove the wire works, not to validate every
field value.

Marked to skip cleanly if the generated stubs are absent — local
developers who haven't run `make protos` can still run the rest of the
suite.
"""

from __future__ import annotations

import asyncio
import importlib
from collections.abc import AsyncIterator

import grpc
import pytest


def _stubs_available() -> bool:
    try:
        importlib.import_module("chaos_backend.generated.chaos_one_pb2_grpc")
    except ImportError:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _stubs_available(),
    reason="generated gRPC stubs not present; run `make protos`",
)


@pytest.fixture
async def grpc_server() -> AsyncIterator[str]:
    pb2_grpc = importlib.import_module("chaos_backend.generated.chaos_one_pb2_grpc")
    adapters = importlib.import_module("chaos_backend.grpc_adapters")
    _ = pb2_grpc  # imported for side effects + future use

    server = grpc.aio.server()
    port = server.add_insecure_port("127.0.0.1:0")
    adapters.register_all(server)
    await server.start()

    try:
        yield f"127.0.0.1:{port}"
    finally:
        await server.stop(grace=0.5)


@pytest.mark.asyncio
async def test_classify_round_trip(grpc_server: str) -> None:
    pb2 = importlib.import_module("chaos_backend.generated.chaos_one_pb2")
    pb2_grpc = importlib.import_module("chaos_backend.generated.chaos_one_pb2_grpc")

    async with grpc.aio.insecure_channel(grpc_server) as channel:
        stub = pb2_grpc.DiscriminationStub(channel)

        observation = pb2.TrackObservation(
            track_id="TRK-WIRE-001",
            position_m=pb2.Vec3(x=0.0, y=30_000.0, z=0.0),
            velocity_mps=pb2.Vec3(x=2_400.0, y=-30.0, z=0.0),
        )
        request = pb2.ClassifyRequest(observation=observation)
        response = await stub.Classify(request, timeout=5.0)

        assert response.track_id == "TRK-WIRE-001"
        assert len(response.votes) == 4
        assert 0.0 <= response.calibrated_confidence <= 1.0


@pytest.mark.asyncio
async def test_generate_coa_round_trip(grpc_server: str) -> None:
    pb2 = importlib.import_module("chaos_backend.generated.chaos_one_pb2")
    pb2_grpc = importlib.import_module("chaos_backend.generated.chaos_one_pb2_grpc")

    async with grpc.aio.insecure_channel(grpc_server) as channel:
        stub = pb2_grpc.CourseOfActionStub(channel)

        classifications = [
            pb2.ClassifyResponse(track_id="A"),
            pb2.ClassifyResponse(track_id="B"),
            pb2.ClassifyResponse(track_id="C"),
            pb2.ClassifyResponse(track_id="D"),
        ]
        request = pb2.COARequest(classifications=classifications, roe_envelope_id="ROE-2")
        response = await stub.Generate(request, timeout=5.0)

        assert response.recommended_id == "COA-B"
        assert len(response.coa) == 3


@pytest.mark.asyncio
async def test_current_playbook_round_trip(grpc_server: str) -> None:
    pb2 = importlib.import_module("chaos_backend.generated.chaos_one_pb2")
    pb2_grpc = importlib.import_module("chaos_backend.generated.chaos_one_pb2_grpc")

    async with grpc.aio.insecure_channel(grpc_server) as channel:
        stub = pb2_grpc.AdversaryModelStub(channel)

        response = await stub.CurrentPlaybook(pb2.AdversaryQuery(), timeout=5.0)

        assert len(response.hypotheses) == 3
        weights = sum(h.weight for h in response.hypotheses)
        assert 0.98 <= weights <= 1.02


@pytest.mark.asyncio
async def test_server_shutdown_is_clean() -> None:
    """Boot a server outside the fixture and verify graceful shutdown."""
    pb2_grpc = importlib.import_module("chaos_backend.generated.chaos_one_pb2_grpc")
    adapters = importlib.import_module("chaos_backend.grpc_adapters")
    _ = pb2_grpc

    server = grpc.aio.server()
    server.add_insecure_port("127.0.0.1:0")
    adapters.register_all(server)
    await server.start()

    await asyncio.wait_for(server.stop(grace=0.1), timeout=2.0)
