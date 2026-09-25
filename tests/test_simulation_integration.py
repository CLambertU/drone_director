"""Closed-loop contracts: scheduling, events, persistence and the live protocol."""

import random
from itertools import combinations

import pytest
from fastapi.testclient import TestClient

from algorithms.conflict_detection import ConflictThresholds, TrajectoryPoint, detect_conflicts
from algorithms.conflict_detection.continuous import _first_overlap
from backend.app import create_app
from backend.config.settings import Settings
from backend.services.environment_service import EnvironmentService
from core.models import AircraftStatus, Event, EventType, Polygon2D, Position2D, Position3D, Weather
from core.repository import create_registry
from simulation.engine import Engine
from simulation.aircraft.flight import FlightPlan
from simulation.engine.planning import _continuous_exit
from simulation.engine.safety import feasible
from simulation.environment.builder import rectangle_polygon


@pytest.fixture
def engine():
    registry = create_registry()
    value = Engine(registry, EnvironmentService(), Settings(_env_file=None))
    value.prepare_demo(8, 42)
    yield value
    registry.close()


def test_fixed_clock_and_actual_distance_ignore_playback_speed(engine):
    start = {key: a.position.model_copy() for key, a in engine.aircraft.items()}
    engine.set_speed(50)
    engine.step(2)
    assert engine.time_s == 2
    actual = sum(a.position.distance_to(start[key]) for key, a in engine.aircraft.items())
    assert engine.snapshot()["metrics"]["total_flight_distance_m"] == pytest.approx(actual)
    assert actual > 0
    assert all(a.battery < 1 for a in engine.aircraft.values())


def test_unresolved_immediate_conflict_stops_the_entire_requested_batch(engine):
    engine.demo_enabled = False
    engine.aircraft["UAV-002"].position = engine.aircraft["UAV-001"].position.model_copy()
    before = {key: a.position.model_copy() for key, a in engine.aircraft.items()}
    engine.running = True
    engine.step(5)
    assert not engine.running
    assert engine.time_s == 0
    assert {key: a.position for key, a in engine.aircraft.items()} == before
    assert engine.conflicts


def test_injected_closure_checks_separation_before_next_tick(engine):
    engine.demo_enabled = False
    engine.running = True
    engine.aircraft["UAV-002"].position = engine.aircraft["UAV-001"].position.model_copy()
    before = {key: a.position.model_copy() for key, a in engine.aircraft.items()}
    area = rectangle_polygon(2900, 240, 300, 150)
    event = engine.inject_event(Event(type=EventType.AIRSPACE_CLOSURE,
        payload={"polygon": area.model_dump(), "min_altitude": 0, "max_altitude": 300}))
    assert event.result["paused_for_safety"]
    assert event.result["residual_conflicts"] > 0
    assert not engine.running and engine.time_s == 0
    assert {key: a.position for key, a in engine.aircraft.items()} == before


def test_start_refuses_motion_when_current_separation_is_lost(engine):
    engine.demo_enabled = False
    engine.aircraft["UAV-002"].position = engine.aircraft["UAV-001"].position.model_copy()
    engine.start()
    assert not engine.running
    assert engine.time_s == 0
    assert engine.conflicts


def test_congestion_is_a_real_capacity_change_without_teleport(engine):
    route = max(engine.routes.values(), key=lambda r: r.current_flow)
    before = {key: a.position.model_copy() for key, a in engine.aircraft.items()}
    event = engine.inject_event(Event(type=EventType.ROUTE_CONGESTION, related_id=route.id,
                                     payload={"capacity": 1}))
    assert event.handled and event.processing_ms > 0
    assert engine.routes[route.id].capacity == 1
    assert event.result["affected_aircraft"]
    assert {key: a.position for key, a in engine.aircraft.items()} == before
    assert engine.registry.events.get(event.id).result == event.result


@pytest.mark.parametrize("event_type", [EventType.WEATHER, EventType.AIRSPACE_CLOSURE])
def test_area_event_replans_or_holds_every_affected_aircraft(engine, event_type):
    area = rectangle_polygon(2900, 240, 300, 150)
    payload = ({"affected_area": area.model_dump(), "precipitation": "thunderstorm"}
               if event_type == EventType.WEATHER else
               {"polygon": area.model_dump(), "min_altitude": 0, "max_altitude": 300})
    event = engine.inject_event(Event(type=event_type, payload=payload))
    assert event.result["affected_aircraft"]
    assert set(event.result["affected_aircraft"]) == set(event.result["replanned_aircraft"] + event.result["holding_aircraft"])
    for aircraft_id in event.result["replanned_aircraft"]:
        plan = engine.plans[aircraft_id]
        points = [engine.aircraft[aircraft_id].position, *plan.positions[plan.cursor:]]
        assert all(not area.intersects_segment(a.xy, b.xy) for a, b in zip(points, points[1:]))


