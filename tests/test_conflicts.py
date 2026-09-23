"""Continuous separation and candidate safety regressions, without sampling."""

import math

import pytest
from pydantic import ValidationError

from algorithms.conflict_detection import ConflictThresholds, TrajectoryPoint, detect_conflicts
from algorithms.conflict_resolution import (
    ResolutionCandidate, ResolutionEnvironment, ResolutionWeights, resolve_conflict,
)
from core.models import Position3D


def path(*entries):
    return [TrajectoryPoint(time=t, position=Position3D(x=x, y=y, z=z))
            for t, x, y, z in entries]


def crossing():
    return {"a": path((0, -10, 0, 50), (10, 10, 0, 50)),
            "b": path((0, 0, -10, 50), (10, 0, 10, 50))}


def limits(**kwargs):
    return ConflictThresholds(**{"horizontal_m": 1, "vertical_m": 2, **kwargs})


def stopped(aircraft_id="a", action="delay", **kwargs):
    initial = crossing()[aircraft_id][0].position
    return ResolutionCandidate(action=action, aircraft_id=aircraft_id,
                               trajectory=[TrajectoryPoint(time=t, position=initial)
                                           for t in (0, 10)], **kwargs)


def test_crossing_between_samples_returns_first_entry_absolute_time():
    trajectories = {key: [p.model_copy(update={"time": p.time + 100}) for p in points]
                    for key, points in crossing().items()}
    conflict, = detect_conflicts(trajectories, limits(), now=100)
    assert conflict.conflict_time == pytest.approx(105 - 1 / math.sqrt(8))
    assert conflict.conflict_position.x == pytest.approx(-1 / math.sqrt(8))
    assert conflict.conflict_position.y == pytest.approx(-1 / math.sqrt(8))
    assert conflict.conflict_position.z == 50
    assert conflict.severity == "warning"


def test_now_clips_existing_conflict_and_reports_critical():
    conflict, = detect_conflicts(crossing(), limits(), now=5)
    assert conflict.conflict_time == 5
    assert conflict.severity == "critical"


def test_future_past_and_disjoint_time_domains_do_not_conflict():
    assert not detect_conflicts(crossing(), limits(time_window_s=4))
    assert not detect_conflicts(crossing(), limits(), now=6)
    assert not detect_conflicts({"a": path((0, 0, 0, 0), (1, 0, 0, 0)),
                                 "b": path((2, 0, 0, 0), (3, 0, 0, 0))}, limits())


def test_altitude_separation_and_tangency_are_inclusive():
    trajectories = crossing()
    for p in trajectories["b"]:
        p.position.z = 52.001
    assert not detect_conflicts(trajectories, limits())
    for p in trajectories["b"]:
        p.position.z = 52
    assert len(detect_conflicts(trajectories, limits())) == 1


def test_horizontal_tangency_detected_but_near_miss_is_not():
    trajectories = {"a": path((0, -10, 0, 0), (10, 10, 0, 0)),
                    "b": path((0, 0, 1, 0), (10, 0, 1, 0))}
    conflict, = detect_conflicts(trajectories, limits())
    assert conflict.conflict_time == pytest.approx(5)
    for p in trajectories["b"]:
        p.position.y = 1.000001
    assert not detect_conflicts(trajectories, limits())


def test_horizontal_and_vertical_breaches_must_overlap_in_time():
    trajectories = {"a": path((0, -10, 0, 0), (10, 10, 0, 0)),
                    "b": path((0, 0, 0, 10), (10, 0, 0, 0))}
    assert not detect_conflicts(trajectories, limits())
    trajectories["a"] = path((0, 0, 0, 0), (10, 0, 0, 0))
    conflict, = detect_conflicts(trajectories, limits())
    assert conflict.conflict_time == pytest.approx(8)


def test_piecewise_paths_with_different_breakpoints_and_stationary_endpoints():
    trajectories = {"a": path((0, -10, 0, 0), (4, -10, 0, 0), (6, 10, 0, 0)),
                    "b": path((1, 0, 0, 0), (3, 0, 0, 0), (8, 0, 0, 0))}
    conflict, = detect_conflicts(trajectories, limits())
    assert conflict.conflict_time == pytest.approx(4.9)


def test_empty_single_point_and_shared_time_boundary_domains():
    assert not detect_conflicts({"a": [], "b": path((0, 0, 0, 0))}, limits())
    conflict, = detect_conflicts({"a": path((1, 0, 0, 0)),
                                 "b": path((0, 0, 0, 0), (1, 0, 0, 0))}, limits())
    assert conflict.conflict_time == 1
    assert not detect_conflicts({"a": path((2, 0, 0, 0)),
                                 "b": path((0, 0, 0, 0), (1, 0, 0, 0))}, limits())


def test_result_is_deterministic_and_one_conflict_per_pair():
    trajectories = {key: path((0, 0, 0, 0), (2, 0, 0, 0), (10, 0, 0, 0))
                    for key in ("c", "a", "b")}
    assert [(c.aircraft_a, c.aircraft_b) for c in detect_conflicts(trajectories)] == [
        ("a", "b"), ("a", "c"), ("b", "c"),
    ]


