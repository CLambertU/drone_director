"""实体 CRUD 接口集成测试。"""

from __future__ import annotations

AIRCRAFT_PAYLOAD = {
    "name": "测试机-01",
    "position": {"x": 100, "y": 200, "z": 120},
    "speed": 0,
    "heading": 90,
    "status": "grounded",
    "battery": 0.8,
    "priority": 3,
}

WAYPOINT_PAYLOAD = {
    "id": "WP-T1",
    "name": "测试航路点",
    "type": "vertiport",
    "position": {"x": 0, "y": 0, "z": 120},
    "capacity": 5,
}

EVENT_PAYLOAD = {
    "type": "event_info",
    "severity": "warning",
    "description": "RT06 流量超容量",
    "related_id": "RT06",
}


def test_aircraft_crud_flow(client):
    # 列表为空
    assert client.get("/api/aircraft").json() == []

    # 创建（服务端生成 id，并返回只读 altitude）
    resp = client.post("/api/aircraft", json=AIRCRAFT_PAYLOAD)
    assert resp.status_code == 201
    created = resp.json()
    aircraft_id = created["id"]
    assert aircraft_id.startswith("AC")
    assert created["altitude"] == 120

    # 列表 / 详情
    assert len(client.get("/api/aircraft").json()) == 1
    detail = client.get(f"/api/aircraft/{aircraft_id}")
    assert detail.status_code == 200
    assert detail.json()["name"] == "测试机-01"

    # 更新
    updated = client.put(
        f"/api/aircraft/{aircraft_id}",
        json={**AIRCRAFT_PAYLOAD, "status": "en_route", "battery": 0.5},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "en_route"

    # 删除后 404
    assert client.delete(f"/api/aircraft/{aircraft_id}").status_code == 204
    assert client.get(f"/api/aircraft/{aircraft_id}").status_code == 404


def test_create_aircraft_validation_error(client):
    bad = {**AIRCRAFT_PAYLOAD, "battery": 9.9}
    resp = client.post("/api/aircraft", json=bad)
    assert resp.status_code == 422


def test_get_missing_returns_404_body(client):
    resp = client.get("/api/aircraft/NO_SUCH_ID")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "not_found"


def test_duplicate_id_conflicts(client):
    client.post("/api/waypoints", json=WAYPOINT_PAYLOAD)
    resp = client.post("/api/waypoints", json=WAYPOINT_PAYLOAD)
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "conflict"


def test_create_event_with_defaults(client):
    resp = client.post("/api/events", json=EVENT_PAYLOAD)
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"].startswith("EV")
    assert body["handled"] is True
    assert body["timestamp"] is not None


def test_create_mission_and_list(client):
    aircraft_id = client.post("/api/aircraft", json=AIRCRAFT_PAYLOAD).json()["id"]
    payload = {
        "aircraft_id": aircraft_id,
        "origin": {"x": 0, "y": 0, "z": 120},
        "destination": {"x": 500, "y": 500, "z": 120},
        "priority": 2,
    }
    resp = client.post("/api/missions", json=payload)
    assert resp.status_code == 201
    assert resp.json()["status"] == "pending"
    assert len(client.get("/api/missions").json()) == 1
