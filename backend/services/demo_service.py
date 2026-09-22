"""Demo 播种编排：实体入库 + 城市/航路网构建，一步完成。"""

from __future__ import annotations

from pathlib import Path

from backend.logging_config import get_logger
from backend.seed import read_seed_bundle, replace_seed_entities
from backend.services.environment_service import EnvironmentService
from core.repository import RepositoryRegistry

logger = get_logger(__name__)


def seed_demo(
    registry: RepositoryRegistry,
    environment: EnvironmentService,
    seed_path: str | Path | None = None,
) -> dict:
    """重置仓储、加载种子实体，并重建城市环境与航路网络。"""
    bundle = read_seed_bundle(seed_path)

    # Build into a separate service: parsing, building or committing failure must
    # leave both the database and the currently visible environment intact.
    staged = EnvironmentService()
    with registry.lock:
        with registry.transaction():
            counts = replace_seed_entities(registry, bundle)
            env_result = staged.apply_seed(bundle.city_config, bundle.buildings or None, registry)
            registry.set_metadata("environment", {
                "city_config": staged.city_config.model_dump(mode="json", round_trip=True),
                "buildings": [
                    building.model_dump(mode="json", round_trip=True)
                    for building in staged.city.buildings
                ],
            })
        environment.install_from(staged)
    logger.info("Demo 播种完成: 实体 %s / 环境 %s", counts, env_result)

    return {"entities": counts, "environment": env_result}
