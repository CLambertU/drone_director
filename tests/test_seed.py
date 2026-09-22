"""种子数据与系统接口测试。"""

from __future__ import annotations


def test_seed_loads_demo_data(client):
    resp = client.post("/api/system/seed")
    assert resp.status_code == 200
    result = resp.json()
    counts = result["entities"]
    assert counts["waypoints"] == 11
    assert counts["routes"] == 6
    assert counts["aircraft"] == 8
    assert counts["missions"] == 3
    assert counts["restrictions"] == 1
    assert counts["weather"] == 1

    # 环境同步构建
    env = result["environment"]
    assert env["buildings"] > 50
    assert env["network_nodes"] == 11
    assert env["network_edges"] == 24
    # 演示城市的走廊不允许穿越建筑
    assert env["blocking_segments"] == []

    # summary 与种子数量一致
    summary = client.get("/api/system/summary").json()
    assert summary["waypoints"] == 11
    assert summary["aircraft"] == 8


def test_seed_resets_previous_data(client):
    client.post(
        "/api/aircraft",
        json={"position": {"x": 0, "y": 0, "z": 100}},
    )
    assert len(client.get("/api/aircraft").json()) == 1

    client.post("/api/system/seed")
    # 种子加载会清空旧数据，固定为 8 架
    assert len(client.get("/api/aircraft").json()) == 8


def test_reset_clears_everything(client):
    client.post("/api/system/seed")
    client.post("/api/system/reset")
    summary = client.get("/api/system/summary").json()
    assert sum(summary.values()) == 0

    # 环境也被清空，访问环境接口返回 409
    assert client.get("/api/environment/summary").status_code == 409


def test_seed_route_references_exist(client):
    """种子数据的航路引用必须都能在航路点表中找到（演示数据自洽性）。"""
    client.post("/api/system/seed")
    waypoint_ids = {w["id"] for w in client.get("/api/waypoints").json()}
    for route in client.get("/api/routes").json():
        assert route["start"] in waypoint_ids
        assert route["end"] in waypoint_ids
        for wp in route["waypoint_ids"]:
            assert wp in waypoint_ids
