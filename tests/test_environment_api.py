"""城市环境与航路网络接口测试。"""

from __future__ import annotations


def test_environment_requires_seed(client):
    assert client.get("/api/environment/summary").status_code == 409
    assert client.get("/api/environment/route-network").status_code == 409


def test_environment_summary_after_seed(client):
    client.post("/api/system/seed")
    resp = client.get("/api/environment/summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["name"] == "天枢市"
    assert body["building_count"] > 50
    assert body["grid"]["resolution"] == 10
    assert 0 < body["grid"]["blocked_ratio"] < 1
    assert body["origin"]["latitude"] == 30.5728


def test_buildings_endpoint(client):
    client.post("/api/system/seed")
    buildings = client.get("/api/environment/buildings").json()
    assert len(buildings) > 50
    b0 = buildings[0]
    assert {"id", "footprint", "height"} <= set(b0)
    assert b0["height"] > 0


def test_route_network_endpoint(client):
    client.post("/api/system/seed")
    data = client.get("/api/environment/route-network").json()
    assert len(data["nodes"]) == 11
    # 6 条走廊展开为 12 个双向航段 = 24 条有向边
    assert len(data["edges"]) == 24
    edge = data["edges"][0]
    assert edge["route_ids"]
    assert edge["distance"] > 0
    assert "position" in data["nodes"][0]


def test_validation_endpoint(client):
    client.post("/api/system/seed")
    result = client.get("/api/environment/validation").json()
    assert result["blocking_segment_count"] == 0
    assert result["violations"] == []


def test_rebuild_after_waypoint_change(client):
    client.post("/api/system/seed")
    # 新增孤立航路点后重建，节点数应 +1
    client.post(
        "/api/waypoints",
        json={
            "id": "WP_NEW",
            "type": "waypoint",
            "position": {"x": 500, "y": 1500, "z": 120},
        },
    )
    resp = client.post("/api/environment/rebuild")
    assert resp.status_code == 200
    assert resp.json()["network_nodes"] == 12
    data = client.get("/api/environment/route-network").json()
    assert any(n["id"] == "WP_NEW" for n in data["nodes"])