@pytest.mark.parametrize("event_type", [EventType.WEATHER, EventType.AIRSPACE_CLOSURE])
def test_aircraft_caught_inside_new_area_exits_immediately_then_reroutes(engine, event_type):
    engine.demo_enabled = False
    engine.step(10)
    aircraft = engine.aircraft["UAV-001"]
    start = aircraft.position.model_copy()
    area = rectangle_polygon(start.x, start.y, 100, 80)
    payload = ({"affected_area": area.model_dump(), "precipitation": "thunderstorm"}
               if event_type == EventType.WEATHER else
               {"polygon": area.model_dump(), "min_altitude": 0, "max_altitude": 300})
    event = engine.inject_event(Event(type=event_type, payload=payload))
    assert aircraft.id in event.result["evacuating_aircraft"]
    assert aircraft.id not in event.result["holding_aircraft"]
    plan = engine.plans[aircraft.id]
    assert plan.egress_target and not plan.egress_only
    assert not area.contains(plan.egress_target.xy)
    assert feasible(engine, aircraft, plan)
    assert FlightPlan.from_dict(plan.to_dict()) == plan
    assert not event.result["residual_conflicts"]
    engine.step(10)
    assert aircraft.position != start
    assert not area.contains(aircraft.position.xy)
    assert not engine.conflicts
    points = [aircraft.position, *engine.plans[aircraft.id].positions[engine.plans[aircraft.id].cursor:]]
    assert all(not area.intersects_segment(a.xy, b.xy) for a, b in zip(points, points[1:]))


def test_no_downstream_route_still_exits_area_before_holding(engine):
    engine.demo_enabled = False
    engine.step(10)
    aircraft = engine.aircraft["UAV-001"]
    source = aircraft.position.model_copy()
    aircraft.destination = source.model_copy()
    area = rectangle_polygon(source.x, source.y, 100, 80)
    event = engine.inject_event(Event(type=EventType.AIRSPACE_CLOSURE, payload={
        "polygon": area.model_dump(), "min_altitude": 0, "max_altitude": 300}))
    plan = engine.plans[aircraft.id]
    assert aircraft.id in event.result["safe_exit_holding_aircraft"]
    assert plan.egress_only and plan.egress_target and feasible(engine, aircraft, plan)
    engine.step(5)
    assert plan.complete
    assert not area.contains(aircraft.position.xy)
    assert aircraft.status == AircraftStatus.HOVERING
    assert aircraft.position != source


def test_evacuation_leg_cannot_leave_and_reenter_concave_area():
    area = Polygon2D(points=[Position2D(x=x, y=y) for x, y in
                            [(0, 0), (10, 0), (10, 10), (7, 10),
                             (7, 3), (3, 3), (3, 10), (0, 10)]])
    source = Position3D(x=1, y=8, z=150)
    assert not _continuous_exit(source, Position3D(x=11, y=8, z=150), [area])
    assert _continuous_exit(source, Position3D(x=-8, y=8, z=150), [area])


def test_invalid_event_has_no_side_effect(engine):
    before = engine.snapshot()
    with pytest.raises(ValueError):
        engine.inject_event(Event(type=EventType.ROUTE_CONGESTION,
                                  related_id=next(iter(engine.routes)), payload={"capacity": 0}))
    assert engine.snapshot() == before


def test_failure_reaches_a_reserved_bay_by_physical_motion(engine):
    engine.demo_enabled = False
    aircraft = engine.aircraft["UAV-004"]
    origin = aircraft.position.model_copy()
    event = engine.inject_event(Event(type=EventType.AIRCRAFT_FAILURE, related_id=aircraft.id))
    assert event.result["success"] and not event.result["landed"]
    assert aircraft.position == origin
    assert aircraft.status == AircraftStatus.DIVERTING
    assert event.result["planned_distance_m"] <= event.result["remaining_range_m"]
    engine.step(180)
    landing = next(e for e in engine.events if e.type == EventType.EMERGENCY_LANDING)
    assert landing.result["landed"]
    assert aircraft.position == engine.waypoints[event.result["bay_id"]].position
    assert engine.distances[aircraft.id] > 150


