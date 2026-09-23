"""Select the least-cost feasible candidate after whole-fleet safety checks."""

from __future__ import annotations

import math

from algorithms.conflict_detection import Conflict, TrajectoryPoint, detect_conflicts
from algorithms.conflict_detection.continuous import _position_at
from algorithms.conflict_detection.models import validate_trajectory

from .models import Resolution, ResolutionCandidate, ResolutionEnvironment


def _anchored_and_complete(candidate: ResolutionCandidate, env: ResolutionEnvironment) -> bool:
    original = env.trajectories.get(candidate.aircraft_id, [])
    replacement = candidate.trajectory
    if not original or not replacement:
        return False
    start = max(env.now, original[0].time)
    end = min(env.now + env.thresholds.time_window_s, original[-1].time)
    if start > end or replacement[0].time > start or replacement[-1].time < end:
        return False

    def at(points: list[TrajectoryPoint]):
        for a, b in list(zip(points, points[1:])) or [(points[0], points[0])]:
            if a.time <= start <= b.time:
                return _position_at(a, b, start)
        raise ValueError("Trajectory does not cover its claimed interval")

    # Even a caller-marked feasible candidate may not teleport at the decision time.
    return at(original).distance_to(at(replacement)) <= 1e-6


def resolve_conflict(conflict: Conflict, environment: ResolutionEnvironment) -> Resolution:
    """Safety is a hard constraint; delay, energy and congestion determine safe ranking.

    The simulator generates candidates and validates obstacles, airspace and
    aircraft performance. This function independently verifies continuity and
    separation against every other forecast, without mutating flight state.
    """
    env = environment
    if not math.isfinite(env.now):
        raise ValueError("Current simulation time must be finite")
    for trajectory in env.trajectories.values():
        validate_trajectory(trajectory)
    selected: ResolutionCandidate | None = None
    best_key: tuple[float, int, str, str, int] | None = None
    for index, candidate in enumerate(env.candidates):
        if not candidate.feasible or candidate.aircraft_id not in (
            conflict.aircraft_a, conflict.aircraft_b,
        ):
            continue
        validate_trajectory(candidate.trajectory)
        if not _anchored_and_complete(candidate, env):
            continue
        # Only pairs involving the altered trajectory need rechecking: O(n), not O(n²).
        if any(detect_conflicts(
            {candidate.aircraft_id: candidate.trajectory, other: trajectory},
            env.thresholds, env.now,
        ) for other, trajectory in env.trajectories.items() if other != candidate.aircraft_id):
            continue
        cost = (env.weights.delay * candidate.delay_s
                + env.weights.energy * candidate.extra_energy
                + env.weights.congestion * candidate.congestion_cost)
        if not math.isfinite(cost):
            raise ValueError("Resolution weighted cost must be finite")
        # Larger priority values mean higher priority; equal-cost plans protect them.
        key = (cost, env.priorities.get(candidate.aircraft_id, 0),
               candidate.aircraft_id, candidate.action, index)
        if best_key is None or key < best_key:
            selected, best_key = candidate, key
    if selected is None:
        return Resolution(
            action="unresolved", success=False,
            reason="No candidate preserves trajectory continuity and fleet separation in the prediction window",
        )
    return Resolution(
        action=selected.action, aircraft_id=selected.aircraft_id,
        parameters=dict(selected.parameters), cost=best_key[0], success=True,
        reason=(f"Safe against all predicted aircraft; cost = "
                f"{env.weights.delay:g}×{selected.delay_s:g} delay + "
                f"{env.weights.energy:g}×{selected.extra_energy:g} energy + "
                f"{env.weights.congestion:g}×{selected.congestion_cost:g} congestion"),
    )