@pytest.mark.parametrize("field,value", [("horizontal_m", 0), ("vertical_m", -1),
                                        ("time_window_s", float("inf")),
                                        ("horizontal_m", float("nan"))])
def test_thresholds_reject_invalid_values(field, value):
    with pytest.raises(ValidationError):
        ConflictThresholds(**{field: value})


@pytest.mark.parametrize("times", [(1, 1), (2, 1)])
def test_nonincreasing_trajectories_are_rejected(times):
    with pytest.raises(ValueError, match="strictly increasing"):
        detect_conflicts({"a": path(*[(t, 0, 0, 0) for t in times])})


def test_nonfinite_values_and_assignment_rejected():
    with pytest.raises(ValidationError):
        TrajectoryPoint(time=float("nan"), position=Position3D())
    with pytest.raises(ValueError):
        detect_conflicts({}, now=float("inf"))
    threshold = limits()
    with pytest.raises(ValidationError):
        threshold.vertical_m = 0


@pytest.mark.parametrize("action", ["speed", "altitude", "reroute", "delay"])
def test_all_candidate_methods_supported_and_original_trajectories_unchanged(action):
    trajectories = crossing()
    before = {key: [p.model_dump() for p in points] for key, points in trajectories.items()}
    conflict, = detect_conflicts(trajectories, limits())
    candidate = stopped(action=action, delay_s=2, extra_energy=3, congestion_cost=4,
                        parameters={"candidate_id": action})
    result = resolve_conflict(conflict, ResolutionEnvironment(
        trajectories, [candidate], thresholds=limits(),
        weights=ResolutionWeights(delay=2, energy=3, congestion=4),
    ))
    assert result.success and result.action == action and result.aircraft_id == "a"
    assert result.cost == 29
    assert result.parameters == {"candidate_id": action}
    assert before == {key: [p.model_dump() for p in points] for key, points in trajectories.items()}


def test_candidate_that_creates_conflict_with_third_aircraft_is_rejected():
    trajectories = crossing()
    trajectories["c"] = path((0, -10, 5, 50), (10, -10, -5, 50))
    conflict, = detect_conflicts(trajectories, limits())
    faster = ResolutionCandidate(action="speed", aircraft_id="a", extra_energy=2,
                                  parameters={"speed_mps": 4},
                                  trajectory=path((0, -10, 0, 50), (10, 30, 0, 50)))
    result = resolve_conflict(conflict, ResolutionEnvironment(
        trajectories, [stopped(), faster], thresholds=limits(),
    ))
    assert result.success and result.action == "speed" and result.cost == 2


@pytest.mark.parametrize("bad_candidate", [
    ResolutionCandidate(action="speed", aircraft_id="a", trajectory=crossing()["a"]),
    stopped(feasible=False),
    ResolutionCandidate(action="altitude", aircraft_id="a",
                        trajectory=path((0, -10, 0, 100), (10, 10, 0, 100))),
    ResolutionCandidate(action="delay", aircraft_id="a",
                        trajectory=path((0, -10, 0, 50), (1, -10, 0, 50))),
    ResolutionCandidate(action="delay", aircraft_id="a", trajectory=[]),
])
def test_residual_conflict_infeasible_teleport_truncated_and_empty_candidates_unresolved(bad_candidate):
    trajectories = crossing()
    conflict, = detect_conflicts(trajectories, limits())
    result = resolve_conflict(conflict, ResolutionEnvironment(
        trajectories, [bad_candidate], thresholds=limits(),
    ))
    assert not result.success and result.action == "unresolved"
    assert result.cost is None and result.aircraft_id is None
    assert "null" in result.model_dump_json()


def test_equal_cost_prefers_changing_lower_priority_aircraft():
    trajectories = crossing()
    conflict, = detect_conflicts(trajectories, limits())
    result = resolve_conflict(conflict, ResolutionEnvironment(
        trajectories, [stopped("a"), stopped("b")], priorities={"a": 9, "b": 1},
        thresholds=limits(),
    ))
    assert result.aircraft_id == "b"


def test_unrelated_existing_pair_conflict_does_not_reject_safe_candidate():
    trajectories = crossing()
    trajectories.update({key: path((0, 100, 100, 50), (10, 100, 100, 50))
                         for key in ("c", "d")})
    conflict = next(c for c in detect_conflicts(trajectories, limits()) if c.aircraft_a == "a")
    assert resolve_conflict(conflict, ResolutionEnvironment(
        trajectories, [stopped()], thresholds=limits(),
    )).success


def test_cost_weights_change_selection_and_invalid_cost_is_rejected():
    trajectories = crossing()
    conflict, = detect_conflicts(trajectories, limits())
    candidates = [stopped(action="delay", delay_s=2),
                  stopped(action="speed", extra_energy=1)]
    env = ResolutionEnvironment(trajectories, candidates, thresholds=limits())
    assert resolve_conflict(conflict, env).action == "speed"
    env.weights = ResolutionWeights(delay=1, energy=3)
    assert resolve_conflict(conflict, env).action == "delay"
    with pytest.raises(ValidationError):
        stopped(delay_s=-1)
    with pytest.raises(ValidationError):
        ResolutionWeights(energy=float("inf"))
