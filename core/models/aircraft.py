"""飞行器实体。"""

from __future__ import annotations

from pydantic import BaseModel, Field, computed_field

from core.models.common import new_id
from core.models.enums import AircraftStatus
from core.models.geometry import Position3D


class Aircraft(BaseModel):
    """单架无人机的运行态快照。

    仿真内核使用三维米制坐标 position，altitude 作为 position.z 的只读视图，
    保证“三维位置”与“高度”始终一致、不会出现两个真值源。
    """

    id: str = Field(default_factory=lambda: new_id("AC"))
    name: str | None = None
    model: str = "standard-uav"

    position: Position3D
    """当前三维位置（米，局部 ENU 坐标）。"""

    speed: float = Field(default=0.0, ge=0.0)
    """地速，米/秒。"""

    heading: float = Field(default=0.0, ge=0.0, lt=360.0)
    """航向角，度（0=正北，顺时针）。"""

    destination: Position3D | None = None
    """当前目的地（无任务时为空）。"""

    status: AircraftStatus = AircraftStatus.GROUNDED
    battery: float = Field(default=1.0, ge=0.0, le=1.0)
    """剩余电量比例 0~1。"""

    priority: int = Field(default=0, ge=0, le=10)
    """调度优先级，数值越大越优先（应急/医疗运输取高值）。"""

    max_speed: float = Field(default=20.0, gt=0.0)
    """最大飞行速度，米/秒。"""

    @computed_field  # type: ignore[prop-decorator]
    @property
    def altitude(self) -> float:
        """当前飞行高度（米），等价于 position.z。"""
        return self.position.z