def test_no_reachable_bay_records_failure_without_fake_landing(engine):
    aircraft = engine.aircraft["UAV-001"]
    aircraft.battery = 0.00001
    event = engine.inject_event(Event(type=EventType.AIRCRAFT_FAILURE, related_id=aircraft.id))
    assert not event.result["success"]
    assert aircraft.status == AircraftStatus.EMERGENCY
    assert aircraft.id not in engine.plans
    assert not any(e.type == EventType.EMERGENCY_LANDING for e in engine.events)


def test_paused_weather_edit_invalidates_existing_plans(engine):
    engine.pause()
    engine.registry.weather.add(Weather(affected_area=rectangle_polygon(2900, 200, 200, 120)))
    assert engine.plans
    engine.sync_entities()
    assert not engine.plans


def test_full_report_keeps_events_outside_live_timeline(engine):
    for i in range(110):
        engine._record(Event(type=EventType.INFO, severity="warning", description=f"audit {i}"))
    assert len(engine.snapshot()["events"]) == 100
    assert len(engine.report()["events"]) == 111
    assert engine.snapshot()["metrics"]["alert_count"] == 110


def test_demo_weather_dissipates_and_stops_after_terminal_tasks(engine):
    engine.step(600)
    assert engine.demo_complete and engine.demo_stage == 4
    assert not engine.running
    assert engine.time_s < 600
    assert not engine.weather
    assert any(e.description.startswith("演示雷暴消散") for e in engine.events)
    assert any(e.description.startswith("自动演示停止") for e in engine.events)


def test_sqlite_restores_paused_motion_and_exact_city(tmp_path):
    path = tmp_path / "flight.sqlite3"
    with TestClient(create_app(database_path=path)) as client:
        assert client.post("/api/simulation/demo", json={"aircraft_count": 4}).status_code == 200
        saved = client.post("/api/simulation/step", json={"steps": 3}).json()
        client.post("/api/simulation/pause")
    with TestClient(create_app(database_path=path)) as client:
        restored = client.get("/api/simulation/state").json()
        assert not restored["simulation"]["running"]
        assert restored["simulation"]["time_s"] == 3
        assert restored["aircraft"] == saved["aircraft"]
        assert restored["environment"]["buildings"] == saved["environment"]["buildings"]
        advanced = client.post("/api/simulation/step", json={"steps": 1}).json()
        assert advanced["metrics"]["total_flight_distance_m"] > saved["metrics"]["total_flight_distance_m"]


def test_api_controls_and_websocket_share_the_same_state(client):
    assert client.post("/api/simulation/start").status_code == 409
    assert client.post("/api/simulation/speed", json={"speed": 0}).status_code == 422
    client.post("/api/simulation/demo", json={"aircraft_count": 4})
    with client.websocket_connect("/api/ws") as ws:
        first = ws.receive_json()
        assert first["sequence"] == 1 and first["data"]["environment"]["buildings"]
        stepped = client.post("/api/simulation/step", json={"steps": 2}).json()
        for _ in range(10):
            message = ws.receive_json()
            if message["data"]["simulation"]["time_s"] == 2:
                break
        assert message["data"]["metrics"] == stepped["metrics"]
        assert "environment" not in message["data"]
    assert client.post("/api/simulation/start").status_code == 200
    assert client.post("/api/simulation/step", json={"steps": 1}).status_code == 409
    assert client.post("/api/simulation/demo", json={"aircraft_count": 4}).status_code == 409
    assert client.post("/api/simulation/pause").json()["simulation"]["running"] is False


def test_broad_phase_matches_exact_detector_on_random_piecewise_trajectories():
    rng = random.Random(823)
    limits = ConflictThresholds(horizontal_m=30, vertical_m=15, time_window_s=10)
    paths = {str(i): [TrajectoryPoint(time=t, position=Position3D(
        x=rng.uniform(-200, 200), y=rng.uniform(-200, 200), z=rng.uniform(0, 150)))
        for t in (0, 2, 5, 10)] for i in range(40)}
    expected = {(a, b): _first_overlap(paths[a], paths[b], limits, 0)
                for a, b in combinations(sorted(paths), 2)}
    expected = {key: value[0] for key, value in expected.items() if value is not None}
    actual = {(c.aircraft_a, c.aircraft_b): c.conflict_time for c in detect_conflicts(paths, limits)}
    assert actual == pytest.approx(expected)
