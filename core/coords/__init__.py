"""坐标转换层。

约束：仿真与算法内部只允许使用米制局部 ENU 坐标（core.models.geometry），
仅在 API 序列化与 Cesium 前端边界处调用本包转换为 WGS84。
"""

from core.coords.transform import GeoOrigin

__all__ = ["GeoOrigin"]
