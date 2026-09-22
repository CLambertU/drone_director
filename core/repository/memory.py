"""供测试与临时场景使用的内存仓储；读写值与调用者隔离。"""

from __future__ import annotations

from threading import RLock
from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class InMemoryRepository(Generic[T]):
    def __init__(self, model_type: type[T], lock: RLock | None = None) -> None:
        self._model_type = model_type
        self._items: dict[str, T] = {}
        self._lock = lock if lock is not None else RLock()

    def _validated_copy(self, item: T) -> T:
        # Revalidate even model_copy(update=...), which bypasses Pydantic validation.
        return self._model_type.model_validate(item.model_dump(round_trip=True))

    def add(self, item: T) -> T:
        with self._lock:
            if item.id in self._items:
                raise ValueError(f"{self._model_type.__name__} id 已存在: {item.id}")
            stored = self._validated_copy(item)
            self._items[stored.id] = stored
            return stored.model_copy(deep=True)

    def get(self, item_id: str) -> T:
        with self._lock:
            try:
                return self._items[item_id].model_copy(deep=True)
            except KeyError:
                raise KeyError(
                    f"{self._model_type.__name__} 不存在: {item_id}"
                ) from None

    def list(self) -> list[T]:
        with self._lock:
            return [item.model_copy(deep=True) for item in self._items.values()]

    def update(self, item: T) -> T:
        with self._lock:
            if item.id not in self._items:
                raise KeyError(
                    f"{self._model_type.__name__} 不存在: {item.id}"
                )
            stored = self._validated_copy(item)
            self._items[stored.id] = stored
            return stored.model_copy(deep=True)

    def upsert(self, item: T) -> T:
        with self._lock:
            stored = self._validated_copy(item)
            self._items[stored.id] = stored
            return stored.model_copy(deep=True)

    def delete(self, item_id: str) -> None:
        with self._lock:
            if item_id not in self._items:
                raise KeyError(
                    f"{self._model_type.__name__} 不存在: {item_id}"
                )
            del self._items[item_id]

    def exists(self, item_id: str) -> bool:
        with self._lock:
            return item_id in self._items

    def count(self) -> int:
        with self._lock:
            return len(self._items)

    def clear(self) -> None:
        with self._lock:
            self._items.clear()
