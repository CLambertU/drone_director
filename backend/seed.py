"""Demo 种子数据加载。

种子数据全部为声明式 JSON（data/demo_seed.json），经同一套 Pydantic 模型
校验后入库——不允许在代码中硬编码任何“演示结果”。
城市建筑可在 JSON 中显式声明，也可由 CityBuilder 按 city 配置程序化生成。
"""

from __future__ import annotations

import json
from pathlib import Path

from backend.logging_config import get_logger
from core.models import (
    Aircraft,
    AirRoute,
    AirspaceRestriction,
    Building,
    CityConfig,
    Event,
    Mission,
    Weather,
    Waypoint,
)
from core.repository import RepositoryRegistry

logger = get_logger(__name__)

DEFAULT_SEED_PATH = Path(__file__).resolve().parent.parent / "data" / "demo_seed.json"

# 加载顺序即外键依赖顺序：航路点 -> 航路 -> 飞行器 -> 任务
_LOAD_ORDER: tuple[tuple[str, type], ...] = (
    ("waypoints", Waypoint),
    ("routes", AirRoute),
    ("aircraft", Aircraft),
    ("missions", Mission),
    ("weather", Weather),
    ("restrictions", AirspaceRestriction),
    ("events", Event),
)


class SeedBundle:
    """解析后的种子数据包。"""

    def __init__(
        self,
        entities: dict[str, list],
        city_config: CityConfig | None,
        buildings: list[Building],
    ) -> None:
        self.entities = entities
        self.city_config = city_config
        self.buildings = buildings


def read_seed_bundle(seed_path: str | Path | None = None) -> SeedBundle:
    path = Path(seed_path) if seed_path else DEFAULT_SEED_PATH
    if not path.exists():
        raise FileNotFoundError(f"种子数据文件不存在: {path}")

    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("种子数据根节点必须是 JSON 对象")

    entities: dict[str, list] = {}
    for key, model_type in _LOAD_ORDER:
        if not isinstance(raw.get(key, []), list):
            raise ValueError(f"种子数据 {key} 必须是 JSON 数组")
        entities[key] = [model_type.model_validate(item) for item in raw.get(key, [])]

    city_config = CityConfig.model_validate(raw["city"]) if raw.get("city") else None
    if not isinstance(raw.get("buildings", []), list):
        raise ValueError("种子数据 buildings 必须是 JSON 数组")
    buildings = [Building.model_validate(b) for b in raw.get("buildings", [])]

    bundle = SeedBundle(entities, city_config, buildings)
    validate_seed_bundle(bundle)
    return bundle


def validate_seed_bundle(bundle: SeedBundle) -> None:
    """先验证完整引用图，任何错误均发生在清空已有数据之前。"""
    ids: dict[str, set[str]] = {}
    for key, items in {**bundle.entities, "buildings": bundle.buildings}.items():
        ids[key] = {item.id for item in items}
        if len(ids[key]) != len(items):
            raise ValueError(f"种子数据 {key} 中存在重复 ID")
    for route in bundle.entities["routes"]:
        sequence = route.waypoint_ids or [route.start, route.end]
        referenced = {route.start, route.end, *route.waypoint_ids}
        missing = referenced - ids["waypoints"]
        if missing:
            raise ValueError(f"航路 {route.id} 引用了不存在的航路点: {sorted(missing)}")
        if route.start == route.end:
            raise ValueError(f"航路 {route.id} 起点与终点不能相同")
        if any(start == end for start, end in zip(sequence, sequence[1:])):
            raise ValueError(f"航路 {route.id} 相邻航路点不能相同")
        if route.waypoint_ids and (
            route.waypoint_ids[0] != route.start or route.waypoint_ids[-1] != route.end
        ):
            raise ValueError(f"航路 {route.id} 航点序列必须从 start 开始、以 end 结束")
    for mission in bundle.entities["missions"]:
        if mission.aircraft_id is not None and mission.aircraft_id not in ids["aircraft"]:
            raise ValueError(f"任务 {mission.id} 引用了不存在的飞行器: {mission.aircraft_id}")
        if mission.route_id is not None and mission.route_id not in ids["routes"]:
            raise ValueError(f"任务 {mission.id} 引用了不存在的航路: {mission.route_id}")


def replace_seed_entities(registry: RepositoryRegistry, bundle: SeedBundle) -> dict[str, int]:
    """替换实体，调用者的外层事务可以继续构建环境并一起回滚。"""
    with registry.transaction():
        registry.reset()
        for key, items in bundle.entities.items():
            repo = registry.all_repos()[key]
            for item in items:
                repo.add(item)
    return {key: len(items) for key, items in bundle.entities.items()}


def load_seed(
    registry: RepositoryRegistry,
    seed_path: str | Path | None = None,
) -> dict[str, int]:
    """仅加载实体数据到仓储并重置（环境构建由 EnvironmentService 负责）。"""
    bundle = read_seed_bundle(seed_path)

    counts = replace_seed_entities(registry, bundle)
    logger.info("种子实体加载完成: %s", counts)
    return counts
