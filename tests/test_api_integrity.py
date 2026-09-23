"""API trust-boundary validation and transaction/derived-state regressions."""

import pytest

from core.models import Event, EventType
from simulation.environment.route_network import RouteNetwork


def make_route(client):
    for waypoint_id, x in [("A", 0), ("B", 100)]:
        response = client.post("/api/waypoints", json={
            "id": waypoint_id, "position": {"x": x, "y": 0, "z": 120}})
        assert response.status_code == 201
    payload = {"id": "R", "start": "A", "end": "B"}
    assert client.post("/api/routes", json=payload).status_code == 201
    return payload


def test_orphan_references_and_route_sequence_rejected(client):
    response = client.post("/api/missions", json={
        "aircraft_id": "missing", "origin": {}, "destination": {"x": 10}})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_reference"
    response = client.post("/api/routes", json={"start": "missing", "end": "also-missing"})
    assert response.status_code == 422
    assert client.get("/api/routes").json() == []
    payload = make_route(client)
    for sequence in [["B", "A"], ["A"], ["A", "A", "B"], ["A", "missing", "B"]]:
        response = client.put("/api/routes/R", json={**payload, "waypoint_ids": sequence})
        assert response.status_code == 422
    assert client.get("/api/routes/R").json()["waypoint_ids"] == []


def test_dependent_deletes_are_rejected_until_dependents_removed(client):
    make_route(client)
    client.post("/api/aircraft", json={"id": "AC", "position": {}})
    mission = {"id": "M", "aircraft_id": "AC", "route_id": "R", "origin": {}, "destination": {}}
    assert client.post("/api/missions", json=mission).status_code == 201
    for url in ["/api/aircraft/AC", "/api/routes/R", "/api/waypoints/A"]:
        response = client.delete(url)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "resource_in_use"
    assert client.delete("/api/missions/M").status_code == 204
    assert client.delete("/api/aircraft/AC").status_code == 204
    assert client.delete("/api/routes/R").status_code == 204
    assert client.delete("/api/waypoints/A").status_code == 204
    assert client.get("/api/environment/route-network").json()["edges"] == []


def test_put_id_and_protected_fields(client):
    client.post("/api/aircraft", json={"id": "AC", "position": {}})
    response = client.put("/api/aircraft/AC", json={"id": "OTHER", "position": {}})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "id_mismatch"
    assert client.put("/api/aircraft/AC", json={"position": {"z": 20}}).status_code == 200
    assert client.get("/api/aircraft/AC").json()["altitude"] == 20
    cases = [
        ("/api/aircraft", {"position": {}, "altitude": 10}),
        ("/api/events", {"type": "event_info", "handled": True}),
        ("/api/events", {"type": "event_info", "timestamp": "2026-01-01T00:00:00Z"}),
        ("/api/routes", {"start": "A", "end": "B", "distance": 100}),
        ("/api/routes", {"start": "A", "end": "B", "current_flow": 5}),
    ]
    for url, payload in cases:
        assert client.post(url, json=payload).status_code == 422


def test_network_refreshes_on_crud_without_city_regeneration(client):
    payload = make_route(client)
    environment = client.app.state.environment
    old_city = environment.city
    old_version = environment.version
    assert client.get("/api/routes/R").json()["distance"] == 100
    assert client.put("/api/routes/R", json={**payload, "status": "closed"}).status_code == 200
    edges = client.get("/api/environment/route-network").json()["edges"]
    assert all(edge["status"] == "closed" for edge in edges)
    assert client.put("/api/waypoints/B", json={"position": {"x": 200, "z": 120}}).status_code == 200
    assert client.get("/api/routes/R").json()["distance"] == 200
    assert client.get("/api/environment/route-network").json()["edges"][0]["distance"] == 200
    assert environment.city is old_city
    assert environment.version == old_version + 2


def test_graph_build_failure_rolls_back_all_entities(client, monkeypatch):
    make_route(client)
    environment = client.app.state.environment
    previous_network = environment.network

    def broken_build(*args, **kwargs):
        raise RuntimeError("graph construction failed")

    monkeypatch.setattr(RouteNetwork, "build", broken_build)
    with pytest.raises(RuntimeError, match="graph construction failed"):
        client.put("/api/waypoints/B", json={"position": {"x": 300, "z": 120}})
    assert client.get("/api/waypoints/B").json()["position"]["x"] == 100
    assert client.get("/api/routes/R").json()["distance"] == 100
    assert environment.network is previous_network


def test_errors_share_envelope_and_validator_context_is_serializable(client):
    responses = [
        client.get("/api/does-not-exist"),
        client.patch("/api/aircraft"),
        client.get("/api/environment/summary"),
        client.post("/api/aircraft", json={"position": {}, "speed": 30, "max_speed": 20}),
        client.post("/api/restrictions", json={
            "polygon": {"points": [{"x": 0}, {"x": 1}, {"y": 1}]},
            "min_altitude": 200, "max_altitude": 100}),
    ]
    assert [response.status_code for response in responses] == [404, 405, 409, 422, 422]
    for response in responses:
        assert set(response.json()) == {"error"}
        assert set(response.json()["error"]) == {"code", "message", "details"}


def test_internal_event_state_preserved_and_handled_event_immutable(client):
    response = client.post("/api/events", json={"type": "event_info"})
    created = response.json()
    updated = client.put(f"/api/events/{created['id']}", json={"type": "event_info", "description": "updated"})
    assert created["handled"] is True
    assert updated.status_code == 409
    assert client.get(f"/api/events/{created['id']}").json()["timestamp"] == created["timestamp"]
    event = Event(id="handled", type=EventType.INFO, handled=True)
    client.app.state.registry.events.add(event)
    assert client.put("/api/events/handled", json={"type": "event_info"}).status_code == 409
    assert client.delete("/api/events/handled").status_code == 409
