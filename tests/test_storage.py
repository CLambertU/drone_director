"""持久化、跨实体回滚、可变对象隔离与种子加载失败恢复。"""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from backend.seed import DEFAULT_SEED_PATH, load_seed
from backend.services.demo_service import seed_demo
from backend.services.environment_service import EnvironmentService
from core.models import Aircraft, Building, CityConfig, Position3D, Waypoint
from core.repository import create_registry


@pytest.fixture(params=["memory", "sqlite"])
def registry(request, tmp_path):
    value = create_registry(tmp_path / "test.sqlite3" if request.param == "sqlite" else None)
    yield value
    value.close()


def aircraft(ac_id="AC1"):
    return Aircraft(id=ac_id, position=Position3D(x=1, y=2, z=120))


def test_backend_crud_contract_and_duplicate_does_not_abort_outer_transaction(registry):
    with registry.transaction():
        registry.aircraft.add(aircraft())
        with pytest.raises(ValueError):
            registry.aircraft.add(aircraft())
        registry.aircraft.upsert(aircraft("AC2"))
        registry.aircraft.upsert(aircraft().model_copy(update={"battery": 0.5}))
    assert registry.aircraft.count() == 2
    assert registry.aircraft.get("AC1").battery == 0.5
    registry.aircraft.delete("AC1")
    assert not registry.aircraft.exists("AC1")
    for operation in (
        lambda: registry.aircraft.get("AC1"),
        lambda: registry.aircraft.delete("AC1"),
        lambda: registry.aircraft.update(aircraft()),
    ):
        with pytest.raises(KeyError):
            operation()
    assert [item.id for item in registry.aircraft.list()] == ["AC2"]


def test_repository_isolates_inputs_and_all_returned_objects(registry):
    source = aircraft()
    returned = registry.aircraft.add(source)
    source.position.x = 77
    returned.position.x = 88
    queried = registry.aircraft.get("AC1")
    queried.position.x = 99
    registry.aircraft.list()[0].position.x = 100
    assert registry.aircraft.get("AC1").position.x == 1

    updated = registry.aircraft.update(source)
    updated.position.x = 200
    source.position.x = 300
    assert registry.aircraft.get("AC1").position.x == 77

    with pytest.raises(ValidationError):
        registry.aircraft.update(source.model_copy(update={"battery": 9}))
    assert registry.aircraft.get("AC1").battery == 1


def test_transaction_rolls_back_entities_and_metadata_after_reset(registry):
    registry.aircraft.add(aircraft())
    registry.set_metadata("environment", {"buildings": [{"id": "original"}]})
    with pytest.raises(RuntimeError, match="build failed"):
        with registry.transaction():
            registry.reset()
            registry.aircraft.add(aircraft("AC2"))
            registry.waypoints.add(Waypoint(id="WP1", position=Position3D(x=0, y=0, z=120)))
            registry.set_metadata("environment", {"buildings": []})
            raise RuntimeError("build failed")
    assert [value.id for value in registry.aircraft.list()] == ["AC1"]
    assert registry.waypoints.count() == 0
    assert registry.get_metadata("environment") == {"buildings": [{"id": "original"}]}


def test_inner_rollback_preserves_outer_transaction_and_metadata_is_copied(registry):
    source = {"nested": [1]}
    with registry.transaction():
        registry.aircraft.add(aircraft())
        with pytest.raises(ValueError):
            with registry.transaction():
                registry.aircraft.delete("AC1")
                registry.aircraft.add(aircraft("AC2"))
                raise ValueError("cancel nested change")
        registry.set_metadata("settings", source)
    source["nested"].append(2)
    registry.get_metadata("settings")["nested"].append(3)
    assert registry.aircraft.exists("AC1")
    assert not registry.aircraft.exists("AC2")
    assert registry.get_metadata("settings") == {"nested": [1]}


def test_sqlite_reopen_preserves_entities_and_exact_generated_environment(tmp_path):
    path = tmp_path / "persistent.sqlite3"
    registry = create_registry(path)
    environment = EnvironmentService()
    seed_demo(registry, environment)
    registry.aircraft.update(registry.aircraft.get("AC01").model_copy(update={"battery": 0.25}))
    original_buildings = [item.model_dump(round_trip=True) for item in environment.city.buildings]
    original_mission = registry.missions.get("MS01")
    registry.close()

    restarted = create_registry(path)
    try:
        assert restarted.aircraft.get("AC01").battery == 0.25
        assert restarted.missions.get("MS01") == original_mission
        saved = restarted.get_metadata("environment")
        restored = EnvironmentService()
        restored.apply_seed(
            CityConfig.model_validate(saved["city_config"]),
            [Building.model_validate(item) for item in saved["buildings"]],
            restarted,
        )
        assert [item.model_dump(round_trip=True) for item in restored.city.buildings] == original_buildings
        assert restored.network.graph.number_of_edges() == environment.network.graph.number_of_edges()
        restarted.reset()
    finally:
        restarted.close()
    cleared = create_registry(path)
    try:
        assert sum(repo.count() for repo in cleared.all_repos().values()) == 0
        assert cleared.get_metadata("environment") is None
    finally:
        cleared.close()


@pytest.mark.parametrize("fault", ["missing_aircraft", "missing_waypoint", "duplicate_id", "missing_city"])
def test_bad_seed_keeps_previous_data_and_environment(registry, tmp_path, fault):
    environment = EnvironmentService()
    seed_demo(registry, environment)
    previous_city, previous_network = environment.city, environment.network
    previous_metadata = registry.get_metadata("environment")
    registry.aircraft.update(registry.aircraft.get("AC01").model_copy(update={"battery": 0.25}))
    raw = json.loads(DEFAULT_SEED_PATH.read_text(encoding="utf-8"))
    if fault == "missing_aircraft":
        raw["missions"][0]["aircraft_id"] = "absent"
    elif fault == "missing_waypoint":
        raw["routes"][0]["start"] = "absent"
        raw["routes"][0]["waypoint_ids"][0] = "absent"
    elif fault == "duplicate_id":
        raw["aircraft"].append(raw["aircraft"][0])
    else:
        del raw["city"]
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError):
        seed_demo(registry, environment, path)
    assert registry.aircraft.get("AC01").battery == 0.25
    assert environment.city is previous_city
    assert environment.network is previous_network
    assert registry.get_metadata("environment") == previous_metadata


def test_entity_only_seed_validates_before_reset(registry, tmp_path):
    registry.aircraft.add(aircraft())
    raw = json.loads(DEFAULT_SEED_PATH.read_text(encoding="utf-8"))
    raw["missions"][0]["route_id"] = "missing"
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="missing"):
        load_seed(registry, path)
    assert registry.aircraft.exists("AC1")
