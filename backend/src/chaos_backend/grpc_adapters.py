"""Thin gRPC servicer adapters.

Keeps the service implementations in `chaos_backend.services` decoupled
from protobuf so they remain straightforward to unit test. The adapters
in this module translate between proto messages and the internal
dataclasses, and inherit from the generated servicer base classes.

Generated stubs are produced from `proto/chaos_one.proto` via
`scripts/generate_protos.sh` or `make protos` and live under
`chaos_backend.generated`. Import is dynamic so the module can be loaded
even when stubs have not been regenerated yet (the adapters simply
become unimportable in that state).
"""

from __future__ import annotations

import importlib
from collections.abc import AsyncIterator
from typing import Any

import grpc  # type: ignore[import-untyped]

from chaos_backend.services.adversary_model import AdversaryModelService
from chaos_backend.services.coa_generator import CourseOfActionService
from chaos_backend.services.discrimination import DiscriminationService

_pb2 = importlib.import_module("chaos_backend.generated.chaos_one_pb2")
_pb2_grpc = importlib.import_module("chaos_backend.generated.chaos_one_pb2_grpc")


_CLASS_LABEL_TO_ENUM = {
    "HGV": _pb2.THREAT_CLASS_HGV,
    "MARV": _pb2.THREAT_CLASS_MARV,
    "BALLISTIC_RV": _pb2.THREAT_CLASS_BALLISTIC_RV,
    "CRUISE_MISSILE": _pb2.THREAT_CLASS_CRUISE_MISSILE,
    "UAS": _pb2.THREAT_CLASS_UAS,
    "DECOY": _pb2.THREAT_CLASS_DECOY,
    "DEBRIS": _pb2.THREAT_CLASS_DEBRIS,
}


def _class_to_enum(label: str) -> int:
    return int(_CLASS_LABEL_TO_ENUM.get(label, _pb2.THREAT_CLASS_UNSPECIFIED))


class DiscriminationAdapter:
    """Duck-typed gRPC servicer. grpcio's add_*ServicerToServer dispatches
    by method name, so inheritance from the generated base class is not
    required and would force a mypy/runtime dependency on the stubs."""

    def __init__(self, service: DiscriminationService) -> None:
        self._service = service

    def Classify(self, request: Any, context: Any) -> Any:  # noqa: N802
        observation = request.observation
        result = self._service.classify(
            track_id=observation.track_id,
            sample_count=max(1, len(request.history)),
            observed_speed_mps=None,
            observed_altitude_m=None,
        )
        return _pb2.ClassifyResponse(
            track_id=result.track_id,
            votes=[
                _pb2.EnsembleVote(
                    model_id=vote.model_id,
                    predicted=_class_to_enum(vote.predicted_class),
                    weight=vote.weight,
                )
                for vote in result.votes
            ],
            calibrated_confidence=result.calibrated_confidence,
            certified_radius_l2=result.certified_radius_l2,
        )

    async def StreamUpdates(  # noqa: N802
        self,
        request_iterator: AsyncIterator[Any],
        context: Any,
    ) -> AsyncIterator[Any]:
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details("StreamUpdates lands in milestone 3+")
        for _ in ():
            yield _


class CourseOfActionAdapter:
    def __init__(self, service: CourseOfActionService) -> None:
        self._service = service

    def Generate(self, request: Any, context: Any) -> Any:  # noqa: N802
        track_ids = [classification.track_id for classification in request.classifications]
        bundle = self._service.generate(
            classified_track_ids=track_ids,
            roe_envelope_id=request.roe_envelope_id,
        )
        return _pb2.COAResponse(
            recommended_id=bundle.recommended_id,
            coa=[
                _pb2.CourseOfActionItem(
                    id=item.id,
                    headline=item.headline,
                    description=item.description,
                    expected_leakage=_pb2.OutcomeBand(
                        point=item.expected_leakage.point,
                        low=item.expected_leakage.low,
                        high=item.expected_leakage.high,
                    ),
                    cost=_pb2.MagazineDelta(
                        ngi=item.cost.ngi,
                        sm3=item.cost.sm3,
                        sm6=item.cost.sm6,
                        pac3=item.cost.pac3,
                        hel_megajoules=item.cost.hel_megajoules,
                    ),
                    escalation=_pb2.EscalationScore(
                        level=item.escalation_level,
                        numeric=0.0,
                    ),
                    releasability=item.releasability,
                    countdown_seconds=item.countdown_seconds,
                )
                for item in bundle.items
            ],
        )


class AdversaryModelAdapter:
    def __init__(self, service: AdversaryModelService) -> None:
        self._service = service

    def CurrentPlaybook(self, request: Any, context: Any) -> Any:  # noqa: N802
        _ = request
        distribution = self._service.current()
        return _pb2.PlaybookDistribution(
            hypotheses=[
                _pb2.PlaybookHypothesis(
                    playbook_id=h.playbook_id,
                    display_name=h.display_name,
                    weight=h.weight,
                    delta_30s=h.delta_30s,
                )
                for h in distribution.hypotheses
            ],
            cost_imposition_index=distribution.cost_imposition_index,
        )

    async def StreamPlaybook(  # noqa: N802
        self,
        request: Any,
        context: Any,
    ) -> AsyncIterator[Any]:
        context.set_code(grpc.StatusCode.UNIMPLEMENTED)
        context.set_details("StreamPlaybook lands in milestone 3+")
        for _ in ():
            yield _


def register_all(server: Any) -> None:
    """Construct adapters around fresh service instances and bind them
    to the given gRPC server. Idempotent for a single server instance."""
    _pb2_grpc.add_DiscriminationServicer_to_server(
        DiscriminationAdapter(DiscriminationService()), server
    )
    _pb2_grpc.add_CourseOfActionServicer_to_server(
        CourseOfActionAdapter(CourseOfActionService()), server
    )
    _pb2_grpc.add_AdversaryModelServicer_to_server(
        AdversaryModelAdapter(AdversaryModelService()), server
    )
