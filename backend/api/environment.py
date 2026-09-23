"""城市环境与航路网络接口（第二阶段）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from backend.api.deps import get_environment_service, get_registry
from backend.services.environment_service import EnvironmentService
from core.repository import RepositoryRegistry
from simulation.environment.route_network import RouteNetwork

router = APIRouter(prefix="/api/environment", tags=["environment"])


class GenerateNetworkRequest(BaseModel):
    neighbor_count: int = Field(default=3, ge=1, le=12)
    max_distance: float | None = Field(default=None, gt=0, allow_inf_nan=False)
    capacity: int = Field(default=20, ge=1, le=1000)


def _require_city(environment: EnvironmentService):
    if environment.city is None:
        raise HTTPException(
            status_code=409,
            detail="城市环境尚未构建，请先 POST /api/system/seed 加载 Demo 数据",
        )
    return environment.city


def _require_network(environment: EnvironmentService):
    if environment.network is None:
        raise HTTPException(
            status_code=409,
            detail="航路网络尚未构建，请先 POST /api/system/seed 加载 Demo 数据",
        )
    return environment.network


@router.get("/summary", summary="城市环境摘要（边界/建筑/栅格占用）")
def environment_summary(
    environment: EnvironmentService = Depends(get_environment_service),
) -> dict:
    city = _require_city(environment)
    return city.summary()


@router.get("/buildings", summary="全部建筑列表")
def list_buildings(
    environment: EnvironmentService = Depends(get_environment_service),
) -> list[dict]:
    city = _require_city(environment)
    return [b.model_dump() for b in city.buildings]


@router.get("/route-network", summary="航路有向图（节点与航段，供三维可视化）")
def route_network(
    environment: EnvironmentService = Depends(get_environment_service),
) -> dict:
    network = _require_network(environment)
    return network.to_dict()


@router.get("/validation", summary="航路段与建筑的碰撞校验结果")
def validate_network(
    environment: EnvironmentService = Depends(get_environment_service),
) -> dict:
    city = _require_city(environment)
    network = _require_network(environment)
    violations = network.validate_against_city(city)
    return {"blocking_segment_count": len(violations), "violations": violations}


@router.post("/rebuild", summary="按当前仓储实体重建城市环境与航路网络")
def rebuild(
    request: Request,
    registry: RepositoryRegistry = Depends(get_registry),
    environment: EnvironmentService = Depends(get_environment_service),
) -> dict:
    if environment.city_config is None:
        raise HTTPException(
            status_code=409,
            detail="尚未加载城市配置，请先 POST /api/system/seed",
        )
    with registry.lock:
        engine = getattr(request.app.state, "engine", None)
        if engine is not None and engine.running:
            raise HTTPException(409, "请先暂停再重建网络")
        result = environment.rebuild_all(registry)
        if engine is not None:
            engine.sync_entities()
            engine.checkpoint()
        return result


@router.post("/generate-network", summary="根据航点、建筑和激活管制区生成安全邻接航段")
def generate_network(
    payload: GenerateNetworkRequest,
    request: Request,
    registry: RepositoryRegistry = Depends(get_registry),
    environment: EnvironmentService = Depends(get_environment_service),
) -> dict:
    with registry.lock:
        engine = getattr(request.app.state, "engine", None)
        if engine is not None and engine.running:
            raise HTTPException(409, "请先暂停再生成网络")
        city = _require_city(environment)
        generated = RouteNetwork.generate_routes(
            registry.waypoints.list(), city, registry.restrictions.list(),
            **payload.model_dump(),
        )
        with registry.transaction():
            for route in generated:
                registry.routes.upsert(route)
            network = RouteNetwork.build(registry.waypoints.list(), registry.routes.list())
        environment.network = network
        environment.version += 1
        if engine is not None:
            engine.sync_entities()
            engine.checkpoint()
        return {
            "generated_routes": len(generated),
            "nodes": network.graph.number_of_nodes(),
            "edges": network.graph.number_of_edges(),
            "isolated_waypoints": [n for n, degree in network.graph.degree if degree == 0],
        }
