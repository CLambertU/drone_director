"""城市环境、三维碰撞与构建器测试。"""

from __future__ import annotations

import pytest

from core.models import Building, CityConfig, GeoPoint, Position3D, Waypoint
from simulation.environment.builder import CityBuilder, rectangle_polygon
from simulation.environment.city import CityEnvironment


def make_config(**overrides) -> CityConfig:
    base = dict(
        name="测试城",
        origin=GeoPoint(latitude=30.0, longitude=104.0),
        min_x=0,
        min_y=0,
        max_x=2000,
        max_y=2000,
        grid_resolution=10,
        building_seed=7,
        generate_buildings=True,
    )
    base.update(overrides)
    return CityConfig(**base)


def make_building(cx=500, cy=500, size=40, height=60) -> Building:
    return Building(
        id="BLT1",
        footprint=rectangle_polygon(cx, cy, size, size),
        height=height,
    )


def test_3d_collision_below_and_above_roof():
    city = CityEnvironment(make_config(), [make_building()])

    # 建筑内部、低于楼顶 -> 碰撞
    assert city.is_position_safe(Position3D(x=500, y=500, z=30)) is False
    # 楼顶上方（含默认 5m 净空）-> 安全
    assert city.is_position_safe(Position3D(x=500, y=500, z=70)) is True
    # 建筑外 -> 安全
    assert city.is_position_safe(Position3D(x=100, y=100, z=10)) is True


def test_segment_clears_over_roof_but_not_through():
    city = CityEnvironment(make_config(), [make_building(height=50)])
    # 120m 从楼顶上方经过 -> 安全
    high = (Position3D(x=400, y=500, z=120), Position3D(x=600, y=500, z=120))
    assert city.is_segment_clear(*high) is True
    # 30m 横穿建筑 -> 受阻
    low = (Position3D(x=400, y=500, z=30), Position3D(x=600, y=500, z=30))
    assert city.is_segment_clear(*low) is False


def test_builder_is_deterministic():
    cfg = make_config()
    waypoints = [Waypoint(id="W1", position=Position3D(x=0, y=0, z=120))]
    b1 = CityBuilder.generate_buildings(cfg, waypoints)
    b2 = CityBuilder.generate_buildings(cfg, waypoints)
    assert len(b1) > 20
    assert [(b.id, b.height) for b in b1] == [(b.id, b.height) for b in b2]


def test_builder_respects_vertiport_clearance():
    """起降点周边净空内不得生成建筑。"""
    cfg = make_config()
    wps = [
        Waypoint(id="W1", position=Position3D(x=0, y=0, z=120)),
        Waypoint(id="W2", position=Position3D(x=1000, y=1000, z=120)),
    ]
    city = CityBuilder.build(cfg, waypoints=wps)
    for wp in wps:
        for building in city.buildings:
            cx = (
                building.footprint.points[0].x
                + building.footprint.points[2].x
            ) / 2
            cy = (
                building.footprint.points[0].y
                + building.footprint.points[2].y
            ) / 2
            # 包围盒中心距航点过近的建筑不应存在（简化检查）
            assert not (
                abs(cx - wp.position.x) < 40 and abs(cy - wp.position.y) < 40
            ), f"航点 {wp.id} 净空被建筑 {building.id} 侵入"


def test_builder_height_below_corridor():
    city = CityBuilder.build(make_config(), waypoints=[])
    assert city.max_building_height() <= 100.0


def test_declared_buildings_used_when_generation_off():
    cfg = make_config(generate_buildings=False)
    city = CityBuilder.build(cfg, buildings=[make_building()])
    assert city.building_count == 1


def test_narrow_building_collision_independent_of_grid_resolution():
    city = CityEnvironment(make_config(grid_resolution=100), [make_building(cx=51, cy=50, size=2)])
    assert not city.is_segment_clear(Position3D(x=0, y=50, z=30), Position3D(x=100, y=50, z=30))


def test_city_bounds_ground_and_clearance():
    city = CityEnvironment(make_config(), [make_building()])
    assert not city.is_position_safe(Position3D(x=-1, y=0, z=50))
    assert not city.is_position_safe(Position3D(x=1, y=1, z=-1))
    assert city.is_position_safe(Position3D(x=1, y=1, z=5))
    assert not city.is_position_safe(Position3D(x=1, y=1, z=5), horizontal_clearance=2)
    assert not city.is_position_safe(Position3D(x=475, y=500, z=30), horizontal_clearance=5)
    assert city.is_position_safe(Position3D(x=474, y=500, z=30), horizontal_clearance=5)
    assert not city.is_position_safe(Position3D(x=500, y=500, z=65))
    assert city.is_position_safe(Position3D(x=500, y=500, z=65.01))
    with pytest.raises(ValueError):
        city.is_position_safe(Position3D(x=500, y=500, z=100), vertical_clearance=-1)


def test_sloped_flight_uses_altitude_at_building():
    city = CityEnvironment(make_config(), [make_building(cx=100, cy=500, size=2, height=30)])
    assert not city.is_segment_clear(Position3D(x=0, y=500, z=0), Position3D(x=1000, y=500, z=100))
    assert city.is_segment_clear(Position3D(x=0, y=500, z=50), Position3D(x=1000, y=500, z=150))


def test_rectangular_building_clearance_uses_both_extents():
    # 旧版用 min(width,height) 把长楼误当成小正方形，会漏掉其长边净空。
    assert CityBuilder._is_protected(100, 100, [(100, 200)], 10, 100)
