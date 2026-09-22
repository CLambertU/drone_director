"""航路网络构建与查询测试。"""

from __future__ import annotations

import pytest

from core.models import (
    AirRoute,
    AirspaceRestriction,
    Building,
    CityConfig,
    GeoPoint,
    Position3D,
    RouteStatus,
    Waypoint,
    WaypointType,
)
from simulation.environment.builder import rectangle_polygon
from simulation.environment.city import CityEnvironment
from simulation.environment.route_network import RouteNetwork


def wp(ac_id: str, x: float, y: float, z: float = 120.0) -> Waypoint:
    return Waypoint(id=ac_id, position=Position3D(x=x, y=y, z=z))


@pytest.fixture
def waypoints() -> list[Waypoint]:
    # L 形三个航点
    return [wp("A", 0, 0), wp("B", 1000, 0), wp("C", 1000, 1000)]


@pytest.fixture
def routes() -> list[AirRoute]:
    return [
        AirRoute(
            id="R1",
            start="A",
            end="C",
            waypoint_ids=["A", "B", "C"],
            distance=2000,
            capacity=10,
            current_flow=2,
            risk_level=0.2,
        )
    ]


def test_build_nodes_and_bidirectional_edges(waypoints, routes):
    network = RouteNetwork.build(waypoints, routes)
    assert set(network.waypoint_ids()) == {"A", "B", "C"}
    # 两条走廊段，双向 => 4 条有向边
    assert network.graph.number_of_edges() == 4
    assert network.has_edge("A", "B") and network.has_edge("B", "A")
    assert network.has_edge("B", "C") and network.has_edge("C", "B")


def test_edge_attributes(waypoints, routes):
    network = RouteNetwork.build(waypoints, routes)
    edge = network.edge_data("A", "B")
    assert edge["route_ids"] == ["R1"]
    assert edge["distance"] == pytest.approx(1000.0)
    assert edge["altitude"] == pytest.approx(120.0)
    assert edge["status"] == RouteStatus.OPEN


def test_shared_segment_merges_attributes(waypoints):
    routes = [
        AirRoute(
            id="R1", start="A", end="B", waypoint_ids=["A", "B"],
            distance=1000, capacity=10, current_flow=4, risk_level=0.2,
        ),
        AirRoute(
            id="R2", start="A", end="B", waypoint_ids=["A", "B"],
            distance=1000, capacity=5, current_flow=6, risk_level=0.5,
            status=RouteStatus.CONGESTED,
        ),
    ]
    network = RouteNetwork.build(waypoints, routes)
    edge = network.edge_data("A", "B")
    assert set(edge["route_ids"]) == {"R1", "R2"}
    assert edge["capacity"] == 5
    assert edge["current_flow"] == 6
    assert edge["risk_level"] == pytest.approx(0.5)
    assert edge["status"] == RouteStatus.CONGESTED

    # 同一路由重复加入不能重复累计物理航段容量或流量。
    network.add_route(routes[1], {w.id: w for w in waypoints})
    assert edge["capacity"] == 5 and edge["current_flow"] == 6
    assert len(edge["route_ids"]) == 2


def test_missing_waypoint_raises(waypoints):
    bad_route = AirRoute(
        id="RX", start="A", end="ZZ", waypoint_ids=["A", "ZZ"], distance=10
    )
    with pytest.raises(ValueError, match="ZZ"):
        RouteNetwork.build(waypoints, [bad_route])


def test_shortest_path_by_distance(waypoints, routes):
    network = RouteNetwork.build(waypoints, routes)
    # 增加近路 B->A? 构造直线捷径 A->C 不必要；验证 L 形路径可达即可
    path = network.shortest_path_by_distance("A", "C")
    assert path == ["A", "B", "C"]
    assert network.neighbors("A") == ["B"]


def test_to_dict_serialization(waypoints, routes):
    network = RouteNetwork.build(waypoints, routes)
    data = network.to_dict()
    assert len(data["nodes"]) == 3
    edge = data["edges"][0]
    assert {"source", "target", "route_ids", "distance", "utilization", "status"} <= set(edge)


def test_generation_connects_bays_deterministically_and_avoids_obstacles():
    city = CityEnvironment(CityConfig(origin=GeoPoint(latitude=30, longitude=104),
                                     max_x=500, max_y=500, generate_buildings=False),
                           [Building(footprint=rectangle_polygon(250, 250, 30, 100), height=150)])
    nodes = [wp("A", 50, 250), wp("B", 450, 250), wp("C", 250, 450),
             Waypoint(id="BAY", type=WaypointType.EMERGENCY_BAY,
                      position=Position3D(x=50, y=450, z=80))]
    generated = RouteNetwork.generate_routes(nodes, city, neighbor_count=2)
    assert [r.model_dump() for r in generated] == [r.model_dump() for r in
                                                 RouteNetwork.generate_routes(reversed(nodes), city, neighbor_count=2)]
    network = RouteNetwork.build(nodes, generated)
    assert network.neighbors("BAY")
    assert not network.has_edge("A", "B")
    assert network.shortest_path_by_distance("A", "B")
    assert network.validate_against_city(city) == []
    assert all(r.current_flow == 0 for r in generated)


def test_generation_honors_airspace_height_activity_and_max_distance():
    city = CityEnvironment(CityConfig(origin=GeoPoint(latitude=0, longitude=0), generate_buildings=False), [])
    nodes = [wp("A", 100, 100), wp("B", 200, 100)]
    restriction = AirspaceRestriction(polygon=rectangle_polygon(150, 100, 2, 50), min_altitude=100, max_altitude=150)
    assert RouteNetwork.generate_routes(nodes, city, [restriction]) == []
    restriction.active = False
    assert len(RouteNetwork.generate_routes(nodes, city, [restriction])) == 1
    restriction.active = True
    restriction.max_altitude = 119
    assert len(RouteNetwork.generate_routes(nodes, city, [restriction])) == 1
    assert RouteNetwork.generate_routes(nodes, city, max_distance=99) == []


def test_repeated_build_has_same_physical_segment_capacity(waypoints, routes):
    net = RouteNetwork.build(waypoints, routes * 3)
    assert net.edge_data("A", "B")["capacity"] == routes[0].capacity
    assert net.edge_data("A", "B")["current_flow"] == routes[0].current_flow
    assert net.edge_data("B", "A")["current_flow"] == routes[0].current_flow
