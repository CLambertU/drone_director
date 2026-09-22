"""临时空域管制实体。"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from core.models.common import new_id
from core.models.geometry import Polygon2D


class AirspaceRestriction(BaseModel):
    id: str = Field(default_factory=lambda: new_id("RZ"))
    name: str | None = None

    polygon: Polygon2D
    """管制区平面范围（米制局部坐标）。"""

    min_altitude: float = Field(default=0.0, ge=0.0)
    max_altitude: float = Field(default=300.0, ge=0.0)

    active: bool = True
    reason: str = ""

    @model_validator(mode="after")
    def _validate_altitude_band(self) -> AirspaceRestriction:
        if self.max_altitude < self.min_altitude:
            raise ValueError("max_altitude 不能小于 min_altitude")
        return self
