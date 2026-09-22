"""内存仓储单元测试。"""

from __future__ import annotations

import threading

import pytest

from core.models import Aircraft, Position3D
from core.repository import InMemoryRepository, RepositoryRegistry, create_registry


def make_aircraft(ac_id: str) -> Aircraft:
    return Aircraft(id=ac_id, position=Position3D(x=1, y=2, z=120))


def test_add_get_update_delete():
    repo: InMemoryRepository[Aircraft] = InMemoryRepository(Aircraft)
    ac = make_aircraft("AC1")
    repo.add(ac)
    assert repo.exists("AC1")
    assert repo.count() == 1
    assert repo.get("AC1").position.x == 1

    repo.update(ac.model_copy(update={"battery": 0.2}))
    assert repo.get("AC1").battery == pytest.approx(0.2)

    repo.delete("AC1")
    assert not repo.exists("AC1")


def test_add_duplicate_raises():
    repo = InMemoryRepository(Aircraft)
    repo.add(make_aircraft("AC1"))
    with pytest.raises(ValueError):
        repo.add(make_aircraft("AC1"))


def test_get_missing_raises_keyerror():
    repo = InMemoryRepository(Aircraft)
    with pytest.raises(KeyError):
        repo.get("MISSING")


def test_registry_reset():
    registry = create_registry()
    registry.aircraft.add(make_aircraft("AC1"))
    assert registry.aircraft.count() == 1
    registry.reset()
    assert registry.aircraft.count() == 0


def test_concurrent_access_is_thread_safe():
    repo = InMemoryRepository(Aircraft)

    def worker(start: int) -> None:
        for i in range(start, start + 100):
            repo.upsert(make_aircraft(f"AC{i}"))

    threads = [threading.Thread(target=worker, args=(i * 100,)) for i in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert repo.count() == 400
