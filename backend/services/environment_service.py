"""城市环境与航路网络服务。

持有当前运行的 CityEnvironment 与 RouteNetwork，
在播种或底层实体变化后统一重建，供 API 与后续仿真引擎共享同一实例。
"""

from __future__ import annotations

from backend.logging_config import get_logger
from core.models import Building, CityConfig
from core.repository import RepositoryRegistry
from simulation.environment.builder import CityBuilder
from simulation.environment.city import CityEnvironment
from simulation.environment.route_network import RouteNetwork

logger = get_logger(__name__)


class EnvironmentService:
    def __init__(self) -> None:
        self.city_config: CityConfig | None = None
        self.declared_buildings: list[Building] | None = None
        self.city: CityEnvironment | None = None
        self.network: RouteNetwork | None = None
        self.version: int = 0

    def install_from(self, staged: EnvironmentService) -> None:
        """调用者持有 registry.lock 时提交完整环境快照。"""
        self.city_config = staged.city_config
        self.declared_buildings = staged.declared_buildings
        self.city = staged.city
        self.network = staged.network
        self.version += 1

    def is_ready(self) -> bool:
        return self.city is not None and self.network is not None

    def apply_seed(
        self,
        city_config: CityConfig | None,
        declared_buildings: list[Building] | None,
        registry: RepositoryRegistry,
    ) -> dict:
        """应用播种数据：构建城市（可能程序化生成建筑）与航路网络。"""
        if city_config is None:
            raise ValueError("缺少 city 配置，无法构建城市环境")
        staged = EnvironmentService()
        staged.city_config = city_config
        staged.declared_buildings = declared_buildings
        result = staged.rebuild_all(registry)
        self.install_from(staged)
        return result

    def rebuild_city(self, waypoints: list | None = None) -> CityEnvironment:
        if self.city_config is None:
            raise RuntimeError("尚未加载城市配置，请先播种 Demo 数据")
        self.city = CityBuilder.build(
            self.city_config,
            buildings=self.declared_buildings,
            waypoints=waypoints,
        )
        logger.info(
            "城市环境构建完成: %s, 建筑 %d 栋, 栅格占用率 %.2f%%",
            self.city_config.name,
            self.city.building_count,
            self.city.grid.blocked_ratio * 100,
        )
        return self.city

    def rebuild_network(self, registry: RepositoryRegistry) -> RouteNetwork:
        self.network = RouteNetwork.build(
            registry.waypoints.list(),
            registry.routes.list(),
        )
        logger.info(
            "航路网络构建完成: 节点 %d, 有向边 %d",
            self.network.graph.number_of_nodes(),
            self.network.graph.number_of_edges(),
        )
        return self.network

    def rebuild_all(self, registry: RepositoryRegistry) -> dict:
        with registry.lock:
            if self.city_config is None:
                raise ValueError("尚未加载城市配置")
            city = self.city or CityBuilder.build(
                self.city_config, buildings=self.declared_buildings,
                waypoints=registry.waypoints.list(),
            )
            network = RouteNetwork.build(registry.waypoints.list(), registry.routes.list())
            violations = network.validate_against_city(city)
            if violations:
                logger.warning("发现 %d 个航段穿越建筑", len(violations))
            self.city, self.network = city, network
            self.version += 1
            return {
                "buildings": city.building_count,
                "network_nodes": network.graph.number_of_nodes(),
                "network_edges": network.graph.number_of_edges(),
                "blocking_segments": violations,
            }
