"""Regressions for executable forecasts: capacity, takeoff and energy constraints."""

from copy import deepcopy
from types import SimpleNamespace

import pytest

from algorithms.conflict_detection import ConflictThresholds, TrajectoryPoint, detect_conflicts
from algorithms.conflict_detection.models import validate_trajectory
from algorithms.conflict_resolution import ResolutionEnvironment, resolve_conflict
from core.models import Aircraft, AircraftStatus, Position3D
from simulation.aircraft.flight import FlightPlan
from simulation.engine.safety import candidates, forecast, forecast_plan


def point(x=0, y=0, z=100):
    return Position3D(x=x, y=y, z=z)


def aircraft(name, position, **kwargs):
    return Aircraft(id=name, position=position, status=AircraftStatus.EN_ROUTE, **kwargs)


def engine_for(aircraft_list, plans, blocked=None, now=0):
    blocked = blocked or set()
    return SimpleNamespace(
        aircraft={a.id: a for a in aircraft_list}, plans=plans, time_s=now,
        _can_enter=lambda aid, plan, cursor, position=None: (aid, cursor) not in blocked,
        settings=SimpleNamespace(conflict_altitude_step_m=30, conflict_max_vertical_speed_mps=2),
        collision_city=SimpleNamespace(is_segment_clear=lambda start, end: True),
        restrictions={}, weather={}, routes={}, occupancy={},
    )


def execute_trace(engine, name, plan, duration):
    """Advance actual motion on copies, using exactly the execution capacity gate."""
    copy_aircraft = engine.aircraft[name].model_copy(deep=True)
    copy_plan = deepcopy(plan)
    trace = []
    copy_plan.advance(copy_aircraft, duration,
                      lambda cursor: engine._can_enter(name, copy_plan, cursor,
                                                       position=copy_aircraft.position), trace)
    return [TrajectoryPoint(time=engine.time_s + t, position=p) for t, p in trace]


def test_capacity_blocked_speed_candidate_cannot_claim_aircraft_moves_to_safety():
    # Previously A's forecast waited, but its speed candidate falsely moved north;
    # B actually reached A's unchanged position after approximately 5.33 seconds.
    a = aircraft("A", point())
    b = aircraft("B", point(80))
    plans = {
        "A": FlightPlan([a.position, point(0, 300)], [], route_ids=["full"]),
        "B": FlightPlan([b.position, point(-220)], [], route_ids=[None]),
    }
    engine = engine_for([a, b], plans, blocked={("A", 1)})
    limits = ConflictThresholds()
    trajectories = forecast(engine, limits)
    conflict, = detect_conflicts(trajectories, limits)
    assert conflict.conflict_time == pytest.approx(50 / 15)
    choices, replacement_plans = candidates(engine, conflict, limits)
    blocked_speed_choices = [c for c in choices if c.aircraft_id == "A" and c.action == "speed"]
    assert blocked_speed_choices
    for choice in blocked_speed_choices:
        assert all(p.position == a.position for p in choice.trajectory)
        assert detect_conflicts({"A": choice.trajectory, "B": trajectories["B"]}, limits)

    decision = resolve_conflict(conflict, ResolutionEnvironment(
        trajectories=trajectories, candidates=choices, thresholds=limits,
    ))
    assert decision.success
    selected = replacement_plans[decision.parameters["candidate_key"]]
    actual = {name: execute_trace(engine, name,
              selected if name == decision.aircraft_id else plan, limits.time_window_s)
              for name, plan in plans.items()}
    assert not detect_conflicts(actual, limits)
    assert a.position == point() and b.position == point(80)
    assert all(plan.cursor == 1 for plan in plans.values())


def test_takeoff_from_ground_is_detected_before_entering_occupied_altitude():
    departing = aircraft("TAKEOFF", point(z=0))
    departing.status = AircraftStatus.TAKING_OFF
    hovering = aircraft("HOVER", point(z=20))
    idle = aircraft("IDLE", point(z=0))
    idle.status = AircraftStatus.GROUNDED
    offline = aircraft("OFFLINE", point(z=10))
    offline.status = AircraftStatus.OFFLINE
    plan = FlightPlan([departing.position, point(z=100)], [])
    engine = engine_for([departing, hovering, idle, offline], {departing.id: plan}, now=50)
    limits = ConflictThresholds(horizontal_m=1, vertical_m=5, time_window_s=10)
    trajectories = forecast(engine, limits)
    assert set(trajectories) == {"TAKEOFF", "HOVER"}
    assert trajectories["TAKEOFF"][0].position.z == 0
    assert trajectories["TAKEOFF"][-1].position.z == 20
    conflict, = detect_conflicts(trajectories, limits, now=50)
    assert conflict.conflict_time == pytest.approx(57.5)
    assert departing.position.z == 0 and plan.cursor == 1


def test_low_battery_forecast_stops_and_exposes_rear_approach_conflict():
    low = aircraft("LOW", point(), battery=0.0001, max_range_m=18000)
    follower = aircraft("FOLLOWER", point(-80))
    plans = {
        "LOW": FlightPlan([low.position, point(1000)], []),
        "FOLLOWER": FlightPlan([follower.position, point(220)], []),
    }
    engine = engine_for([low, follower], plans)
    limits = ConflictThresholds()
    trajectories = forecast(engine, limits)
    predicted = trajectories["LOW"]
    assert predicted[-1].position.x == pytest.approx(1.8)
    assert [p.time for p in predicted] == pytest.approx([0, 0.12, 10])
    assert predicted[-2].position == predicted[-1].position
    conflict, = detect_conflicts(trajectories, limits)
    assert conflict.conflict_time == pytest.approx((80 + 1.8 - 30) / 15)
    assert predicted == execute_trace(engine, "LOW", plans["LOW"], 10)
    assert low.battery == 0.0001 and low.position.x == 0


