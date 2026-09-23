"""Explainable planning over a consistent environment snapshot."""

from copy import deepcopy
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field

from algorithms.path_planning import CostWeights, PlanningContext, PlanningError, PlanningResult, plan_path
from backend.api.deps import get_environment_service, get_registry
from backend.exceptions import AppError
from backend.services.environment_service import EnvironmentService
from core.repository import RepositoryRegistry

router = APIRouter(prefix="/api/planning", tags=["planning"])


class PlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    source: str = Field(min_length=1)
    target: str = Field(min_length=1)
    dimension: Literal["2d", "3d"] = "3d"
    speed_mps: float = Field(default=15, gt=0, le=100)
    max_distance_m: float | None = Field(default=None, ge=0)
    respect_capacity: bool = True
    weights: CostWeights | None = None
    blocked_edges: list[tuple[str, str]] = Field(default_factory=list)


class PlanResponse(PlanningResult):
    environment_version: int


@router.post("/path", response_model=PlanResponse, summary="A* 多项加权规划与约束解释")
def plan(
    payload: PlanRequest, request: Request,
    registry: RepositoryRegistry = Depends(get_registry),
    environment: EnvironmentService = Depends(get_environment_service),
) -> PlanResponse:
    with registry.lock:
        if not environment.is_ready():
            raise AppError(409, "environment_not_ready", "请先加载城市环境")
        graph = deepcopy(environment.network.graph)
        if payload.dimension == "2d" and payload.source in graph:
            altitude = graph.nodes[payload.source]["position"].z
            graph.remove_nodes_from([n for n, d in graph.nodes(data=True)
                                     if abs(d["position"].z - altitude) > 1e-6])
        context = PlanningContext(
            graph=graph, city=environment.city,
            restrictions=registry.restrictions.list(), weather=registry.weather.list(),
            speed_mps=payload.speed_mps, max_distance_m=payload.max_distance_m,
            respect_capacity=payload.respect_capacity, blocked_edges=set(payload.blocked_edges),
        )
        version = environment.version
    weights = payload.weights or CostWeights(**{
        key: getattr(request.app.state.settings, f"cost_weight_{key}")
        for key in CostWeights.model_fields
    })
    try:
        result = plan_path(payload.source, payload.target, context, weights)
    except PlanningError as exc:
        raise AppError(422, exc.reason, str(exc), exc.details) from exc
    return PlanResponse(**result.model_dump(), environment_version=version)
