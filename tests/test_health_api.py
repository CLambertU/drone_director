"""健康检查接口测试。"""

from __future__ import annotations


def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "version" in body
    assert "time" in body


def test_openapi_docs_available(client):
    assert client.get("/openapi.json").status_code == 200
    assert client.get("/docs").status_code == 200
