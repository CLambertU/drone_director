"""FastAPI 应用工厂与 ASGI 入口。

启动方式：
    # 方式一：uvicorn 命令
    uvicorn backend.app:app --host 127.0.0.1 --port 8011 --reload
    # 方式二：直接运行本文件（端口读取 TS_HOST / TS_PORT，默认 8011）
    python -m backend.app
文档：
    http://127.0.0.1:8011/docs
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend import __version__
from backend.api.router import api_router
from backend.config import settings
from backend.exceptions import register_exception_handlers
from backend.logging_config import configure_logging, get_logger
from backend.services.demo_service import seed_demo
from backend.services.environment_service import EnvironmentService
from core.repository import create_registry
from core.models import Building, CityConfig

logger = get_logger(__name__)


def create_app(
    seed_on_startup: bool | None = None,
    database_path: str | Path | None = settings.database_path,
) -> FastAPI:
    configure_logging(settings.log_level)
    should_seed = (
        settings.seed_on_startup if seed_on_startup is None else seed_on_startup
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        try:
            if should_seed:
                result = seed_demo(app.state.registry, app.state.environment)
                logger.info("启动时加载种子数据: %s", result)
            else:
                saved = app.state.registry.get_metadata("environment")
                if saved:
                    app.state.environment.apply_seed(
                        CityConfig.model_validate(saved["city_config"]),
                        [Building.model_validate(b) for b in saved["buildings"]],
                        app.state.registry,
                    )
            logger.info("%s 启动完成 (env=%s, http://%s:%d)",
                        settings.app_name, settings.environment, settings.host, settings.port)
            yield
        finally:
            app.state.registry.close()
            logger.info("应用关闭")

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=(
            "城市低空交通智能规划与自主协同系统后端 API。\n\n"
            "交互式文档：[/docs](/docs)；健康检查：[/api/health](/api/health)。"
        ),
        lifespan=lifespan,
    )

    app.state.registry = create_registry(database_path=database_path)
    app.state.environment = EnvironmentService()
    app.state.settings = settings

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    @app.middleware("http")
    async def trace_request(request, call_next):
        request_id = uuid4().hex
        request.state.request_id = request_id
        started = perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logger.debug("request=%s %s %s status=%d elapsed_ms=%.1f", request_id,
                     request.method, request.url.path, response.status_code,
                     (perf_counter() - started) * 1000)
        return response

    app.include_router(api_router)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host=settings.host, port=settings.port, log_level=settings.log_level.lower())
