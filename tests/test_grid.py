"""二维占用栅格测试。"""

from __future__ import annotations

import pytest

from core.models.geometry import Polygon2D, Position2D
from simulation.environment.grid import OccupancyGrid2D


def square(cx: float, cy: float, size: float) -> Polygon2D:
    h = size / 2
    return Polygon2D(
        points=[
            Position2D(x=cx - h, y=cy - h),
            Position2D(x=cx + h, y=cy - h),
            Position2D(x=cx + h, y=cy + h),
            Position2D(x=cx - h, y=cy + h),
        ]
    )


@pytest.fixture
def grid() -> OccupancyGrid2D:
    g = OccupancyGrid2D(0, 0, 100, 100, resolution=10)
    g.rasterize_polygon(square(50, 50, 40))  # 30~70 区域
    return g


def test_grid_dimensions():
    g = OccupancyGrid2D(0, 0, 250, 150, resolution=10)
    assert (g.nx, g.ny) == (25, 15)


def test_rasterization_blocks_interior(grid):
    assert grid.is_xy_blocked(50, 50) is True
    assert grid.is_xy_blocked(35, 65) is True


def test_rasterization_frees_outside(grid):
    assert grid.is_xy_blocked(10, 10) is False
    assert grid.is_xy_blocked(90, 90) is False


def test_out_of_bounds_is_blocked(grid):
    # 城市空域之外视为不可飞
    assert grid.is_xy_blocked(-5, 50) is True
    assert grid.is_xy_blocked(105, 50) is True


def test_segment_blocked(grid):
    # 从西侧穿过中心建筑
    assert grid.is_segment_blocked_2d(0, 50, 100, 50) is True
    # 南侧街道，不穿建筑
    assert grid.is_segment_blocked_2d(0, 10, 100, 10) is False


def test_blocked_ratio(grid):
    # 40x40 建筑闭合边界触及 6x6 个单元，保守占用面积大于实际建筑面积。
    assert grid.blocked_ratio == pytest.approx(0.36)


def test_narrow_building_not_lost_between_cell_centers():
    g = OccupancyGrid2D(0, 0, 100, 100, resolution=10)
    g.rasterize_polygon(square(51, 51, 2))
    assert g.is_xy_blocked(51, 51)
    assert g.is_segment_blocked_2d(0, 51, 100, 51, step=100)


@pytest.mark.parametrize("resolution", [0, -1, float("nan"), float("inf")])
def test_invalid_resolution_rejected(resolution):
    with pytest.raises(ValueError):
        OccupancyGrid2D(0, 0, 100, 100, resolution)
