"""动态事件接口。

POST /api/events 即“动态注入事件”入口（第六阶段起由仿真引擎消费处理：
更新天气/管制 -> 重算航路代价 -> 受影响飞行器重规划 -> 记录处理结果）。
"""

from backend.api._crud import build_crud_router
from core.models import Event

router = build_crud_router(
    prefix="/api/events",
    tag="events",
    model_type=Event,
    repo_attr="events",
    resource_name="事件",
)
