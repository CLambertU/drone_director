"""气象状态实体。"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from core.models.common import new_id
from core.models.enums import PrecipitationType
from core.models.geometry import Polygon2D


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Weather(BaseModel):
    """一片受天气影响的区域及其气象参数。"""

    id: str = Field(default_factory=lambda: new_id("WX"))
    name: str | None = None

    wind_speed: float = Field(default=0.0, ge=0.0)
    """风速，米/秒。"""

    wind_direction: float = Field(default=0.0, ge=0.0, lt=360.0)
    """风向（来风方向），度，0=正北。"""

    visibility_m: float = Field(default=10000.0, gt=0.0)
    """能见度，米。"""

    precipitation: PrecipitationType = PrecipitationType.NONE

    affected_area: Polygon2D
    """受影响区域多边形（米制局部坐标）。"""

    observed_at: datetime = Field(default_factory=_utcnow)
