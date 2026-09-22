"""二维占用栅格（建筑碰撞层）。

用于保守二维占用展示/查询；最终三维飞行合法性由 CityEnvironment 精确几何判定。
所有与建筑投影接触的单元均标记占用，因此栅格面积是障碍面积的上界。
"""

from __future__ import annotations

import math

import numpy as np

from core.models.geometry import Polygon2D, Position2D


class OccupancyGrid2D:
    def __init__(
        self,
        min_x: float,
        min_y: float,
        max_x: float,
        max_y: float,
        resolution: float,
    ) -> None:
        if not all(math.isfinite(v) for v in (min_x, min_y, max_x, max_y, resolution)):
            raise ValueError("栅格配置必须是有限数")
        if resolution <= 0:
            raise ValueError("栅格分辨率必须为正数")
        if max_x <= min_x or max_y <= min_y:
            raise ValueError("栅格边界必须满足 max > min")
        self.min_x = float(min_x)
        self.min_y = float(min_y)
        self.max_x = float(max_x)
        self.max_y = float(max_y)
        self.resolution = float(resolution)

        self.nx = max(1, math.ceil((max_x - min_x) / resolution))
        self.ny = max(1, math.ceil((max_y - min_y) / resolution))
        # 行=y，列=x；True 表示该单元被建筑投影占用
        self.occupied = np.zeros((self.ny, self.nx), dtype=bool)

    # ---------- 坐标 <-> 栅格索引 ----------

    def world_to_cell(self, x: float, y: float) -> tuple[int, int] | None:
        """世界坐标 -> (col, row)；严格越界返回 None。

        边界点（x == max_x 等）属于合法空域，索引钳制到最后一个单元。
        """
        if not (self.min_x <= x <= self.max_x and self.min_y <= y <= self.max_y):
            return None
        col = int((x - self.min_x) / self.resolution)
        row = int((y - self.min_y) / self.resolution)
        return min(col, self.nx - 1), min(row, self.ny - 1)

    def cell_center(self, col: int, row: int) -> Position2D:
        return Position2D(
            x=self.min_x + (col + 0.5) * self.resolution,
            y=self.min_y + (row + 0.5) * self.resolution,
        )

    # ---------- 栅格化 ----------

    def rasterize_polygon(self, polygon: Polygon2D) -> int:
        """把多边形占用区域烧入栅格，返回新增占用单元数。"""
        xs = [p.x for p in polygon.points]
        ys = [p.y for p in polygon.points]
        x0, x1 = max(min(xs), self.min_x), min(max(xs), self.max_x)
        y0, y1 = max(min(ys), self.min_y), min(max(ys), self.max_y)
        if x1 < x0 or y1 < y0:
            return 0

        # 闭合边界也占用：精确落在格线时需覆盖格线两侧的单元。
        c0, r0 = self.world_to_cell_clamped(x0 - 1e-8, y0 - 1e-8)
        c1, r1 = self.world_to_cell_clamped(x1, y1)

        added = 0
        for row in range(r0, r1 + 1):
            for col in range(c0, c1 + 1):
                left, bottom = self.min_x + col * self.resolution, self.min_y + row * self.resolution
                right, top = min(left + self.resolution, self.max_x), min(bottom + self.resolution, self.max_y)
                corners = [Position2D(x=left, y=bottom), Position2D(x=right, y=bottom),
                           Position2D(x=right, y=top), Position2D(x=left, y=top)]
                covered = any(left <= p.x <= right and bottom <= p.y <= top for p in polygon.points)
                if covered or any(polygon.intersects_segment(a, b)
                                  for a, b in zip(corners, corners[1:] + corners[:1])):
                    if not self.occupied[row, col]:
                        added += 1
                    self.occupied[row, col] = True
        return added

    def world_to_cell_clamped(self, x: float, y: float) -> tuple[int, int]:
        col = int((x - self.min_x) / self.resolution)
        row = int((y - self.min_y) / self.resolution)
        return (
            min(max(col, 0), self.nx - 1),
            min(max(row, 0), self.ny - 1),
        )

    # ---------- 查询 ----------

    def is_xy_blocked(self, x: float, y: float) -> bool:
        cell = self.world_to_cell(x, y)
        if cell is None:
            # 边界外视为不可飞（城市空域之外）
            return True
        col, row = cell
        return bool(self.occupied[row, col])

    def is_segment_blocked_2d(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
        step: float | None = None,
    ) -> bool:
        """精确线段/占用单元检查。step 保留兼容，已不采用离散采样。"""
        if step is not None and (not math.isfinite(step) or step <= 0):
            raise ValueError("step 必须为正有限数")
        if self.world_to_cell(x1, y1) is None or self.world_to_cell(x2, y2) is None:
            return True
        c0, r0 = self.world_to_cell_clamped(min(x1, x2) - 1e-8, min(y1, y2) - 1e-8)
        c1, r1 = self.world_to_cell_clamped(max(x1, x2), max(y1, y2))
        for row, col in np.argwhere(self.occupied[r0:r1 + 1, c0:c1 + 1]):
            left = self.min_x + (int(col) + c0) * self.resolution
            bottom = self.min_y + (int(row) + r0) * self.resolution
            t0, t1 = 0.0, 1.0
            for origin, delta, low, high in ((x1, x2 - x1, left, min(left + self.resolution, self.max_x)),
                                           (y1, y2 - y1, bottom, min(bottom + self.resolution, self.max_y))):
                if delta == 0:
                    if not low <= origin <= high:
                        t0, t1 = 1.0, 0.0
                        break
                else:
                    near, far = sorted(((low - origin) / delta, (high - origin) / delta))
                    t0, t1 = max(t0, near), min(t1, far)
            if t0 <= t1:
                return True
        return False

    @property
    def blocked_ratio(self) -> float:
        total = self.occupied.size
        return float(self.occupied.sum() / total) if total else 0.0

    def stats(self) -> dict:
        return {
            "resolution": self.resolution,
            "cells_x": self.nx,
            "cells_y": self.ny,
            "total_cells": int(self.occupied.size),
            "blocked_cells": int(self.occupied.sum()),
            "blocked_ratio": round(self.blocked_ratio, 4),
        }
