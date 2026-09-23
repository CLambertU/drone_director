"""系统级接口：种子数据加载、数据重置、全局状态摘要。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request

from backend.api.deps import get_environment_service, get_registry
from backend.services.demo_service import seed_demo
from backend.services.environment_service import EnvironmentService
from core.repository import RepositoryRegistry
from backend.exceptions import AppError

router = APIRouter(prefix="/api/system", tags=["system"])


@router.get("/summary", summary="获取各实体数量摘要")
def summary(registry: RepositoryRegistry = Depends(get_registry)) -> dict:
    with registry.lock:
        return {name: repo.count() for name, repo in registry.all_repos().items()}


@router.post("/seed", summary="加载内置 Demo 种子数据（会清空当前数据并重建城市/航路网）")
def seed(
    request: Request,
    registry: RepositoryRegistry = Depends(get_registry),
    environment: EnvironmentService = Depends(get_environment_service),
) -> dict:
    with registry.lock:
        engine = getattr(request.app.state, "engine", None)
        if engine is not None and engine.running:
            raise AppError(409, "simulation_running", "请先暂停再加载场景")
        result = seed_demo(registry, environment)
        if engine is not None:
            engine.reset_runtime()
        return result


@router.post("/reset", summary="清空全部运行数据（含城市环境与航路网）")
def reset(
    request: Request,
    registry: RepositoryRegistry = Depends(get_registry),
    environment: EnvironmentService = Depends(get_environment_service),
) -> dict:
    with registry.lock:
        engine = getattr(request.app.state, "engine", None)
        if engine is not None and engine.running:
            raise AppError(409, "simulation_running", "请先暂停再清空场景")
        registry.reset()
        environment.install_from(EnvironmentService())
        if engine is not None:
            engine.reset_runtime()
    return {"reset": True}
