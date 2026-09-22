"""SQLite 仓储；使用模型 JSON 保留领域类型，事务由注册表统一管理。"""

from __future__ import annotations

import sqlite3
from threading import RLock
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class SQLiteRepository(Generic[T]):
    def __init__(
        self, model_type: type[T], collection: str,
        connection: sqlite3.Connection, lock: RLock,
    ) -> None:
        self._model_type = model_type
        self._collection = collection
        self._connection = connection
        self._lock = lock

    def _serialize(self, item: T) -> tuple[T, str]:
        validated = self._model_type.model_validate(item.model_dump(round_trip=True))
        return validated, validated.model_dump_json(round_trip=True)

    def add(self, item: T) -> T:
        with self._lock:
            validated, payload = self._serialize(item)
            try:
                self._connection.execute(
                    "INSERT INTO entities(collection, id, payload) VALUES (?, ?, ?)",
                    (self._collection, validated.id, payload),
                )
            except sqlite3.IntegrityError:
                raise ValueError(
                    f"{self._model_type.__name__} id 已存在: {validated.id}"
                ) from None
            return validated

    def get(self, item_id: str) -> T:
        with self._lock:
            row = self._connection.execute(
                "SELECT payload FROM entities WHERE collection = ? AND id = ?",
                (self._collection, item_id),
            ).fetchone()
            if row is None:
                raise KeyError(f"{self._model_type.__name__} 不存在: {item_id}")
            return self._model_type.model_validate_json(row[0])

    def list(self) -> list[T]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT payload FROM entities WHERE collection = ? ORDER BY rowid",
                (self._collection,),
            ).fetchall()
            return [self._model_type.model_validate_json(row[0]) for row in rows]

    def update(self, item: T) -> T:
        with self._lock:
            validated, payload = self._serialize(item)
            result = self._connection.execute(
                "UPDATE entities SET payload = ? WHERE collection = ? AND id = ?",
                (payload, self._collection, validated.id),
            )
            if not result.rowcount:
                raise KeyError(f"{self._model_type.__name__} 不存在: {validated.id}")
            return validated

    def upsert(self, item: T) -> T:
        with self._lock:
            validated, payload = self._serialize(item)
            self._connection.execute(
                "INSERT INTO entities(collection, id, payload) VALUES (?, ?, ?) "
                "ON CONFLICT(collection, id) DO UPDATE SET payload = excluded.payload",
                (self._collection, validated.id, payload),
            )
            return validated

    def delete(self, item_id: str) -> None:
        with self._lock:
            result = self._connection.execute(
                "DELETE FROM entities WHERE collection = ? AND id = ?",
                (self._collection, item_id),
            )
            if not result.rowcount:
                raise KeyError(f"{self._model_type.__name__} 不存在: {item_id}")

    def exists(self, item_id: str) -> bool:
        with self._lock:
            return self._connection.execute(
                "SELECT 1 FROM entities WHERE collection = ? AND id = ?",
                (self._collection, item_id),
            ).fetchone() is not None

    def count(self) -> int:
        with self._lock:
            return self._connection.execute(
                "SELECT COUNT(*) FROM entities WHERE collection = ?",
                (self._collection,),
            ).fetchone()[0]

    def clear(self) -> None:
        with self._lock:
            self._connection.execute(
                "DELETE FROM entities WHERE collection = ?", (self._collection,),
            )
