"""pytest 公共夹具。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app import create_app


@pytest.fixture
def client() -> TestClient:
    # 每个测试使用全新的应用与内存仓储，互不污染
    app = create_app(seed_on_startup=False, database_path=None)
    with TestClient(app) as c:
        yield c
