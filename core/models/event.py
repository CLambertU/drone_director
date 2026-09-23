"""动态运行事件实体。

事件系统是“感知 → 分析 → 决策 → 执行 → 反馈”闭环的统一输入/留痕载体：
外部通过 POST /api/events 注入，仿真器消费事件并把处理结果回写记录。
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from core.models.common import new_id
from core.models.enums import EventType, Severity
from core.models.geometry import Position3D


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Event(BaseModel):
    id: str = Field(default_factory=lambda: new_id("EV"))
    type: EventType
    timestamp: datetime = Field(default_factory=_utcnow)
    location: Position3D | None = None
    severity: Severity = Severity.INFO
    description: str = ""

    related_id: str | None = None
    """关联实体 ID（如故障飞行器 ID、被关闭航路 ID）。"""

    payload: dict[str, Any] = Field(default_factory=dict)
    """事件附加参数，由对应处理器解释（如雷暴强度、备降点列表）。"""

    handled: bool = False
    """是否已被仿真引擎处理完成。"""

    simulation_time: float = Field(default=0.0, ge=0.0)
    processed_at: datetime | None = None
    processing_ms: float = Field(default=0.0, ge=0.0)
    result: dict[str, Any] = Field(default_factory=dict)
