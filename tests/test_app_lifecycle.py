from fastapi.testclient import TestClient

from backend.app import create_app


def test_restart_restores_entities_and_exact_city(tmp_path):
    db = tmp_path / "restart.sqlite3"
    with TestClient(create_app(database_path=db, seed_on_startup=False)) as client:
        assert client.post("/api/system/seed").status_code == 200
        city = client.get("/api/environment/buildings").json()
        response = client.post("/api/aircraft", json={
            "id": "PERSIST", "position": {"x": 10, "y": 10, "z": 120},
        })
        assert response.status_code == 201
        assert response.headers["X-Request-ID"]
    with TestClient(create_app(database_path=db, seed_on_startup=False)) as client:
        assert client.get("/api/aircraft/PERSIST").status_code == 200
        assert client.get("/api/environment/buildings").json() == city
        assert client.get("/api/environment/route-network").status_code == 200


def test_reset_stays_empty_after_restart(tmp_path):
    db = tmp_path / "reset.sqlite3"
    with TestClient(create_app(database_path=db, seed_on_startup=True)) as client:
        assert client.post("/api/system/reset").status_code == 200
    with TestClient(create_app(database_path=db, seed_on_startup=False)) as client:
        assert client.get("/api/aircraft").json() == []
        assert client.get("/api/environment/summary").status_code == 409
