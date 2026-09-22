"""低空航路（航路网中的走廊/边序列）。"""

from __future__ import annotations

from pydantic import BaseModel, Field, computed_field

from core.models.common import new_id
from core.models.enums import RouteStatus


class AirRoute(BaseModel):
    id: str = Field(default_factory=lambda: new_id("RT"))
    name: str | None = None

    start: str
    """起点航路点 ID。"""

    end: str
    """终点航路点 ID。"""

    waypoint_ids: list[str] = Field(default_factory=list)
    """走廊经过的有序航路点序列（含 start/end）；为空表示直连。"""

    distance: float = Field(default=0.0, ge=0.0)
    """航路长度，米。"""

    capacity: int = Field(default=10, ge=1)
    """单位时间最大通行容量（架次）。"""

    current_flow: int = Field(default=0, ge=0)
    """当前实际流量（架次），允许超过容量并据此判定拥堵。"""

    risk_level: float = Field(default=0.0, ge=0.0, le=1.0)
    """静态风险评分 0~1。"""

    status: RouteStatus = RouteStatus.OPEN

    @computed_field  # type: ignore[prop-decorator]
    @property
    def utilization(self) -> float:
        """航路利用率 = 当前流量 / 容量。"""
        return self.current_flow / self.capacity if self.capacity else 0.0
