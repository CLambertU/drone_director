"""API 公共依赖。"""

from __future__ import annotations

from fastapi import Request

from backend.services.environment_service import EnvironmentService
from core.repository import RepositoryRegistry


def get_registry(request: Request) -> RepositoryRegistry:
    return request.app.state.registry


def get_environment_service(request: Request) -> EnvironmentService:
    return request.app.state.environment
