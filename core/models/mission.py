"""运输任务实体。"""

from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from core.models.common import new_id
from core.models.enums import MissionStatus
from core.models.geometry import Position3D


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Mission(BaseModel):
    id: str = Field(default_factory=lambda: new_id("MS"))
    aircraft_id: str | None = None
    """执行任务的飞行器 ID。"""

    origin: Position3D
    destination: Position3D

    priority: int = Field(default=0, ge=0, le=10)
    status: MissionStatus = MissionStatus.PENDING

    route_id: str | None = None
    """分配的航路 ID（调度阶段填充）。"""

    created_at: datetime = Field(default_factory=_utcnow)
    assigned_at: datetime | None = None
    completed_at: datetime | None = None
    created_sim_time: float = Field(default=0.0, ge=0.0)
    started_sim_time: float | None = None
    completed_sim_time: float | None = None
    baseline_duration_s: float | None = Field(default=None, ge=0.0)
    distance_flown_m: float = Field(default=0.0, ge=0.0)
    delay_s: float = Field(default=0.0, ge=0.0)
