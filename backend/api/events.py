"""动态事件接口。

POST /api/events 即“动态注入事件”入口（第六阶段起由仿真引擎消费处理：
更新天气/管制 -> 重算航路代价 -> 受影响飞行器重规划 -> 记录处理结果）。
"""

from backend.api._crud import build_crud_router
from backend.api.simulation import get_engine
from backend.exceptions import AppError
from backend.models import EventInput
from fastapi import Depends
from core.models import Event

router = build_crud_router(
    prefix="/api/events",
    tag="events",
    model_type=Event,
    repo_attr="events",
    resource_name="事件",
    allow_create=False,
)


@router.post("", response_model=Event, status_code=201, summary="注入事件并执行约束更新、重规划与结果记录")
def inject(payload: EventInput, engine=Depends(get_engine)):
    values = payload.model_dump()
    if values.get("id") is None:
        values.pop("id", None)
    try:
        return engine.inject_event(Event.model_validate(values))
    except KeyError as exc:
        raise AppError(404, "not_found", str(exc)) from exc
    except ValueError as exc:
        raise AppError(422, "invalid_event", str(exc)) from exc
    except RuntimeError as exc:
        raise AppError(409, "environment_not_ready", str(exc)) from exc
