def test_generate_connects_safe_emergency_bays_and_is_idempotent(client):
    assert client.post("/api/system/seed").status_code == 200
    response = client.post("/api/environment/generate-network", json={"neighbor_count": 3})
    assert response.status_code == 200
    result = response.json()
    assert result["generated_routes"] > 0
    assert "EB01" not in result["isolated_waypoints"]
    assert "EB02" not in result["isolated_waypoints"]
    count = len(client.get("/api/routes").json())
    assert client.post("/api/environment/generate-network", json={}).status_code == 200
    assert len(client.get("/api/routes").json()) == count


def test_generation_requires_city(client):
    assert client.post("/api/environment/generate-network", json={}).status_code == 409
