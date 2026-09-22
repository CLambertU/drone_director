"""共享锁、跨实体事务与可切换的 SQLite / 内存仓储。"""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from threading import RLock
from typing import Any, Iterator, TypeVar

from pydantic import BaseModel

from core.models import (
    Aircraft, AirRoute, AirspaceRestriction, Event, Mission, Weather, Waypoint,
)
from core.repository.base import Repository
from core.repository.memory import InMemoryRepository
from core.repository.sqlite import SQLiteRepository

T = TypeVar("T", bound=BaseModel)


class RepositoryRegistry:
    def __init__(self, database_path: str | Path | None = None) -> None:
        # ponytail: one writer lock suits the MVP; separate simulation ownership
        # and database pooling when measured request throughput requires it.
        self.lock = RLock()
        self._connection: sqlite3.Connection | None = None
        self._metadata: dict[str, Any] = {}
        self._transaction_counter = 0
        if database_path is not None:
            if str(database_path) != ":memory:":
                Path(database_path).parent.mkdir(parents=True, exist_ok=True)
            self._connection = sqlite3.connect(
                str(database_path), isolation_level=None, check_same_thread=False,
                timeout=5.0,
            )
            try:
                self._connection.execute("PRAGMA journal_mode = WAL")
                self._connection.execute("PRAGMA foreign_keys = ON")
                self._connection.execute(
                    "CREATE TABLE IF NOT EXISTS entities ("
                    "collection TEXT NOT NULL, id TEXT NOT NULL, payload TEXT NOT NULL, "
                    "PRIMARY KEY (collection, id))"
                )
                self._connection.execute(
                    "CREATE TABLE IF NOT EXISTS metadata ("
                    "key TEXT PRIMARY KEY, payload TEXT NOT NULL)"
                )
            except BaseException:
                self._connection.close()
                raise

        self.aircraft: Repository[Aircraft] = self._make_repo(Aircraft, "aircraft")
        self.waypoints: Repository[Waypoint] = self._make_repo(Waypoint, "waypoints")
        self.routes: Repository[AirRoute] = self._make_repo(AirRoute, "routes")
        self.missions: Repository[Mission] = self._make_repo(Mission, "missions")
        self.weather: Repository[Weather] = self._make_repo(Weather, "weather")
        self.restrictions: Repository[AirspaceRestriction] = self._make_repo(
            AirspaceRestriction, "restrictions",
        )
        self.events: Repository[Event] = self._make_repo(Event, "events")

    def _make_repo(self, model_type: type[T], collection: str) -> Repository[T]:
        if self._connection is not None:
            return SQLiteRepository(model_type, collection, self._connection, self.lock)
        return InMemoryRepository(model_type, self.lock)

    def all_repos(self) -> dict[str, Repository]:
        return {
            "aircraft": self.aircraft,
            "waypoints": self.waypoints,
            "routes": self.routes,
            "missions": self.missions,
            "weather": self.weather,
            "restrictions": self.restrictions,
            "events": self.events,
        }

    @contextmanager
    def transaction(self) -> Iterator[None]:
        """Atomic cross-repository operation; nested blocks roll back independently."""
        with self.lock:
            if self._connection is None:
                snapshots = {key: repo.list() for key, repo in self.all_repos().items()}
                metadata = deepcopy(self._metadata)
                try:
                    yield
                except BaseException:
                    for key, repo in self.all_repos().items():
                        repo.clear()
                        for item in snapshots[key]:
                            repo.add(item)
                    self._metadata = metadata
                    raise
            else:
                self._transaction_counter += 1
                savepoint = f"registry_{self._transaction_counter}"
                self._connection.execute(f"SAVEPOINT {savepoint}")
                try:
                    yield
                    self._connection.execute(f"RELEASE SAVEPOINT {savepoint}")
                except BaseException:
                    self._connection.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                    self._connection.execute(f"RELEASE SAVEPOINT {savepoint}")
                    raise

    def get_metadata(self, key: str, default: Any = None) -> Any:
        with self.lock:
            if self._connection is None:
                return deepcopy(self._metadata.get(key, default))
            row = self._connection.execute(
                "SELECT payload FROM metadata WHERE key = ?", (key,),
            ).fetchone()
            return json.loads(row[0]) if row else deepcopy(default)

    def set_metadata(self, key: str, value: Any) -> None:
        payload = json.dumps(value, ensure_ascii=False, allow_nan=False)
        with self.lock:
            if self._connection is None:
                self._metadata[key] = json.loads(payload)
            else:
                self._connection.execute(
                    "INSERT INTO metadata(key, payload) VALUES (?, ?) "
                    "ON CONFLICT(key) DO UPDATE SET payload = excluded.payload",
                    (key, payload),
                )

    def reset(self) -> None:
        with self.transaction():
            for repo in self.all_repos().values():
                repo.clear()
            self._metadata.clear()
            if self._connection is not None:
                self._connection.execute("DELETE FROM metadata")

    def close(self) -> None:
        with self.lock:
            if self._connection is not None:
                self._connection.close()


def create_registry(database_path: str | Path | None = None) -> RepositoryRegistry:
    return RepositoryRegistry(database_path=database_path)
