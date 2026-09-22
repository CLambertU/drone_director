"""基础几何类型。

仿真内核统一使用局部米制坐标（ENU：东向 x / 北向 y / 天向 z），
与 Cesium 的 WGS84 经纬度之间的转换统一收敛在 core.coords 包，
禁止在业务代码中散落经纬度与米制的混用逻辑。
"""

from __future__ import annotations

import math
from typing import Iterable

from pydantic import BaseModel, ConfigDict, Field, model_validator

_EPS = 1e-8  # 米制几何接触容差


class Position2D(BaseModel):
    """平面位置，单位：米（相对城市局部坐标原点）。"""

    model_config = ConfigDict(allow_inf_nan=False)

    x: float = 0.0
    y: float = 0.0

    def distance_to(self, other: Position2D) -> float:
        return math.hypot(self.x - other.x, self.y - other.y)


class Position3D(BaseModel):
    """局部 ENU 米制坐标；z 相对城市原点切平面，不是离地高度。

    负 z 可用于坐标转换；地面/飞行高度约束由城市与飞行模型判定。
    """

    model_config = ConfigDict(allow_inf_nan=False)

    x: float = 0.0
    y: float = 0.0
    z: float = 0.0

    @property
    def xy(self) -> Position2D:
        return Position2D(x=self.x, y=self.y)

    def distance_to(self, other: Position3D) -> float:
        """三维欧氏距离，单位：米。"""
        return math.sqrt(
            (self.x - other.x) ** 2
            + (self.y - other.y) ** 2
            + (self.z - other.z) ** 2
        )

    def horizontal_distance_to(self, other: Position3D) -> float:
        return math.hypot(self.x - other.x, self.y - other.y)


class Polygon2D(BaseModel):
    """平面多边形（闭合环，首尾点无需重复），用于禁飞区/天气影响区。"""

    points: list[Position2D] = Field(min_length=3)

    @model_validator(mode="after")
    def _validate_ring(self) -> Polygon2D:
        # 接受常见的显式闭合环，但内部只保留一个首点。
        if self.points[0] == self.points[-1]:
            self.points = self.points[:-1]
        if len({(p.x, p.y) for p in self.points}) != len(self.points):
            raise ValueError("多边形不允许重复顶点")
        if len(self.points) < 3:
            raise ValueError("多边形至少需要 3 个不同顶点")
        edges = list(zip(self.points, self.points[1:] + self.points[:1]))
        area2 = sum(a.x * b.y - b.x * a.y for a, b in edges)
        if abs(area2) <= _EPS:
            raise ValueError("多边形面积必须大于零")
        for i, (a, b) in enumerate(edges):
            if a.distance_to(b) <= _EPS:
                raise ValueError("多边形边长必须大于零")
            for j in range(i + 1, len(edges)):
                if j == i + 1 or (i == 0 and j == len(edges) - 1):
                    continue
                if _segments_intersect(a, b, *edges[j]):
                    raise ValueError("多边形不允许自交或非相邻边接触")
        return self

    def contains(self, point: Position2D) -> bool:
        """射线法判断点是否在多边形内；边界及顶点属于内部。"""
        result = False
        n = len(self.points)
        j = n - 1
        for i in range(n):
            pi, pj = self.points[i], self.points[j]
            if _point_segment_distance(point, pi, pj) <= _EPS:
                return True
            if (pi.y > point.y) != (pj.y > point.y) and (
                point.x
                < (pj.x - pi.x) * (point.y - pi.y) / (pj.y - pi.y) + pi.x
            ):
                result = not result
            j = i
        return result

    def contains_any(self, points: Iterable[Position2D]) -> bool:
        return any(self.contains(p) for p in points)

    def intersects_segment(
        self, start: Position2D, end: Position2D, clearance: float = 0.0,
    ) -> bool:
        """精确线段/多边形相交，clearance 为水平欧氏净空，接触算相交。"""
        if not math.isfinite(clearance) or clearance < 0:
            raise ValueError("水平净空必须是非负有限数")
        if self.contains(start) or self.contains(end):
            return True
        for a, b in zip(self.points, self.points[1:] + self.points[:1]):
            if _segments_intersect(start, end, a, b):
                return True
            distance = min(
                _point_segment_distance(start, a, b),
                _point_segment_distance(end, a, b),
                _point_segment_distance(a, start, end),
                _point_segment_distance(b, start, end),
            )
            if distance <= clearance + _EPS:
                return True
        return False

    def intersects_prism(
        self, start: Position3D, end: Position3D,
        min_altitude: float, max_altitude: float,
        horizontal_clearance: float = 0.0,
    ) -> bool:
        """线性三维航段与闭合挤出体相交；先裁剪高度区间再检查平面。

        因为只检查处于高度带内的那段轨迹，上升/下降段不会因平均高度
        或离散采样而漏检窄障碍物。高度相对同一个局部 ENU 原点。
        """
        if not (math.isfinite(min_altitude) and math.isfinite(max_altitude)):
            raise ValueError("高度带必须是有限数")
        if min_altitude > max_altitude:
            raise ValueError("高度带下限不得超过上限")
        if not math.isfinite(horizontal_clearance) or horizontal_clearance < 0:
            raise ValueError("水平净空必须是非负有限数")
        dz = end.z - start.z
        if abs(dz) <= _EPS:
            if not min_altitude - _EPS <= start.z <= max_altitude + _EPS:
                return False
            t0, t1 = 0.0, 1.0
        else:
            lo, hi = sorted(((min_altitude - start.z) / dz, (max_altitude - start.z) / dz))
            t0, t1 = max(0.0, lo), min(1.0, hi)
            if t0 > t1:
                return False
        a, b = [Position2D(x=start.x + (end.x - start.x) * t,
                           y=start.y + (end.y - start.y) * t) for t in (t0, t1)]
        return self.intersects_segment(a, b, horizontal_clearance)


def _point_segment_distance(p: Position2D, a: Position2D, b: Position2D) -> float:
    dx, dy = b.x - a.x, b.y - a.y
    length2 = dx * dx + dy * dy
    if length2 == 0:
        return p.distance_to(a)
    t = max(0.0, min(1.0, ((p.x - a.x) * dx + (p.y - a.y) * dy) / length2))
    return math.hypot(p.x - a.x - t * dx, p.y - a.y - t * dy)


def _segments_intersect(a: Position2D, b: Position2D, c: Position2D, d: Position2D) -> bool:
    def cross(p: Position2D, q: Position2D, r: Position2D) -> float:
        return (q.x - p.x) * (r.y - p.y) - (q.y - p.y) * (r.x - p.x)

    ab_c, ab_d = cross(a, b, c), cross(a, b, d)
    cd_a, cd_b = cross(c, d, a), cross(c, d, b)
    if ((ab_c < 0 < ab_d or ab_d < 0 < ab_c)
            and (cd_a < 0 < cd_b or cd_b < 0 < cd_a)):
        return True
    return min(_point_segment_distance(a, c, d), _point_segment_distance(b, c, d),
               _point_segment_distance(c, a, b), _point_segment_distance(d, a, b)) <= _EPS
