"""实体 CRUD 路由工厂。

各类实体的列表/详情/创建/更新/删除行为完全一致，统一由此工厂生成，
保证响应格式、错误码一致；实体特有的动作（如调度、事件注入）在各自路由中扩展。

注意：FastAPI 依赖参数注解的具体类型识别请求体，泛型 TypeVar 会被误判为
query 参数，因此在注册路由前把端点的 payload 注解替换为具体模型类。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response

from backend.api.deps import get_environment_service, get_registry
from backend.exceptions import NotFoundError
from backend.models import INPUT_MODELS
from backend.services.entity_service import EntityService
from backend.services.environment_service import EnvironmentService
from core.repository import RepositoryRegistry


def build_crud_router(
    *,
    prefix: str,
    tag: str,
    model_type: type,
    repo_attr: str,
    resource_name: str,
) -> APIRouter:
    router = APIRouter(prefix=prefix, tags=[tag])

    def _repo(registry: RepositoryRegistry = Depends(get_registry)):
        return getattr(registry, repo_attr)

    def _service(
        registry: RepositoryRegistry = Depends(get_registry),
        environment: EnvironmentService = Depends(get_environment_service),
    ):
        return EntityService(registry, environment)

    def list_items(repo=Depends(_repo)):
        return repo.list()

    def create_item(payload, service=Depends(_service)):
        return service.write(repo_attr, model_type, payload)

    def get_item(item_id: str, repo=Depends(_repo)):
        try:
            return repo.get(item_id)
        except KeyError:
            raise NotFoundError(resource_name, item_id)

    def update_item(item_id: str, payload, service=Depends(_service)):
        return service.write(repo_attr, model_type, payload, item_id)

    def delete_item(item_id: str, service=Depends(_service)) -> Response:
        service.delete(repo_attr, item_id)
        return Response(status_code=204)

    # 将请求体参数注解绑定为具体模型类，使 FastAPI 正确按 JSON body 解析
    create_item.__annotations__["payload"] = INPUT_MODELS[repo_attr]
    update_item.__annotations__["payload"] = INPUT_MODELS[repo_attr]

    router.get(
        "",
        response_model=list[model_type],
        summary=f"获取{resource_name}列表",
    )(list_items)
    router.post(
        "",
        response_model=model_type,
        status_code=201,
        summary=f"创建{resource_name}",
    )(create_item)
    router.get(
        "/{item_id}",
        response_model=model_type,
        summary=f"获取单个{resource_name}",
    )(get_item)
    router.put(
        "/{item_id}",
        response_model=model_type,
        summary=f"更新{resource_name}",
    )(update_item)
    router.delete(
        "/{item_id}",
        status_code=204,
        summary=f"删除{resource_name}",
    )(delete_item)

    return router
