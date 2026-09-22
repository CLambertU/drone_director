"""航路点（航路网节点）。"""

from __future__ import annotations

from pydantic import BaseModel, Field

from core.models.common import new_id
from core.models.enums import WaypointType
from core.models.geometry import Position3D


class Waypoint(BaseModel):
    id: str = Field(default_factory=lambda: new_id("WP"))
    name: str | None = None
    type: WaypointType = WaypointType.WAYPOINT

    position: Position3D
    capacity: int = Field(default=1, ge=0)
    """同时容纳/服务能力（单位时间可处理架次）。"""

    risk_level: float = Field(default=0.0, ge=0.0, le=1.0)
    """静态风险评分（建筑密度、人口密度等），0~1。"""
