import pytest


def test_plan_returns_actual_cost_and_avoids_restriction(client):
    client.post("/api/system/seed")
    response = client.post("/api/planning/path", json={"source": "WP01", "target": "WP09"})
    assert response.status_code == 200
    result = response.json()
    assert "WP05" not in result["node_ids"]  # active central restriction
    assert result["distance_m"] == pytest.approx(4000)
    assert result["total_cost"] == pytest.approx(sum(result["cost_breakdown"].values()))
    assert result["environment_version"] >= 1


def test_planning_explains_unreachable_and_invalid_weights(client):
    client.post("/api/system/seed")
    response = client.post("/api/planning/path", json={"source": "WP01", "target": "WP05"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "unsafe_endpoint"
    assert client.post("/api/planning/path", json={
        "source": "WP01", "target": "WP09", "weights": {"risk": -1},
    }).status_code == 422
