"""城市三维环境相关模型。"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from core.models.common import new_id
from core.models.geometry import Polygon2D


class GeoPoint(BaseModel):
    """WGS84 大地坐标。"""

    latitude: float = Field(ge=-90.0, le=90.0)
    longitude: float = Field(ge=-180.0, le=180.0)
    altitude: float = 0.0
    """椭球高，米。"""


class CityConfig(BaseModel):
    """城市环境配置：局部坐标原点、平面边界、栅格精度。"""

    name: str = "天枢市"
    origin: GeoPoint
    """局部 ENU 坐标原点对应的 WGS84 位置。"""

    min_x: float = 0.0
    min_y: float = 0.0
    max_x: float = 2000.0
    max_y: float = 2000.0

    grid_resolution: float = Field(default=10.0, gt=0.0)
    """占用栅格单元边长，米。"""

    building_seed: int = 42
    """程序化生成建筑时的确定性随机种子。"""

    generate_buildings: bool = True
    """播种时若未显式给出建筑列表，是否按街区程序化生成。"""

    @model_validator(mode="after")
    def _validate_bounds(self) -> CityConfig:
        if self.max_x <= self.min_x or self.max_y <= self.min_y:
            raise ValueError("城市边界必须满足 max > min")
        return self

    @property
    def width(self) -> float:
        return self.max_x - self.min_x

    @property
    def height(self) -> float:
        return self.max_y - self.min_y


class Building(BaseModel):
    """城市建筑：平面 footprint 挤出盒状体（MVP），后续可扩展为多段面。"""

    id: str = Field(default_factory=lambda: new_id("BL"))
    name: str | None = None

    footprint: Polygon2D
    """建筑占地多边形（米制局部坐标）。"""

    height: float = Field(gt=0.0)
    """建筑顶部离地高度，米。"""

    elevation: float = Field(default=0.0, ge=0.0)
    """基底离地高度（地形起伏预留），米。"""
