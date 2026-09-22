"""低空航路网络（NetworkX 有向图）。

- 节点：Waypoint（起降点/航路点/应急备降点），保留三维位置与容量/风险；
- 边：相邻航路点构成的可飞航段，高度作为边属性（高度层模型，而非全 3D 体素）；
- 一条 AirRoute 走廊默认双向通行，其有序 waypoint 序列被展开为航段；
- 多条走廊共用同一物理有向航段时容量取小、流量取大、风险与状态取最差。
  current_flow 是同一航段的观测值，不能按走廊或双向边累加为系统总流量。

第三阶段的 A* 直接在该图上以“可配置多目标边代价”搜索。
"""

from __future__ import annotations

import hashlib
import math
from typing import Iterable

import networkx as nx

from core.models import AirRoute, AirspaceRestriction, RouteStatus, Waypoint
from simulation.environment.city import CityEnvironment

# 状态严重度排序：用于共享航段取最差状态
_STATUS_ORDER = {
    RouteStatus.OPEN: 0,
    RouteStatus.CONGESTED: 1,
    RouteStatus.RESTRICTED: 2,
    RouteStatus.CLOSED: 3,
}


class RouteNetwork:
    def __init__(self) -> None:
        self.graph: nx.DiGraph = nx.DiGraph()

    # ---------- 构建 ----------

    @classmethod
    def build(
        cls,
        waypoints: Iterable[Waypoint],
        routes: Iterable[AirRoute],
    ) -> "RouteNetwork":
        network = cls()
        wp_map = {w.id: w for w in waypoints}
        for waypoint in wp_map.values():
            network.add_waypoint(waypoint)
        for route in routes:
            network.add_route(route, wp_map)
        return network

    def add_waypoint(self, waypoint: Waypoint) -> None:
        self.graph.add_node(
            waypoint.id,
            name=waypoint.name,
            type=waypoint.type.value,
            position=waypoint.position,
            capacity=waypoint.capacity,
            risk_level=waypoint.risk_level,
        )

    def add_route(self, route: AirRoute, wp_map: dict[str, Waypoint]) -> None:
        sequence = route.waypoint_ids or [route.start, route.end]
        if len(sequence) < 2:
            raise ValueError(f"航路 {route.id} 至少需要两个航路点")
        for wp_id in sequence:
            if wp_id not in wp_map:
                raise ValueError(f"航路 {route.id} 引用了不存在的航路点: {wp_id}")
        if sequence[0] != route.start or sequence[-1] != route.end:
            raise ValueError(f"航路 {route.id} 的端点与 waypoint_ids 不一致")
        if len(set(sequence)) != len(sequence):
            raise ValueError(f"航路 {route.id} 不允许重复航路点")

        for u, v in zip(sequence[:-1], sequence[1:]):
            segment_length = wp_map[u].position.distance_to(wp_map[v].position)
            altitude = (wp_map[u].position.z + wp_map[v].position.z) / 2
            self._merge_edge(
                u,
                v,
                route_id=route.id,
                distance=segment_length,
                capacity=route.capacity,
                current_flow=route.current_flow,
                risk_level=route.risk_level,
                altitude=altitude,
                status=route.status,
            )
            # 走廊双向可飞：反向航段对称添加
            self._merge_edge(
                v,
                u,
                route_id=route.id,
                distance=segment_length,
                capacity=route.capacity,
                current_flow=route.current_flow,
                risk_level=route.risk_level,
                altitude=altitude,
                status=route.status,
            )

    def _merge_edge(self, u: str, v: str, **attrs) -> None:
        if not self.graph.has_edge(u, v):
            self.graph.add_edge(
                u,
                v,
                route_ids=[attrs["route_id"]],
                distance=attrs["distance"],
                capacity=attrs["capacity"],
                current_flow=attrs["current_flow"],
                risk_level=attrs["risk_level"],
                altitude=attrs["altitude"],
                status=attrs["status"],
            )
            return

        data = self.graph.get_edge_data(u, v)
        if attrs["route_id"] not in data["route_ids"]:
            data["route_ids"].append(attrs["route_id"])
        data["capacity"] = min(data["capacity"], attrs["capacity"])
        data["current_flow"] = max(data["current_flow"], attrs["current_flow"])
        data["risk_level"] = max(data["risk_level"], attrs["risk_level"])
        if _STATUS_ORDER[attrs["status"]] > _STATUS_ORDER[data["status"]]:
            data["status"] = attrs["status"]

    @staticmethod
    def generate_routes(
        waypoints: Iterable[Waypoint],
        city: CityEnvironment,
        restrictions: Iterable[AirspaceRestriction] = (),
        *,
        neighbor_count: int = 3,
        max_distance: float | None = None,
        capacity: int = 20,
        horizontal_clearance: float = 5.0,
        vertical_clearance: float = 5.0,
    ) -> list[AirRoute]:
        """确定性近邻连边：所有节点（含备降点）按距离选择可飞邻居。

        不保证任意障碍场景都连通；孤立点需增设航路点/高度层，由调用方报告。
        输入限制全部按当前 active 状态检查，运行期间仍需动态复核。
        """
        if not isinstance(neighbor_count, int) or neighbor_count < 1:
            raise ValueError("neighbor_count 必须为正整数")
        if not isinstance(capacity, int) or capacity < 1:
            raise ValueError("capacity 必须为正整数")
        if max_distance is not None and (not math.isfinite(max_distance) or max_distance <= 0):
            raise ValueError("max_distance 必须为正有限数")
        if any(not math.isfinite(c) or c < 0 for c in (horizontal_clearance, vertical_clearance)):
            raise ValueError("净空必须为非负有限数")
        nodes = sorted(waypoints, key=lambda w: w.id)
        if len({w.id for w in nodes}) != len(nodes):
            raise ValueError("自动连边不允许重复航路点 ID")
        active = [r for r in restrictions if r.active]
        routes: dict[tuple[str, str], AirRoute] = {}
        # ponytail: 城市级数百节点用 O(n²) 近邻搜索；大规模再引入空间索引。
        for node in nodes:
            candidates = sorted((other for other in nodes if other.id != node.id),
                                key=lambda other: (node.position.distance_to(other.position), other.id))
            accepted = 0
            for other in candidates:
                distance = node.position.distance_to(other.position)
                if max_distance is not None and distance > max_distance:
                    break
                if distance <= 1e-8:
                    continue
                if not city.is_segment_clear(node.position, other.position, vertical_clearance,
                                             horizontal_clearance=horizontal_clearance):
                    continue
                if any(r.polygon.intersects_prism(node.position, other.position,
                                                 r.min_altitude, r.max_altitude,
                                                 horizontal_clearance) for r in active):
                    continue
                key = tuple(sorted((node.id, other.id)))
                digest = hashlib.sha256(repr(key).encode()).hexdigest()[:16]
                routes[key] = AirRoute(id=f"AUTO-{digest}", name=f"自动航段 {key[0]} ↔ {key[1]}",
                                       start=key[0], end=key[1], waypoint_ids=list(key),
                                       distance=distance, capacity=capacity, current_flow=0,
                                       risk_level=max(node.risk_level, other.risk_level))
                accepted += 1
                if accepted >= neighbor_count:
                    break
        return [routes[key] for key in sorted(routes)]

    # ---------- 查询 ----------

    def waypoint_ids(self) -> list[str]:
        return list(self.graph.nodes)

    def neighbors(self, node: str) -> list[str]:
        return list(self.graph.successors(node))

    def edge_data(self, u: str, v: str) -> dict:
        return self.graph.get_edge_data(u, v)

    def has_edge(self, u: str, v: str) -> bool:
        return self.graph.has_edge(u, v)

    def shortest_path_by_distance(self, source: str, target: str) -> list[str]:
        """以纯几何距离求最短路（第二阶段连通性校验用；第三阶段替换为多目标 A*）。"""
        return nx.dijkstra_path(self.graph, source, target, weight="distance")

    def validate_against_city(self, city) -> list[dict]:
        """检查全部航段是否穿越建筑，返回违规航段列表。"""
        violations: list[dict] = []
        positions = {
            nid: data["position"] for nid, data in self.graph.nodes(data=True)
        }
        for u, v, data in self.graph.edges(data=True):
            # 只校验一次（双向边重复）
            if u > v:
                continue
            if not city.is_segment_clear(positions[u], positions[v]):
                violations.append(
                    {
                        "from": u,
                        "to": v,
                        "route_ids": data["route_ids"],
                        "altitude": data["altitude"],
                    }
                )
        return violations

    # ---------- 序列化 ----------

    def to_dict(self) -> dict:
        nodes = [
            {
                "id": nid,
                "name": data.get("name"),
                "type": data.get("type"),
                "position": data["position"].model_dump(),
                "capacity": data.get("capacity"),
                "risk_level": data.get("risk_level"),
            }
            for nid, data in self.graph.nodes(data=True)
        ]
        edges = []
        for u, v, data in self.graph.edges(data=True):
            edges.append(
                {
                    "source": u,
                    "target": v,
                    "route_ids": data["route_ids"],
                    "distance": round(data["distance"], 2),
                    "capacity": data["capacity"],
                    "current_flow": data["current_flow"],
                    "utilization": round(
                        data["current_flow"] / data["capacity"], 3
                    )
                    if data["capacity"]
                    else 0.0,
                    "risk_level": data["risk_level"],
                    "altitude": data["altitude"],
                    "status": data["status"].value,
                }
            )
        return {"nodes": nodes, "edges": edges}