def test_capacity_gate_is_checked_again_at_future_segment_entry():
    a = aircraft("A", point(), max_speed=10)
    plan = FlightPlan([a.position, point(10), point(100)], [], speed_mps=10,
                      route_ids=["open", "full"])
    engine = engine_for([a], {"A": plan}, blocked={("A", 2)}, now=100)
    result = forecast_plan(engine, "A", plan, ConflictThresholds(time_window_s=10))
    assert [p.time for p in result] == pytest.approx([100, 101, 110])
    assert [p.position.x for p in result] == pytest.approx([0, 10, 10])
    assert result == execute_trace(engine, "A", plan, 10)
    assert plan.cursor == 1 and a.position.x == 0


def test_forecast_respects_aircraft_max_speed_and_does_not_mutate_state():
    a = aircraft("SLOW", point(), max_speed=3)
    plan = FlightPlan([a.position, point(100)], [], speed_mps=20, wait_s=2)
    engine = engine_for([a], {a.id: plan}, now=17)
    before_aircraft, before_plan = a.model_dump(), deepcopy(plan.to_dict())
    result = forecast_plan(engine, a.id, plan, ConflictThresholds(time_window_s=10))
    assert [p.time for p in result] == pytest.approx([17, 19, 27])
    assert result[-1].position.x == 24
    assert a.model_dump() == before_aircraft
    assert plan.to_dict() == before_plan


def test_diagonal_climb_respects_vertical_rate_and_actual_energy_budget():
    a = aircraft("CLIMB", point(z=0), max_range_m=1000)
    plan = FlightPlan([a.position, point(30, 0, 40)], [], speed_mps=15, vertical_speed_mps=2)
    trace = []
    distance, energy = plan.advance(a, 5, trace=trace)
    assert a.position.x == pytest.approx(7.5)
    assert a.position.z == pytest.approx(10)
    assert distance == pytest.approx(12.5)
    assert energy == pytest.approx(12.5 + 4 * 10)
    assert a.battery == pytest.approx(1 - 52.5 / 1000)
    assert a.speed == pytest.approx(2.5)
    assert trace[0][0] == 0 and trace[-1][0] == 5
    for (ta, pa), (tb, pb) in zip(trace, trace[1:]):
        assert abs(pb.z - pa.z) <= 2 * (tb - ta) + 1e-9


def test_climb_battery_exhaustion_creates_stationary_tail_without_teleport():
    a = aircraft("EMPTY", point(z=0), battery=0.01, max_range_m=1000)
    plan = FlightPlan([a.position, point(z=100)], [], vertical_speed_mps=2)
    trace = []
    distance, energy = plan.advance(a, 10, trace=trace)
    assert distance == pytest.approx(2)
    assert energy == pytest.approx(10)
    assert a.battery == 0 and a.position.z == pytest.approx(2)
    assert [t for t, _ in trace] == pytest.approx([0, 1, 10])
    assert trace[-1][1] == trace[-2][1]
    assert not plan.complete


def test_residual_dt_crosses_waypoints_and_split_steps_match_single_step():
    a = aircraft("FULL", point(), max_range_m=1000)
    b = a.model_copy(deep=True)
    plan = FlightPlan([a.position, point(5), point(20)], [], speed_mps=10, wait_s=0.25)
    split = deepcopy(plan)
    trace = []
    whole_distance, whole_energy = plan.advance(a, 2, trace=trace)
    first = split.advance(b, 0.75)
    second = split.advance(b, 1.25)
    assert a.position == b.position == point(17.5)
    assert a.battery == pytest.approx(b.battery)
    assert whole_distance == pytest.approx(first[0] + second[0]) == pytest.approx(17.5)
    assert whole_energy == pytest.approx(first[1] + second[1])
    assert [t for t, _ in trace] == pytest.approx([0, 0.25, 0.75, 2])
    assert plan.cursor == split.cursor == 2


@pytest.mark.parametrize("wait", [0, 4, 10])
def test_wait_and_repeated_waypoints_produce_strictly_increasing_forecast(wait):
    a = aircraft("WAIT", point())
    plan = FlightPlan([a.position, a.position, point(15), point(15)], [], wait_s=wait)
    engine = engine_for([a], {a.id: plan})
    result = forecast_plan(engine, a.id, plan, ConflictThresholds(time_window_s=10))
    validate_trajectory(result)
    assert result[0].time == 0 and result[-1].time == 10
    assert result[-1].position.x == (0 if wait == 10 else 15)


def test_zero_dt_and_zero_battery_cannot_move_aircraft():
    a = aircraft("ZERO", point(), battery=0)
    plan = FlightPlan([a.position, point(100)], [], wait_s=3)
    before = deepcopy(plan.to_dict())
    trace = []
    assert plan.advance(a, 0, trace=trace) == (0, 0)
    assert plan.to_dict() == before
    assert trace == [(0, point())]
    trace.clear()
    assert plan.advance(a, 10, trace=trace) == (0, 0)
    assert a.position == point() and a.battery == 0
    assert trace[0][0] == 0 and trace[-1][0] == 10
    assert all(p == point() for _, p in trace)
